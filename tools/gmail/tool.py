"""Gmail tool - list, read, send, download."""
import base64, os, mimetypes
from email import encoders
from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
API_NAME, API_VERSION = "gmail", "v1"


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
    """Return an authorized Gmail service. First run opens browser for OAuth."""
    env = _load_env()
    client_id = env.get("GMAIL_CLIENT_ID", "")
    client_secret = env.get("GMAIL_CLIENT_SECRET", "")
    creds = None
    if os.path.exists(TOKEN_FILE):
        import json
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
            # Build client config from .env (no client_secret.json needed)
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


def _b64decode(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _walk_parts(payload):
    """Yield every part in the payload, recursing through nested multipart."""
    for p in payload.get("parts", []):
        yield p
        yield from _walk_parts(p)


def _list(g, query="is:unread", max_results=20):
    res = g.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    out = []
    for m in res.get("messages", []):
        full = g.users().messages().get(userId="me", id=m["id"],
                                       format="metadata").execute()
        hdrs = full.get("payload", {}).get("headers", [])
        subj = next((h["value"] for h in hdrs
                     if h["name"] == "Subject"), "(no subject)")
        sender = next((h["value"] for h in hdrs
                       if h["name"] == "From"), "?")
        date = next((h["value"] for h in hdrs
                     if h["name"] == "Date"), "?")
        out.append(f"{full['threadId']} | {date} | {sender} | {subj}")
    return "\n".join(out) or "(no messages)"


def _read(g, message_id):
    full = g.users().messages().get(userId="me", id=message_id,
                                   format="full").execute()
    g.users().messages().modify(userId="me", id=message_id,
        body={"removeLabelIds": ["UNREAD"]}).execute()
    parts = []
    for h in full.get("payload", {}).get("headers", []):
        if h["name"] in ("Subject", "From", "To", "Date"):
            parts.append(f"{h['name']}: {h['value']}")
    # body: top-level payload first, else first text part anywhere in the tree
    body = full["payload"].get("body", {}).get("data", "")
    if not body:
        for p in _walk_parts(full["payload"]):
            if p.get("mimeType", "").startswith("text/"):
                d = p.get("body", {}).get("data", "")
                if d:
                    body = d
                    break
    if body:
        parts.append(f"\n--- BODY ---\n{_b64decode(body).decode(errors='replace')}")
    # attachments: any part with a filename, anywhere in the tree
    atts = [p["filename"] for p in _walk_parts(full["payload"]) if p.get("filename")]
    if atts:
        parts.append(f"\nAttachments: {', '.join(atts)}")
    return "\n".join(parts)


def _send(g, to, subject, body, attachments=""):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase

    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    for path in [a.strip() for a in attachments.split(",") if a.strip()]:
        p = Path(path)
        if not p.exists():
            return f"ERROR: attachment not found: {path}"
        mime, _ = mimetypes.guess_type(p.name)
        maintype, subtype = (mime or "application/octet-stream").split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={p.name}")
        msg.attach(part)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    res = g.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Sent. Message ID: {res['id']}"


def _download(g, message_id, save_dir="downloads"):
    full = g.users().messages().get(userId="me", id=message_id,
                                   format="full").execute()
    g.users().messages().modify(userId="me", id=message_id,
        body={"removeLabelIds": ["UNREAD"]}).execute()
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    saved = []
    for p in _walk_parts(full["payload"]):
        if not p.get("filename"):
            continue
        aid = p.get("body", {}).get("attachmentId")
        if aid:
            att = g.users().messages().attachments().get(
                userId="me", messageId=message_id, id=aid
            ).execute()
            data = _b64decode(att["data"])
        else:
            # inline image (cid-embedded): data is in the part body
            d = p.get("body", {}).get("data", "")
            if not d:
                continue
            data = _b64decode(d)
        dest = Path(save_dir) / p["filename"]
        dest.write_bytes(data)
        saved.append(str(dest))
    return "\n".join(f"Saved: {s}" for s in saved) or "(no attachments)"


def tool(action, query="is:unread", message_id="", to="", subject="",
         body="", attachments="", save_dir="downloads"):
    g = _get_service()
    if action == "list":
        return _list(g, query)
    if action == "read":
        return _read(g, message_id)
    if action == "send":
        return _send(g, to, subject, body, attachments)
    if action == "download":
        return _download(g, message_id, save_dir)
    return f"Unknown action: {action}"
