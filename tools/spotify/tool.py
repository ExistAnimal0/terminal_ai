import json, os, time, urllib.request, urllib.parse, urllib.error

CRED_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "spotify.json")
API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def _load_creds():
    with open(CRED_PATH) as f:
        return json.load(f)


def _save_creds(creds):
    with open(CRED_PATH, "w") as f:
        json.dump(creds, f, indent=2)


def _refresh_token(creds):
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        body = _parse(resp.read()) or {}
    creds["access_token"] = body.get("access_token", creds["access_token"])
    if body.get("refresh_token"):
        creds["refresh_token"] = body["refresh_token"]
    creds["expires_at"] = time.time() + body.get("expires_in", 3600)
    _save_creds(creds)
    return creds


def _get_token(creds):
    if creds.get("expires_at", 0) > time.time() + 30:
        return creds["access_token"]
    return _refresh_token(creds)["access_token"]


def _parse(raw):
    """Parse a response body: JSON if possible, else raw text, else None."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw.decode("utf-8", "replace")


def _api(method, path, token, body=None):
    """Return (status_code, parsed_body). Never raises on empty or non-JSON bodies."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, _parse(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, _parse(e.read())


def _ok(code):
    return 200 <= code < 300


def _active_device(token):
    code, body = _api("GET", "/me/player/devices", token)
    if not _ok(code) or not isinstance(body, dict):
        return None
    for d in body.get("devices", []):
        if d.get("is_active"):
            return d.get("id")
    devs = body.get("devices", [])
    return devs[0]["id"] if devs else None


def tool(action, **kwargs):
    creds = _load_creds()
    token = _get_token(creds)

    if action == "status":
        code, body = _api("GET", "/me/player", token)
        if code == 204 or not isinstance(body, dict):
            return "Nothing playing."
        if code == 202:
            return "No active device."
        if _ok(code):
            is_playing = bool(body.get("is_playing"))
            vol = (body.get("device") or {}).get("volume_percent", 0)
            item = body.get("item") or body.get("track") or {}
            name = item.get("name", "?")
            artist = (item.get("artists") or [{}])[0].get("name", "?")
            return f"{'Playing' if is_playing else 'Paused'}: {name} - {artist} (vol {vol}%)"
        return f"Error {code}: {body}"

    if action == "play":
        body = kwargs.get("body") or {"position_ms": 0}
        code, res = _api("PUT", "/me/player/play", token, body)
        return "OK" if _ok(code) else f"Error {code}: {res}"

    if action == "pause":
        dev = _active_device(token)
        body = {"device_ids": [dev]} if dev else None
        code, res = _api("PUT", "/me/player/pause", token, body)
        return "Paused." if _ok(code) else f"Error {code}: {res}"

    if action == "next":
        code, res = _api("POST", "/me/player/next", token)
        return "Skipped forward." if _ok(code) else f"Error {code}: {res}"

    if action == "previous":
        code, res = _api("POST", "/me/player/previous", token)
        return "Skipped back." if _ok(code) else f"Error {code}: {res}"

    if action == "volume":
        dev = _active_device(token)
        if not dev:
            return "No active device to set volume on."
        pct = int(kwargs.get("percent", 50))
        code, res = _api("PUT", "/me/player", token,
                        {"volume_percent": pct, "device_ids": [dev]})
        return f"Volume set to {pct}%." if _ok(code) else f"Error {code}: {res}"

    if action == "search":
        q = kwargs.get("query", "")
        code, body = _api("GET", f"/search?type=track&limit=5&q={urllib.parse.quote(q)}", token)
        if not _ok(code) or not isinstance(body, dict):
            return f"Error {code}: {body}"
        tracks = (body.get("tracks") or {}).get("items", [])
        if not tracks:
            return "No results."
        return "\n".join(
            f"{i+1}. {t['name']} - {t['artists'][0]['name']} [{t['id']}]"
            for i, t in enumerate(tracks)
        )

    if action == "play_id":
        tid = kwargs.get("id", "")
        code, res = _api("PUT", "/me/player/play", token,
                        {"uris": [f"spotify:track:{tid}"]})
        return "Playing." if _ok(code) else f"Error {code}: {res}"

    return f"Unknown action: {action}"
