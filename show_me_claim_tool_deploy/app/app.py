import csv
import io
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("SHOWME_DB_PATH", DATA_DIR / "showme.db"))
TOPICS_PATH = Path(os.getenv("SHOWME_TOPICS_PATH", BASE_DIR / "topics.json"))

app = Flask(__name__)
app.secret_key = os.getenv("SHOWME_SECRET_KEY", "dev-only-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

CLASS_CODE = os.getenv("SHOWME_CLASS_CODE", "show-me-2026")
ADMIN_KEY = os.getenv("SHOWME_ADMIN_KEY", "change-me")
DISPLAY_FULL_NAMES = os.getenv("SHOWME_DISPLAY_FULL_NAMES", "1") == "1"


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init_db():
    con = db_connect()
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                section TEXT,
                manage_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id TEXT,
                student_id INTEGER NOT NULL,
                custom_title TEXT,
                custom_plan TEXT,
                receipt TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                released_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                FOREIGN KEY(topic_id) REFERENCES topics(id),
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_standard_claim
            ON claims(topic_id)
            WHERE status = 'active' AND topic_id IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_claims_student
            ON claims(student_id, status);
            """
        )
        con.commit()
    finally:
        con.close()
    sync_topics()


def sync_topics():
    with open(TOPICS_PATH, "r", encoding="utf-8") as f:
        topics = json.load(f)
    con = db_connect()
    try:
        with con:
            for i, t in enumerate(topics, start=1):
                con.execute(
                    """
                    INSERT INTO topics(id, category, title, prompt, sort_order, active)
                    VALUES(?,?,?,?,?,1)
                    ON CONFLICT(id) DO UPDATE SET
                        category=excluded.category,
                        title=excluded.title,
                        prompt=excluded.prompt,
                        sort_order=excluded.sort_order,
                        active=1
                    """,
                    (t["id"], t["category"], t["title"], t["prompt"], i),
                )
    finally:
        con.close()


def normalized_email(value):
    return (value or "").strip().lower()


def validate_email(email):
    return "@" in email and "." in email.split("@", 1)[1]


def display_name(name):
    if DISPLAY_FULL_NAMES:
        return name
    parts = [p for p in name.strip().split() if p]
    if len(parts) <= 1:
        return name
    return f"{parts[0]} {parts[-1][0]}."


def student_claim_state(con, student_id):
    rows = con.execute(
        "SELECT * FROM claims WHERE student_id=? AND status='active' ORDER BY created_at",
        (student_id,),
    ).fetchall()
    custom_count = sum(1 for r in rows if r["topic_id"] is None)
    return rows, custom_count


def get_or_create_student(con, name, email, section):
    row = con.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
    if row:
        con.execute(
            "UPDATE students SET name=?, section=? WHERE id=?",
            (name, section, row["id"]),
        )
        return con.execute("SELECT * FROM students WHERE id=?", (row["id"],)).fetchone()

    token = secrets.token_urlsafe(24)
    con.execute(
        "INSERT INTO students(name,email,section,manage_token,created_at) VALUES(?,?,?,?,?)",
        (name, email, section, token, utcnow()),
    )
    return con.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()


def new_receipt(prefix="SM"):
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def class_code_ok(value):
    return secrets.compare_digest((value or "").strip(), CLASS_CODE)


def admin_ok():
    supplied = session.get("admin_key") or request.args.get("key") or request.form.get("key")
    return bool(supplied) and secrets.compare_digest(str(supplied), ADMIN_KEY)


@app.context_processor
def inject_helpers():
    return {"display_name": display_name}


@app.get("/")
def index():
    con = db_connect()
    try:
        topics = con.execute(
            """
            SELECT t.*,
                   c.id AS claim_id,
                   s.name AS claimant_name,
                   c.created_at AS claimed_at
            FROM topics t
            LEFT JOIN claims c ON c.topic_id=t.id AND c.status='active'
            LEFT JOIN students s ON s.id=c.student_id
            WHERE t.active=1
            ORDER BY t.sort_order
            """
        ).fetchall()
        stats = con.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM topics WHERE active=1) AS total_topics,
              (SELECT COUNT(*) FROM claims WHERE status='active' AND topic_id IS NOT NULL) AS standard_claimed,
              (SELECT COUNT(*) FROM claims WHERE status='active' AND topic_id IS NULL) AS custom_claimed,
              (SELECT COUNT(DISTINCT student_id) FROM claims WHERE status='active') AS students_started
            """
        ).fetchone()
        categories = [r[0] for r in con.execute(
            "SELECT DISTINCT category FROM topics WHERE active=1 ORDER BY category"
        ).fetchall()]
    finally:
        con.close()
    return render_template("index.html", topics=topics, stats=stats, categories=categories)


