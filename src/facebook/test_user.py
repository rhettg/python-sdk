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
