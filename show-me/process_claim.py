import json, os, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOPICS_PATH = ROOT / "topics.json"
CLAIMS_PATH = ROOT / "claims.json"
RESULT_PATH = ROOT / "request-result.json"

def finish(success, message):
    RESULT_PATH.write_text(json.dumps({"success": success, "message": message}, indent=2), encoding="utf-8")

def active_count(claims, user):
    n = sum(1 for v in claims.get("claims", {}).values() if v.get("claimed_by") == user)
    n += sum(1 for v in claims.get("custom", []) if v.get("claimed_by") == user and v.get("active", True))
    return n

def own_custom(claims, user):
    return next((v for v in claims.get("custom", []) if v.get("claimed_by") == user and v.get("active", True)), None)

with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
    event = json.load(f)

issue = event["issue"]
user = event["sender"]["login"]
title = (issue.get("title") or "").strip()
body = issue.get("body") or ""

topics = {t["id"]: t for t in json.loads(TOPICS_PATH.read_text(encoding="utf-8"))}
claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
claims.setdefault("claims", {})
claims.setdefault("custom", [])
now = datetime.now(timezone.utc).isoformat()

m = re.fullmatch(r"CLAIM\s+([A-Z]+-\d+)", title, re.I)
if m:
    tid = m.group(1).upper()
    if tid not in topics:
        finish(False, f"I could not find **{tid}** in the SHOW ME topic list.")
    elif tid in claims["claims"]:
        owner = claims["claims"][tid]["claimed_by"]
        finish(False, f"**{tid}** has already been claimed by **@{owner}**. Choose another available investigation.")
    elif active_count(claims, user) >= 2:
        finish(False, "You already have two active SHOW ME investigations. Release one before claiming another.")
    else:
        claims["claims"][tid] = {"claimed_by": user, "claimed_at": now}
        CLAIMS_PATH.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        finish(True, f"**CLAIM CONFIRMED:** {tid} — {topics[tid]['title']} is reserved for **@{user}**. Save this issue as your receipt.")
else:
    m = re.fullmatch(r"RELEASE\s+([A-Z]+-\d+)", title, re.I)
    if m:
        tid = m.group(1).upper()
        current = claims["claims"].get(tid)
        if not current:
            finish(False, f"**{tid}** is not currently claimed.")
        elif current.get("claimed_by") != user:
            finish(False, f"Only **@{current.get('claimed_by')}** can release **{tid}**.")
        else:
            del claims["claims"][tid]
            CLAIMS_PATH.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            finish(True, f"**{tid}** has been released and is available again.")
    elif title.upper() == "CUSTOM SHOW ME":
        if active_count(claims, user) >= 2:
            finish(False, "You already have two active SHOW ME investigations. Release one before creating a custom topic.")
        elif own_custom(claims, user):
            finish(False, "You already used your one **Create a Topic on My Own** slot.")
        else:
            tm = re.search(r"(?im)^\s*Topic title:\s*(.+?)\s*$", body)
            dm = re.search(r"(?ims)^\s*What I plan to show:\s*(.+?)(?:\n\s*\n|\Z)", body)
            custom_title = tm.group(1).strip() if tm else ""
            description = dm.group(1).strip() if dm else ""
            if not custom_title or not description:
                finish(False, "For a custom investigation, fill in both **Topic title:** and **What I plan to show:**, then submit a new request.")
            else:
                cid = f"CUSTOM-{user}"
                claims["custom"].append({
                    "id": cid,
                    "claimed_by": user,
                    "title": custom_title,
                    "description": description,
                    "claimed_at": now,
                    "active": True
                })
                CLAIMS_PATH.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                finish(True, f"**CUSTOM TOPIC CONFIRMED:** {custom_title} is reserved for **@{user}** and counts as one of your two SHOW ME investigations.")
    elif title.upper() == "RELEASE CUSTOM":
        item = own_custom(claims, user)
        if not item:
            finish(False, "You do not currently have an active custom SHOW ME investigation.")
        else:
            item["active"] = False
            CLAIMS_PATH.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            finish(True, "Your custom SHOW ME investigation has been released. You may now create a different custom topic.")
    else:
        finish(False, "This issue was not recognized as a SHOW ME reservation request.")
