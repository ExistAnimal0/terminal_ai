"""Google Calendar tool - list, read, create, update, delete, search events."""
import json, os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
API_NAME, API_VERSION = "calendar", "v3"


def _load_env():
    """Parse .env file into a dict."""
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def _get_service():
    """Return an authorized Calendar service. First run opens browser for OAuth."""
    env = _load_env()
    # Reuse Gmail's OAuth client (same Google Cloud project)
    client_id = env.get("GMAIL_CLIENT_ID", "")
    client_secret = env.get("GMAIL_CLIENT_SECRET", "")
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            td = json.load(f)
        creds = Credentials(
            token=td.get("token"),
            refresh_token=td.get("refresh_token"),
            token_uri=td.get("token_uri"),
            client_id=td.get("client_id") or client_id,
            client_secret=td.get("client_secret") or client_secret,
        )
    if creds is None or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build(API_NAME, API_VERSION, credentials=creds)


def _fmt_event(e):
    """Format an event dict into a readable one-liner."""
    start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
    end = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", "")
    loc = e.get("location", "")
    desc = (e.get("description") or "").strip()
    parts = [f"{e['id']} | {e.get('summary', '(no title)')}"]
    if start:
        parts.append(f"start: {start}")
    if end:
        parts.append(f"end: {end}")
    if loc:
        parts.append(f"loc: {loc}")
    if desc:
        parts.append(f"desc: {desc[:120]}")
    return " | ".join(parts)


def _list(g, calendar_id="primary", time_min="", time_max="", max_results=20):
    params = {"calendarId": calendar_id, "maxResults": max_results,
              "singleEvents": True}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    res = g.events().list(**params).execute()
    events = res.get("items", [])
    if not events:
        return "(no events)"
    lines = [_fmt_event(e) for e in events]
    lines.insert(0, f"{len(events)} event(s):")
    return "\n".join(lines)


def _read(g, calendar_id, event_id):
    res = g.events().get(calendarId=calendar_id, eventId=event_id).execute()
    lines = [
        f"ID: {res['id']}",
        f"Title: {res.get('summary', '(none)')}",
        f"Start: {res.get('start', {}).get('dateTime') or res.get('start', {}).get('date', '')}",
        f"End: {res.get('end', {}).get('dateTime') or res.get('end', {}).get('date', '')}",
    ]
    if res.get("description"):
        lines.append(f"Description: {res['description']}")
    if res.get("location"):
        lines.append(f"Location: {res['location']}")
    atts = [a.get("email", "") for a in res.get("attendees", [])]
    if atts:
        lines.append(f"Attendees: {', '.join(atts)}")
    return "\n".join(lines)


def _create(g, calendar_id, title, start, end, description="", location="", attendees=""):
    body = {
        "summary": title,
        "start": {"dateTime": start} if "T" in start else {"date": start},
        "end": {"dateTime": end} if "T" in end else {"date": end},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [
            {"email": a.strip()} for a in attendees.split(",") if a.strip()
        ]
    res = g.events().insert(calendarId=calendar_id, body=body,
                           sendNotifications=True).execute()
    return f"Created event {res['id']}: {res.get('htmlLink', '')}"


def _update(g, calendar_id, event_id, title="", start="", end="",
            description="", location="", attendees=""):
    res = g.events().get(calendarId=calendar_id, eventId=event_id).execute()
    if title:
        res["summary"] = title
    if start:
        res["start"] = {"dateTime": start} if "T" in start else {"date": start}
    if end:
        res["end"] = {"dateTime": end} if "T" in end else {"date": end}
    if description:
        res["description"] = description
    if location:
        res["location"] = location
    if attendees:
        res["attendees"] = [
            {"email": a.strip()} for a in attendees.split(",") if a.strip()
        ]
    updated = g.events().update(calendarId=calendar_id, eventId=event_id,
                                body=res, sendNotifications=True).execute()
    return f"Updated event {updated['id']}: {updated.get('htmlLink', '')}"


def _delete(g, calendar_id, event_id):
    g.events().delete(calendarId=calendar_id, eventId=event_id,
                     sendNotifications=True).execute()
    return f"Deleted event {event_id}"


def _search(g, calendar_id, query, max_results=20):
    res = g.events().list(calendarId=calendar_id, q=query,
                         maxResults=max_results, singleEvents=True).execute()
    events = res.get("items", [])
    if not events:
        return f"(no events matching '{query}')"
    lines = [f"{len(events)} result(s) for '{query}':"]
    lines.extend(_fmt_event(e) for e in events)
    return "\n".join(lines)


def tool(action, calendar_id="primary", event_id="", query="",
         time_min="", time_max="", title="", start="", end="",
         description="", location="", attendees="", max_results=20):
    g = _get_service()
    if action == "list":
        return _list(g, calendar_id, time_min, time_max, max_results)
    if action == "read":
        if not event_id:
            return "ERROR: event_id required"
        return _read(g, calendar_id, event_id)
    if action == "create":
        if not title or not start:
            return "ERROR: title and start required"
        if not end:
            end = start
        return _create(g, calendar_id, title, start, end,
                       description, location, attendees)
    if action == "update":
        if not event_id:
            return "ERROR: event_id required"
        return _update(g, calendar_id, event_id, title, start, end,
                       description, location, attendees)
    if action == "delete":
        if not event_id:
            return "ERROR: event_id required"
        return _delete(g, calendar_id, event_id)
    if action == "search":
        if not query:
            return "ERROR: query required"
        return _search(g, calendar_id, query, max_results)
    return f"Unknown action: {action}"
