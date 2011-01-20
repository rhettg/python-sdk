#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Python client library for the Facebook Platform.

This client library is designed to support the Graph API and the official
Facebook JavaScript SDK, which is the canonical way to implement
Facebook authentication. Read more about the Graph API at
http://developers.facebook.com/docs/api. You can download the Facebook
JavaScript SDK at http://github.com/facebook/connect-js/.

If your application is using Google AppEngine's webapp framework, your
usage of this module might look like this:

    user = facebook.get_user_from_cookie(self.request.cookies, key, secret)
    if user:
        graph = facebook.GraphAPI(user["access_token"])
        profile = graph.fetch("me")
        friends = graph.fetch_connections("me", "friends")

"""

import cgi
import base64
import hashlib
import hmac
import httplib
import logging
import time
import urllib


# Find a JSON parser
try:
    import json
    _decode_json = json.loads
    _encode_json = json.dumps
except ImportError:
    try:
        import simplejson
    except ImportError:
        # For Google AppEngine
        from django.utils import simplejson
    _decode_json = simplejson.loads
    _encode_json = simplejson.dumps

class Error(Exception): pass

class CommunicationError(Error): pass

class GraphAPIError(Error):
    def __init__(self, type, message):
        Exception.__init__(self, message)
        self.type = type


GRAPH_API_HOST = "graph.facebook.com"
USER_AGENT = "Facebook Python API Client 1.0"

log = logging.getLogger(__name__)


class GraphAPI(object):
    """A client for the Facebook Graph API.

    See http://developers.facebook.com/docs/api for complete documentation
    for the API.

    The Graph API is made up of the objects in Facebook (e.g., people, pages,
    events, photos) and the connections between them (e.g., friends,
    photo tags, and event RSVPs). This client provides access to those
    primitive types in a generic way. For example, given an OAuth access
    token, this will fetch the profile of the active user and the list
    of the user's friends:

       graph = facebook.GraphAPI(access_token)
       user = graph.fetch("me")
       friends = graph.fetch_connections(user["id"], "friends")

    You can see a list of all of the objects and connections supported
    by the API at http://developers.facebook.com/docs/reference/api/.

    You can obtain an access token via OAuth or by using the Facebook
    JavaScript SDK. See http://developers.facebook.com/docs/authentication/
    for details.

    If you are using the JavaScript SDK, you can use the
    get_user_from_cookie() method below to get the OAuth access token
    for the active user from the cookie saved by the SDK.
    """
    def __init__(self, access_token):
        self.access_token = access_token

    def fetch(self, id, metadata=None, fields=None):
        """Fetchs the given object from the graph."""
        args = dict()
        if metadata is not None:
            args = {
                'metadata': metadata
            }
        if fields is not None:
            args['fields'] = ",".join(fields)

        # Unset the args if we didn't need it
        args = args or None
        
        return self.request("GET", "/" + str(id), args=args)

    def multi_fetch(self, ids):
        """Fetch multiple objects by id"""
        return self.request("GET", "/", args={'ids': ",".join(ids)})

    def fetch_url(self, url):
        """Fetch an object by it's URL
        
        This is useful for when you don't have the actual id, but just a url.
        """
        return self.multi_fetch([url])

    def fetch_connections(self, id, connection_name, limit=None, offset=None, until=None, since=None):
        path = "/".join(("", str(id), connection_name))
        args = dict()

        if limit:
            args['limit'] = limit
        if offset:
            args['offset'] = offset
        if until:
            args['until'] = time.mktime(until.timetuple())
        if since:
            args['since'] = time.mktime(since.timetuple())
            

        # Unset the args if we didn't need it
        args = args or None
        
        return self.request("GET", path, args=args)
        
    def put(self, parent_id, connection_name, **data):
        """Writes the given object to the graph, connected to the given parent.

        For example,

            graph.put("me", "feed", message="Hello, world")

        writes "Hello, world" to the active user's wall. Likewise, this
        will comment on a the first post of the active user's feed:

            feed = graph.fetch_connections("me", "feed")
            post = feed["data"][0]
            graph.put(post["id"], "comments", message="First!")

        See http://developers.facebook.com/docs/api#publishing for all of
        the supported writeable objects.

        Most write operations require extended permissions. For example,
        publishing wall posts requires the "publish_stream" permission. See
        http://developers.facebook.com/docs/authentication/ for details about
        extended permissions.
        """
        
        path = "/".join(("", str(parent_id), connection_name))
        
        return self.request("POST", path, data=data)
    
    def search(self, object_type, query, **kwargs):
        """Search over public objects in the social graph
        
        Example object types would be: 'user, page, event, group, place, checkin'

        Some objects types have additional query terms that can be passed as kwargs to this function
        """
        args = {
            'q': query,
            'type': object_type,
        }
        args.update(kwargs)
        return self.request("GET", "/search", args=args)
        
    def delete(self, id):
        return self.request("DELETE", "/" + id)

    def request(self, method, path, args=None, data=None):
        """Fetches the given path in the Graph API under the context of the curent access token.

        """
        return graph_api_request(method, path, args=args, data=data, access_token=self.access_token)


    # Common GraphAPI operations
    def put_wall_post(self, message, attachment={}, profile_id="me"):
        """Writes a wall post to the given profile's wall.

        We default to writing to the authenticated user's wall if no
        profile_id is specified.

        attachment adds a structured attachment to the status message being
        posted to the Wall. It should be a dictionary of the form:

            {"name": "Link name"
             "link": "http://www.example.com/",
             "caption": "{*actor*} posted a new review",
             "description": "This is a longer description of the attachment",
             "picture": "http://www.example.com/thumbnail.jpg"}

        """
        return self.put(profile_id, "feed", message=message, **attachment)

    def put_comment(self, object_id, message):
        """Writes the given comment on the given post."""
        return self.put(object_id, "comments", message=message)

    def put_like(self, object_id):
        """Likes the given post."""
        return self.put(object_id, "likes")


class TestUser(object):
    """Class for creating an manipulating test users"""
    _graph_api_cls = GraphAPI
    
    def __init__(self, user_data):
        self.user_data = user_data
        self._graph_api = None

    @property
    def id(self):
        return self.user_data['id']

    @property
    def graph_api(self):
        if not self._graph_api:
            if not self.user_data['access_token']:
                raise Error("User does not have current application installed, no access_token")

            self._graph_api = self._graph_api_cls(self.user_data['access_token'])
        return self._graph_api

    @property
    def profile(self):
        return self.graph_api.fetch("me")

    def build_signed_request(self, user_id, app_secret):
        return build_signed_request(user_id, self.user_data['access_token'], app_secret)

    def friend_user(self, other_user):
        """Associate the two TestUser's as friends"""
        other_user.graph_api.put(other_user.id, "friends/%s" % self.id)
        self.graph_api.put(self.id, "friends/%s" % other_user.id)

    def __repr__(self):
        return "<TestUser: %r>" % self.user_data

    @classmethod
    def create(cls, graph_api, app_id, installed=False, permissions=None):
        args = {}

        if permissions:
            args['permissions'] = ",".join(permissions)

        args['installed'] = installed

        user = TestUser(graph_api.put(app_id, "accounts/test-users", **args))
        user._graph_api_cls = graph_api.__class__
        return user

    @classmethod
    def list_all(cls, graph_api, app_id):
        response = graph_api.fetch_connections(app_id, "accounts/test-users")
        return [TestUser(user_data) for user_data in response['data']]

    @classmethod
    def delete_all(cls, graph_api, app_id):
        """Remote all test users"""
        for user in cls.list_all(graph_api, app_id):
            graph_api.delete(user.id)


