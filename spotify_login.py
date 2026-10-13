"""Spotify login - run this once to get tokens.

Usage:  python spotify_login.py

Reads client_id / client_secret / redirect_uri from .env,
opens the authorize URL in your browser, you click Agree,
then paste the redirect URL back. Tokens are saved to spotify.json.
"""
import json
import os
import time
import urllib.parse
import urllib.request
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE, ".env")
CRED_PATH = os.path.join(BASE, "spotify.json")
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = ("streaming user-modify-playback-state user-read-playback-state "
          "user-read-currently-playing user-read-private")


def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def main():
    env = load_env()
    client_id = env.get("SPOTIFY_CLIENT_ID", "")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri = env.get("SPOTIFY_REDIRECT_URI", "https://spotify.com")

    if not client_id or not client_secret:
        print("Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET in .env")
        print()
        print("To get them:")
        print("  1. Go to https://developer.spotify.com/dashboard")
        print("  2. Log in with your Spotify account")
        print("  3. Click 'Create App', give it a name, accept the terms")
        print("  4. On the app page, copy the Client ID and Client Secret")
        print("  5. Add a Redirect URI: https://spotify.com")
        print("  6. Paste both values into your .env file")
        print()
        print("Then run this script again.")
        return

    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&scope={urllib.parse.quote(SCOPES)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
    )

    print("Opening Spotify in your browser...")
    webbrowser.open(auth_url)
    print()
    print("Click 'Agree' in the browser.")
    print("You'll land on an error page - that's normal.")
    print("Copy the FULL URL from the address bar and paste it below.")
    print()

    try:
        redirect_url = input("Paste the redirect URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.")
        return

    if not redirect_url:
        print("Nothing pasted. Cancelled.")
        return

    params = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)
    code = params.get("code", [None])[0]
    error = params.get("error", [None])[0]

    if error:
        print(f"Spotify returned an error: {error}")
        return
    if not code:
        print("Couldn't find a 'code' in that URL.")
        print("Make sure you copied the full URL from the address bar.")
        return

    print("Exchanging code for tokens...")
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())

    creds = {
        "access_token": body.get("access_token", ""),
        "refresh_token": body.get("refresh_token", ""),
        "expires_in": body.get("expires_in", 3600),
        "expires_at": time.time() + body.get("expires_in", 3600),
        "scopes": SCOPES,
    }
    with open(CRED_PATH, "w") as f:
        json.dump(creds, f, indent=2)

    print(f"Done. Tokens saved to {CRED_PATH}")
    print(f"Access token expires in {creds['expires_in']} seconds.")


if __name__ == "__main__":
    main()
