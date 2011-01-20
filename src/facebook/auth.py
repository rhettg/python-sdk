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