@app.route("/claim/<topic_id>", methods=["GET", "POST"])
def claim_topic(topic_id):
    con = db_connect()
    topic = con.execute("SELECT * FROM topics WHERE id=? AND active=1", (topic_id,)).fetchone()
    if not topic:
        con.close()
        abort(404)

    existing = con.execute(
        """
        SELECT c.*, s.name AS claimant_name
        FROM claims c JOIN students s ON s.id=c.student_id
        WHERE c.topic_id=? AND c.status='active'
        """,
        (topic_id,),
    ).fetchone()

    if request.method == "GET":
        con.close()
        return render_template("claim.html", topic=topic, existing=existing, custom=False)

    name = (request.form.get("name") or "").strip()
    email = normalized_email(request.form.get("email"))
    section = (request.form.get("section") or "").strip()
    code = request.form.get("class_code")

    if not class_code_ok(code):
        con.close()
        flash("The class code is not correct.", "error")
        return redirect(url_for("claim_topic", topic_id=topic_id))
    if not name or not validate_email(email):
        con.close()
        flash("Enter your name and a valid email address.", "error")
        return redirect(url_for("claim_topic", topic_id=topic_id))

    try:
        con.execute("BEGIN IMMEDIATE")
        if con.execute(
            "SELECT 1 FROM claims WHERE topic_id=? AND status='active'", (topic_id,)
        ).fetchone():
            con.rollback()
            flash("Someone else claimed this SHOW ME first. Choose another available topic.", "error")
            return redirect(url_for("index"))

        student = get_or_create_student(con, name, email, section)
        active_claims, _ = student_claim_state(con, student["id"])
        if len(active_claims) >= 2:
            con.rollback()
            flash("You already have two active SHOW ME reservations.", "error")
            return redirect(url_for("manage", token=student["manage_token"]))

        receipt = new_receipt(topic_id)
        con.execute(
            """
            INSERT INTO claims(topic_id,student_id,receipt,created_at,status)
            VALUES(?,?,?,?, 'active')
            """,
            (topic_id, student["id"], receipt, utcnow()),
        )
        con.commit()
        return redirect(url_for("receipt", token=student["manage_token"], receipt=receipt))
    except sqlite3.IntegrityError:
        con.rollback()
        flash("Someone else claimed this SHOW ME first. Choose another available topic.", "error")
        return redirect(url_for("index"))
    finally:
        con.close()


@app.route("/custom", methods=["GET", "POST"])
def custom_topic():
    if request.method == "GET":
        return render_template("claim.html", topic=None, existing=None, custom=True)

    name = (request.form.get("name") or "").strip()
    email = normalized_email(request.form.get("email"))
    section = (request.form.get("section") or "").strip()
    code = request.form.get("class_code")
    custom_title = (request.form.get("custom_title") or "").strip()
    custom_plan = (request.form.get("custom_plan") or "").strip()

    if not class_code_ok(code):
        flash("The class code is not correct.", "error")
        return redirect(url_for("custom_topic"))
    if not name or not validate_email(email):
        flash("Enter your name and a valid email address.", "error")
        return redirect(url_for("custom_topic"))
    if len(custom_title) < 12 or len(custom_plan) < 25:
        flash("Give your SHOW ME a clear question and briefly say what you plan to change, compare, or construct.", "error")
        return redirect(url_for("custom_topic"))

    con = db_connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        student = get_or_create_student(con, name, email, section)
        active_claims, custom_count = student_claim_state(con, student["id"])
        if len(active_claims) >= 2:
            con.rollback()
            flash("You already have two active SHOW ME reservations.", "error")
            return redirect(url_for("manage", token=student["manage_token"]))
        if custom_count >= 1:
            con.rollback()
            flash("Create a Topic on My Own can be used for only one of your two investigations.", "error")
            return redirect(url_for("manage", token=student["manage_token"]))

        receipt = new_receipt("CUSTOM")
        con.execute(
            """
            INSERT INTO claims(topic_id,student_id,custom_title,custom_plan,receipt,created_at,status)
            VALUES(NULL,?,?,?,?,?, 'active')
            """,
            (student["id"], custom_title, custom_plan, receipt, utcnow()),
        )
        con.commit()
        return redirect(url_for("receipt", token=student["manage_token"], receipt=receipt))
    finally:
        con.close()


@app.get("/receipt/<token>/<receipt>")
def receipt(token, receipt):
    con = db_connect()
    try:
        student = con.execute("SELECT * FROM students WHERE manage_token=?", (token,)).fetchone()
        if not student:
            abort(404)
        claim = con.execute(
            """
            SELECT c.*, t.title AS topic_title, t.prompt AS topic_prompt, t.category
            FROM claims c LEFT JOIN topics t ON t.id=c.topic_id
            WHERE c.receipt=? AND c.student_id=?
            """,
            (receipt, student["id"]),
        ).fetchone()
        if not claim:
            abort(404)
        return render_template("receipt.html", student=student, claim=claim)
    finally:
        con.close()


