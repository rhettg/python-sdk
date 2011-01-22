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
"""
Python client library for the Facebook Platform.

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

class Error(Exception): 
    """Generic client library error"""
    pass

class CommunicationError(Error): 
    pass


GRAPH_API_HOST = "graph.facebook.com"
USER_AGENT = "Facebook Python API Client 1.0"

from facebook.graph_api import GraphAPI
from facebook.auth import get_user_from_cookie
from facebook.auth import get_oauth_access_token
from facebook.auth import parse_signed_request

__all__ = ["GraphAPI"]