def get_oauth_access_token(app_id, app_secret):
    """Authenticates as an application and retrieves the OAuth access token"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/plain',
    }

    data = {"grant_type": "client_credentials", "client_id": app_id, "client_secret": app_secret}
    
    conn = httplib.HTTPSConnection(GRAPH_API_HOST)
    
    conn.request("POST", "/oauth/access_token", urllib.urlencode(data), headers=headers)
    response = conn.getresponse()

    if response.status != httplib.OK:
        raise CommunicationError((response.status, response.reason))

    access_token = response.read()
    if not access_token:
        raise AuthenticationError("Unknown response")

    return access_token.split("=")[1]

def graph_api_request(method, path, args=None, data=None, access_token=None, headers=None):
    out_headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/javascript',
    }

    args = args or dict()

    if headers:
        out_headers.update(headers)

    if access_token is not None:
        if data is not None:
            data["access_token"] = access_token
        else:
            args["access_token"] = access_token

    out_data = None
    if data:
        out_data = urllib.urlencode(data)
        out_headers.setdefault('Content-type', "application/x-www-form-urlencoded")

    conn = httplib.HTTPSConnection(GRAPH_API_HOST)

    out_path = "?".join((path, urllib.urlencode(args)))

    log.debug("%s %s" % (method, out_path))

    conn.request(method, out_path, out_data, out_headers)
    response = conn.getresponse()

    log.debug("Response: %r", (response.status, response.reason))

    if response.getheader('Content-type').startswith("text/javascript"):
        response_data = _decode_json(response.read())
    else:
        raise Exception(response.getheader('Content-type'))
        response_data = response.read()

    log.debug("Response Data: %r", response_data)

    if isinstance(response_data, dict) and response_data.get("error"):
        raise GraphAPIError(response_data["error"]["type"],
                            response_data["error"]["message"])

    if response.status != httplib.OK:
        raise CommunicationError((response.status, response.reason))

    if not response:
        raise GraphAPIError("No response")

    return response_data


def get_user_from_cookie(cookies, app_id, app_secret):
    """Parses the cookie set by the official Facebook JavaScript SDK.

    cookies should be a dictionary-like object mapping cookie names to
    cookie values.

    If the user is logged in via Facebook, we return a dictionary with the
    keys "uid" and "access_token". The former is the user's Facebook ID,
    and the latter can be used to make authenticated requests to the Graph API.
    If the user is not logged in, we return None.

    Download the official Facebook JavaScript SDK at
    http://github.com/facebook/connect-js/. Read more about Facebook
    authentication at http://developers.facebook.com/docs/authentication/.
    """
    cookie = cookies.get("fbs_" + app_id, "")
    if not cookie: return None
    args = dict((k, v[-1]) for k, v in cgi.parse_qs(cookie.strip('"')).items())
    payload = "".join(k + "=" + args[k] for k in sorted(args.keys())
                      if k != "sig")
    sig = hashlib.md5(payload + app_secret).hexdigest()
    expires = int(args["expires"])
    if sig == args.get("sig") and (expires == 0 or time.time() < expires):
        return args
    else:
        return None


def parse_signed_request(signed_request, app_secret):
    """Return dictionary with signed request data."""
    try:
        l = signed_request.split('.', 2)
        encoded_sig = str(l[0])
        payload = str(l[1])
    except IndexError:
        raise ValueError("'signed_request' malformed")

    sig = base64.urlsafe_b64decode(encoded_sig + "=" * ((4 - len(encoded_sig) % 4) % 4))
    data = base64.urlsafe_b64decode(payload + "=" * ((4 - len(payload) % 4) % 4))

    data = _decode_json(data)

    if data.get('algorithm').upper() != 'HMAC-SHA256':
        raise Error("'signed_request' is using an unknown algorithm")
    else:
        expected_sig = hmac.new(app_secret, msg=payload, digestmod=hashlib.sha256).digest()

    if sig != expected_sig:
        raise Error("'signed_request' signature mismatch")
    else:
        return data


def build_signed_request(user_id, oauth_token, app_secret):
    data = dict(
                algorithm='HMAC-SHA256',
                issued_at=int(time.time()),
                user=dict(locale='en_US', country='us')
                )

    if oauth_token is not None:
        data['oauth_token'] = oauth_token
        data['user_id'] = user_id
        
    payload = base64.urlsafe_b64encode(_encode_json(data))
    payload = payload.rstrip("=")

    sig = hmac.new(app_secret, msg=payload, digestmod=hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(sig)

    return ".".join((encoded_sig.rstrip("="), payload.rstrip("=")))