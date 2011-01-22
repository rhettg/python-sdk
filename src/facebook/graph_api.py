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

"""Core graph API

Instances of GraphAPI provide a view into the facebook graph with the provided access token.
"""

import httplib
import logging
import time
import urllib

import facebook

class GraphAPIError(facebook.Error):
    def __init__(self, type, message):
        Exception.__init__(self, message)
        self.type = type


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
    """
    def __init__(self, access_token=None):
        """Create an instance of GraphAPI bound to the specified access token
        
        If an access token isn't provided, the graph api will only be able to access public information.
        """
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
        """Fetch a connection for the specifeid object.
        
        There are various optional argument that can be used to prune down the results.
        
        Args:
          id: Identifier for the object to fetch a connection from
          connection_name: Name of the connection: Ex: 'friends'
          limit: (optional) maximum connected objects to retrieve
          offset: (optional) return objects great than the offset specified (useful for paging)
          until: (optional) datetime instance that represents how old an object must be
          since: (optional) datetime instance that reprsents how new an object must be
        
        Returns:
          Dictionary result set. Typically with a key 'data' that contains a list of connected objects.
        """
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


def graph_api_request(method, path, args=None, data=None, access_token=None, headers=None):
    out_headers = {
        'User-Agent': facebook.USER_AGENT,
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

    conn = httplib.HTTPSConnection(facebook.GRAPH_API_HOST)

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
        raise facebook.CommunicationError((response.status, response.reason))

    if not response:
        raise GraphAPIError("No response")

    return response_data