@app.route("/manage/<token>", methods=["GET", "POST"])
def manage(token):
    con = db_connect()
    student = con.execute("SELECT * FROM students WHERE manage_token=?", (token,)).fetchone()
    if not student:
        con.close()
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")
        claim_id = request.form.get("claim_id")
        claim = con.execute(
            "SELECT * FROM claims WHERE id=? AND student_id=? AND status='active'",
            (claim_id, student["id"]),
        ).fetchone()
        if not claim:
            con.close()
            flash("That reservation is no longer active.", "error")
            return redirect(url_for("manage", token=token))

        if action == "release":
            with con:
                con.execute(
                    "UPDATE claims SET status='released', released_at=? WHERE id=?",
                    (utcnow(), claim["id"]),
                )
            con.close()
            flash("Reservation released. A standard topic is now available to the class again.", "success")
            return redirect(url_for("manage", token=token))

        if action == "edit_custom" and claim["topic_id"] is None:
            title = (request.form.get("custom_title") or "").strip()
            plan = (request.form.get("custom_plan") or "").strip()
            if len(title) < 12 or len(plan) < 25:
                con.close()
                flash("Keep a clear question and a brief plan for what you will change, compare, or construct.", "error")
                return redirect(url_for("manage", token=token))
            with con:
                con.execute(
                    "UPDATE claims SET custom_title=?, custom_plan=? WHERE id=?",
                    (title, plan, claim["id"]),
                )
            con.close()
            flash("Custom SHOW ME updated.", "success")
            return redirect(url_for("manage", token=token))

    claims = con.execute(
        """
        SELECT c.*, t.title AS topic_title, t.prompt AS topic_prompt, t.category
        FROM claims c LEFT JOIN topics t ON t.id=c.topic_id
        WHERE c.student_id=? AND c.status='active'
        ORDER BY c.created_at
        """,
        (student["id"],),
    ).fetchall()
    con.close()
    return render_template("manage.html", student=student, claims=claims)


@app.get("/faq")
def faq():
    return render_template("faq.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        key = request.form.get("key") or ""
        if secrets.compare_digest(key, ADMIN_KEY):
            session["admin_key"] = key
            return redirect(url_for("admin"))
        flash("Incorrect admin key.", "error")
    return render_template("admin_login.html")


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not admin_ok():
        return redirect(url_for("admin_login"))
    if request.args.get("key"):
        session["admin_key"] = request.args.get("key")

    con = db_connect()
    if request.method == "POST":
        claim_id = request.form.get("claim_id")
        action = request.form.get("action")
        if action == "release":
            with con:
                con.execute(
                    "UPDATE claims SET status='released', released_at=? WHERE id=? AND status='active'",
                    (utcnow(), claim_id),
                )
            flash("Claim released.", "success")
            con.close()
            return redirect(url_for("admin"))

    claims = con.execute(
        """
        SELECT c.*, s.name, s.email, s.section, s.manage_token,
               t.title AS topic_title, t.category
        FROM claims c
        JOIN students s ON s.id=c.student_id
        LEFT JOIN topics t ON t.id=c.topic_id
        WHERE c.status='active'
        ORDER BY s.name, c.created_at
        """
    ).fetchall()
    topics = con.execute(
        """
        SELECT t.*, c.id AS claim_id, s.name AS claimant_name
        FROM topics t
        LEFT JOIN claims c ON c.topic_id=t.id AND c.status='active'
        LEFT JOIN students s ON s.id=c.student_id
        WHERE t.active=1
        ORDER BY t.sort_order
        """
    ).fetchall()
    con.close()
    return render_template("admin.html", claims=claims, topics=topics)


@app.get("/admin/export.csv")
def admin_export():
    if not admin_ok():
        return redirect(url_for("admin_login"))
    con = db_connect()
    rows = con.execute(
        """
        SELECT s.name, s.email, s.section,
               COALESCE(c.topic_id, 'CUSTOM') AS topic_id,
               COALESCE(t.title, c.custom_title) AS title,
               c.custom_plan, c.receipt, c.created_at, c.status
        FROM claims c
        JOIN students s ON s.id=c.student_id
        LEFT JOIN topics t ON t.id=c.topic_id
        ORDER BY s.name, c.created_at
        """
    ).fetchall()
    con.close()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["name", "email", "section", "topic_id", "title", "custom_plan", "receipt", "created_at", "status"])
    for r in rows:
        writer.writerow(list(r))
    data = io.BytesIO(out.getvalue().encode("utf-8"))
    return send_file(data, mimetype="text/csv", as_attachment=True, download_name="show_me_claims.csv")


@app.post("/admin/logout")
def admin_logout():
    session.pop("admin_key", None)
    return redirect(url_for("index"))


@app.get("/health")
def health():
    return {"ok": True}


init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
