import json, os, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
SHOWME_ROOT = ROOT.parent
TOPICS_PATH = SHOWME_ROOT / "topics.json"
CLAIMS_PATH = SHOWME_ROOT / "claims.json"
SUBMISSIONS_PATH = ROOT / "submissions.json"
RESULT_PATH = ROOT / "request-result.json"

def finish(success, message):
    RESULT_PATH.write_text(
        json.dumps({"success": success, "message": message}, indent=2),
        encoding="utf-8",
    )

def field(body, heading):
    pattern = rf"(?ims)^###\s+{re.escape(heading)}\s*\n+(.*?)(?=\n###\s+|\Z)"
    m = re.search(pattern, body)
    if not m:
        return ""
    value = m.group(1).strip()
    if value in {"_No response_", "No response"}:
        return ""
    return value

def clean_line(value, max_len):
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:max_len]

def active_custom(claims, user):
    return next(
        (
            v for v in claims.get("custom", [])
            if v.get("claimed_by") == user and v.get("active", True)
        ),
        None,
    )

def validate_http_url(url, kind):
    try:
        parsed = urlparse(url)
    except Exception:
        return False, f"The {kind} URL is not a valid URL."

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, f"The {kind} URL must begin with http:// or https://."

    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return False, f"The {kind} URL points to a local computer, not a public page."

    if kind == "exhibit" and (parsed.hostname or "").lower() == "github.com":
        return False, (
            "The exhibit URL is a github.com repository/file URL. "
            "Submit the actual public webpage URL instead (normally a github.io address)."
        )

    req = Request(url, headers={"User-Agent": "ECON238-SHOW-ME-Museum-Validator/1.0"})
    try:
        with urlopen(req, timeout=20) as response:
            status = getattr(response, "status", 200)
            content_type = (response.headers.get("Content-Type") or "").lower()
            final_url = response.geturl()
            response.read(2048)
    except HTTPError as exc:
        return False, f"The {kind} URL returned HTTP {exc.code}."
    except URLError as exc:
        return False, f"The {kind} URL could not be reached: {exc.reason}."
    except Exception as exc:
        return False, f"The {kind} URL could not be verified: {exc}."

    if status < 200 or status >= 400:
        return False, f"The {kind} URL returned HTTP {status}."

    if kind == "exhibit":
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return False, (
                "The exhibit URL loads, but it does not appear to be a public HTML webpage. "
                "Submit the exact webpage URL, not a PDF, repository, or download."
            )
    elif kind == "cover image":
        if content_type and not content_type.startswith("image/"):
            return False, (
                "The cover-image URL loads, but it does not appear to be an image. "
                "Use the public URL of a PNG, JPG, WEBP, GIF, or similar image."
            )

    return True, final_url

with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
    event = json.load(f)

issue = event["issue"]
user = event["sender"]["login"]
body = issue.get("body") or ""
issue_number = issue["number"]

exhibit_type = field(body, "Exhibit type")
topic_id = clean_line(field(body, "Class-list Topic ID"), 40).upper()
title = clean_line(field(body, "Exhibit title"), 140)
url = clean_line(field(body, "Exact public exhibit URL"), 500)
cover_url = clean_line(field(body, "Cover-image URL"), 500)
hook = clean_line(field(body, "One-sentence hook"), 320)

if exhibit_type.startswith("CLASS LIST"):
    slot = "LIST"
elif exhibit_type.startswith("MY OWN"):
    slot = "OWN"
else:
    finish(False, "I could not determine whether this is your CLASS LIST or MY OWN exhibit.")
    raise SystemExit

if not title:
    finish(False, "Missing **Exhibit title**. Submit a new Museum form with a title.")
    raise SystemExit
if not url:
    finish(False, "Missing **Exact public exhibit URL**.")
    raise SystemExit
if not cover_url:
    finish(False, "Missing **Cover-image URL**.")
    raise SystemExit
if not hook:
    finish(False, "Missing **One-sentence hook**.")
    raise SystemExit

topics = {t["id"]: t for t in json.loads(TOPICS_PATH.read_text(encoding="utf-8"))}
claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
museum = json.loads(SUBMISSIONS_PATH.read_text(encoding="utf-8"))
museum.setdefault("students", {})

if slot == "LIST":
    if not topic_id:
        finish(False, "Your class-list exhibit must include its Topic ID, such as **CLIM-03**.")
        raise SystemExit
    if topic_id not in topics:
        finish(False, f"**{topic_id}** is not a SHOW ME class-list Topic ID.")
        raise SystemExit
    claim = claims.get("claims", {}).get(topic_id)
    if not claim or claim.get("claimed_by") != user:
        finish(
            False,
            f"**{topic_id}** is not currently reserved to **@{user}**. "
            "Claim your class-list topic first, then submit it to the Museum.",
        )
        raise SystemExit
    category = topics[topic_id]["category"]
else:
    custom = active_custom(claims, user)
    if not custom:
        finish(
            False,
            "I cannot find an active **Create a Topic on My Own** reservation for your GitHub account. "
            "Create/reserve your own topic first, then submit the exhibit.",
        )
        raise SystemExit
    topic_id = custom["id"]
    category = "Student-Created"

ok, checked_url = validate_http_url(url, "exhibit")
if not ok:
    finish(False, checked_url)
    raise SystemExit

ok, checked_cover = validate_http_url(cover_url, "cover image")
if not ok:
    finish(False, checked_cover)
    raise SystemExit

entry = {
    "github_user": user,
    "slot": slot,
    "topic_id": topic_id,
    "category": category,
    "title": title,
    "url": checked_url,
    "cover_url": checked_cover,
    "hook": hook,
    "submitted_at": datetime.now(timezone.utc).isoformat(),
    "issue_number": issue_number,
}

student = museum["students"].setdefault(user, {})
replaced = slot in student
student[slot] = entry
SUBMISSIONS_PATH.write_text(
    json.dumps(museum, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

action = "UPDATED" if replaced else "ADDED"
kind = "class-list" if slot == "LIST" else "student-created"
finish(
    True,
    f"**MUSEUM {action}:** Your {kind} exhibit **{title}** passed the public-page checks "
    "and has been accepted. The Museum page may take a minute or two to republish. "
    "This issue is your submission receipt.",
)
