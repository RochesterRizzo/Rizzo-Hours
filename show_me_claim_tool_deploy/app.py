import csv, io, os, secrets, sqlite3
from datetime import datetime, timezone
from flask import Flask, abort, redirect, render_template_string, request, session, url_for, Response

app = Flask(__name__)
app.secret_key = os.environ.get("SHOWME_SECRET_KEY") or secrets.token_hex(32)
DB = os.environ.get("SHOWME_DB_PATH", "/data/showme.db")
CLASS_CODE = os.environ.get("SHOWME_CLASS_CODE", "ECO238SHOWME")
ADMIN_KEY = os.environ.get("SHOWME_ADMIN_KEY", "")
FULL = os.environ.get("SHOWME_DISPLAY_FULL_NAMES", "1") == "1"

RAW = """CLIM-01|Climate & Models|U.S. Net Zero, Everything Else Unchanged
CLIM-02|Climate & Models|Who Actually Moves Global Temperature?
CLIM-03|Climate & Models|Climate Sensitivity Surgery
CLIM-04|Climate & Models|Where Does ECS Actually Come From?
CLIM-05|Climate & Models|Cloud Feedback and the Upper Tail
CLIM-06|Climate & Models|Aerosol Masking
CLIM-07|Climate & Models|The Carbon-Budget Machine
CLIM-08|Climate & Models|What Does One Billion Tons of CO2 Do?
CLIM-09|Climate & Models|How Much Does the Terminal Year Matter?
CLIM-10|Climate & Models|Climate Damages Without Percentage Fog
CLIM-11|Climate & Models|Growth Versus Climate Damages
CLIM-12|Climate & Models|Discount-Rate Surgery on the SCC
CLIM-13|Climate & Models|Why SCC Estimates Disagree
CLIM-14|Climate & Models|Heat Deaths, Cold Deaths, and Adaptation
CLIM-15|Climate & Models|Same Heat, Different Society
CLIM-16|Climate & Models|Sea-Level Rise: From Centimeters to Risk
ENERGY-17|Energy & Grid|LCOE Versus an Electricity System
ENERGY-18|Energy & Grid|100% Renewable for One Real Week
ENERGY-19|Energy & Grid|Four-Hour Batteries Meet a Three-Day Lull
ENERGY-20|Energy & Grid|Storage-Cost Surgery
ENERGY-21|Energy & Grid|Transmission as a Substitute for Storage
ENERGY-22|Energy & Grid|Firming Wind and Solar
ENERGY-23|Energy & Grid|Data Centers: Quantity Constraint or Price Response?
ENERGY-24|Energy & Grid|How Extraordinary Is Current Electricity-Demand Growth?
ENERGY-25|Energy & Grid|Electrify All Passenger Cars
ENERGY-26|Energy & Grid|Electrify Heating
ENERGY-27|Energy & Grid|The Primary-Energy Illusion
ENERGY-28|Energy & Grid|Close a Nuclear Plant—What Replaces It?
ENERGY-29|Energy & Grid|New Nuclear Financing
ENERGY-30|Energy & Grid|One Gigawatt Is Not One Gigawatt
ENERGY-31|Energy & Grid|Curtailment Is Endogenous
ENERGY-32|Energy & Grid|Hydrogen Versus Direct Electrification
RISK-33|Risk & Toxicology|The 2-BE Exercise
RISK-34|Risk & Toxicology|Detection Is Not Exposure Is Not Dose Is Not Harm
RISK-35|Risk & Toxicology|Make Parts per Trillion Physical
RISK-36|Risk & Toxicology|What Happens When Detection Improves 1,000x?
RISK-37|Risk & Toxicology|Hazard Classification Versus Actual Exposure
RISK-38|Risk & Toxicology|Linear-No-Threshold Surgery
RISK-39|Risk & Toxicology|Tiny Risk Times Huge Population
RISK-40|Risk & Toxicology|Chemical Substitution
RISK-41|Risk & Toxicology|Air-Pollution Mortality Model Surgery
RISK-42|Risk & Toxicology|Wildfire Smoke in Scale
RISK-43|Risk & Toxicology|Risk-Risk Tradeoff
RES-44|Resources & Minerals|Lithium Future Under Alternative Battery Chemistries
RES-45|Resources & Minerals|The Copper Bottleneck
RES-46|Resources & Minerals|Years of Reserves Remaining Is a Model
RES-47|Resources & Minerals|Geology Versus Supply Chain
RES-48|Resources & Minerals|How Many New Mines?
RES-49|Resources & Minerals|The Value of Substitution
RES-50|Resources & Minerals|Deep-Sea Versus Terrestrial Mining
FOOD-51|Food & Land|Land Spared by Yield
FOOD-52|Food & Land|No Synthetic Nitrogen
FOOD-53|Food & Land|Organic Yield-Gap Land Model
FOOD-54|Food & Land|Yield Versus Biodiversity
FOOD-55|Food & Land|Beef Land-Use Counterfactual
FOOD-56|Food & Land|Local-Food System Surgery
FOOD-57|Food & Land|Food Miles With Transport Modes
FOOD-58|Food & Land|Precision Agriculture
FOOD-59|Food & Land|GMO Farming-System Counterfactual
WW-60|Water & Waste|How Much Landfill Would We Actually Need?
WW-61|Water & Waste|Landfill Harm Model
WW-62|Water & Waste|Recycling Where It Matters
WW-63|Water & Waste|Plastic Substitution
WW-64|Water & Waste|Western Water Reallocation
WW-65|Water & Waste|Water-Efficiency Paradox
WW-66|Water & Waste|Desalination Future
POL-67|Policy & Institutions|Catch Shares Versus Race-to-Fish
POL-68|Policy & Institutions|Endangered-Species Incentives
POL-69|Policy & Institutions|Carbon-Tax Equivalence
POL-70|Policy & Institutions|What Does $100 per Ton of CO2 Mean in Actual Life?
POL-71|Policy & Institutions|Policy Cost per Ton
POL-72|Policy & Institutions|Carbon Offsets: Make Additionality Visible
POL-73|Policy & Institutions|30x30 Is Not One Conservation Plan
POL-74|Policy & Institutions|Wildfire Policy Counterfactual
POL-75|Policy & Institutions|Precautionary Policy Surgery"""
TOPICS = [dict(zip(("id","cat","title"), line.split("|",2))) for line in RAW.splitlines()]
TMAP = {t["id"]:t for t in TOPICS}

STYLE = """body{margin:0;font-family:Arial,sans-serif;background:#eef2f5;color:#17202a}.wrap{max-width:1050px;margin:auto;background:white;min-height:100vh}.head{background:#073a66;color:white;padding:26px}.head h1{margin:0;font-size:2rem}.nav,main{padding:16px 26px}.nav{background:#f4f6f8;border-bottom:1px solid #ddd}.nav a{margin-right:18px;color:#073a66;font-weight:700;text-decoration:none}.custom,.topic,.card{border:1px solid #d4dbe1;border-radius:10px;padding:16px;margin:0 0 14px}.custom{border:3px solid #2d8b57;background:#f0fbf5}.topic{border-left:7px solid #073a66}.claimed{background:#f3f3f3;border-left-color:#999}.meta{font-size:.83rem;color:#65727e;font-weight:700;text-transform:uppercase}.btn{display:inline-block;background:#073a66;color:white;padding:9px 13px;border:0;border-radius:7px;text-decoration:none;font-weight:700;cursor:pointer}.green{background:#26734d}.danger{background:#a51e22}.ok{color:#176b3a;font-weight:800}.taken{color:#8a3434;font-weight:800}input,textarea,select{padding:9px;border:1px solid #bbb;border-radius:6px;font:inherit;max-width:100%}label{display:block;font-weight:700;margin:11px 0 4px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}.filters input{min-width:260px}.receipt{border:2px solid #073a66;border-radius:10px;padding:18px;background:#f8fbff}.code{font-family:monospace;overflow-wrap:anywhere;background:#eef2f5;padding:5px}.err{background:#fff0f0;color:#7b1616;padding:10px;border-radius:7px}table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{border-bottom:1px solid #ddd;padding:7px;text-align:left;vertical-align:top}"""

BASE = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{{title}}</title><style>""" + STYLE + """</style></head><body><div class='wrap'><header class='head'><h1>SHOW ME</h1><p>ECON 238 Environmental Economics — claim two investigations.</p></header><nav class='nav'><a href='{{url_for("home")}}'>Topics</a><a href='{{url_for("faq")}}'>FAQ</a></nav><main>{{body|safe}}</main></div></body></html>"""

def con():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    c=sqlite3.connect(DB, timeout=20); c.row_factory=sqlite3.Row; return c

def init():
    c=con()
    c.executescript("""CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY AUTOINCREMENT,topic_id TEXT,custom_title TEXT,student_name TEXT NOT NULL,email TEXT NOT NULL,section TEXT,token TEXT NOT NULL UNIQUE,released INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
    CREATE UNIQUE INDEX IF NOT EXISTS uniq_topic ON claims(topic_id) WHERE released=0 AND topic_id IS NOT NULL;""")
    c.commit(); c.close()
init()

def page(title, body, **ctx):
    inner=render_template_string(body, **ctx)
    return render_template_string(BASE,title=title,body=inner)

def shown(name):
    if FULL:return name
    p=name.split(); return name if len(p)<2 else p[0]+" "+p[-1][0]+"."

@app.get("/")
def home():
    c=con(); rows=c.execute("SELECT topic_id,student_name FROM claims WHERE released=0 AND topic_id IS NOT NULL").fetchall(); c.close()
    claimed={r["topic_id"]:shown(r["student_name"]) for r in rows}
    q=request.args.get("q","").lower().strip(); cat=request.args.get("cat","")
    topics=[t for t in TOPICS if (not cat or t["cat"]==cat) and (not q or q in (t["id"]+" "+t["cat"]+" "+t["title"]).lower())]
    cats=sorted({t["cat"] for t in TOPICS})
    body="""<div class='custom'><h2>Create a Topic on My Own</h2><p>Every student may use this option for one of the two investigations. It never becomes unavailable.</p><a class='btn green' href='{{url_for("claim_custom")}}'>Create my own topic</a></div>
    <form class='filters'><input name='q' value='{{q0}}' placeholder='Search topics'><select name='cat'><option value=''>All categories</option>{% for c in cats %}<option {% if c==cat %}selected{% endif %}>{{c}}</option>{% endfor %}</select><button class='btn'>Filter</button></form>
    <p><b>{{available}}</b> available · <b>{{taken}}</b> claimed</p>
    {% for t in topics %}<div class='topic {% if t.id in claimed %}claimed{% endif %}'><div class='meta'>{{t.id}} · {{t.cat}}</div><h3>{{t.title}}</h3>{% if t.id in claimed %}<div class='taken'>CLAIMED — {{claimed[t.id]}}</div>{% else %}<div class='ok'>AVAILABLE</div><p><a class='btn' href='{{url_for("claim_topic",topic_id=t.id)}}'>Claim this topic</a></p>{% endif %}</div>{% endfor %}"""
    return page("SHOW ME",body,topics=topics,claimed=claimed,cats=cats,cat=cat,q0=request.args.get("q",""),available=75-len(claimed),taken=len(claimed))

def count(c,email):
    return c.execute("SELECT COUNT(*) n FROM claims WHERE lower(email)=lower(?) AND released=0",(email,)).fetchone()["n"]

FORM="""{% if error %}<div class='err'>{{error}}</div>{% endif %}<div class='card'><div class='meta'>{{label}}</div><h2>{{heading}}</h2><form method='post'>{% if custom %}<label>Your SHOW ME topic</label><textarea name='custom_title' rows='4' required>{{custom_title}}</textarea>{% endif %}<label>Your name</label><input name='student_name' required><label>University email</label><input type='email' name='email' required><label>Section</label><input name='section'><label>Class code</label><input name='class_code' required><br><button class='btn'>Claim this investigation</button></form></div>"""

def reserve(topic_id=None):
    name=request.form.get("student_name","").strip(); email=request.form.get("email","").strip(); section=request.form.get("section","").strip(); code=request.form.get("class_code","").strip(); custom=request.form.get("custom_title","").strip() if topic_id is None else None
    if not name or not email:return None,"Enter your name and email."
    if code!=CLASS_CODE:return None,"The class code is incorrect."
    if topic_id is None and not custom:return None,"Describe your topic."
    c=con()
    try:
        c.execute("BEGIN IMMEDIATE")
        if count(c,email)>=2:return None,"You already have two active reservations."
        if topic_id is None and c.execute("SELECT 1 FROM claims WHERE lower(email)=lower(?) AND released=0 AND custom_title IS NOT NULL",(email,)).fetchone():return None,"You may create your own topic only once."
        if topic_id and c.execute("SELECT 1 FROM claims WHERE topic_id=? AND released=0",(topic_id,)).fetchone():return None,"Someone else claimed this topic first."
        token=secrets.token_urlsafe(24)
        c.execute("INSERT INTO claims(topic_id,custom_title,student_name,email,section,token,created_at) VALUES(?,?,?,?,?,?,?)",(topic_id,custom,name,email,section,token,datetime.now(timezone.utc).isoformat()))
        c.commit(); return token,None
    except sqlite3.IntegrityError:return None,"Someone else claimed this topic first."
    finally:c.close()

@app.route("/claim/custom",methods=["GET","POST"])
def claim_custom():
    err=None
    if request.method=="POST":
        token,err=reserve()
        if token:return redirect(url_for("receipt",token=token))
    return page("Create a Topic",FORM,error=err,label="CUSTOM SHOW ME",heading="Create a Topic on My Own",custom=True,custom_title=request.form.get("custom_title",""))

@app.route("/claim/<topic_id>",methods=["GET","POST"])
def claim_topic(topic_id):
    t=TMAP.get(topic_id)
    if not t:abort(404)
    err=None
    if request.method=="POST":
        token,err=reserve(topic_id)
        if token:return redirect(url_for("receipt",token=token))
    return page("Claim Topic",FORM,error=err,label=t["id"]+" · "+t["cat"],heading=t["title"],custom=False,custom_title="")

def getclaim(token):
    c=con(); r=c.execute("SELECT * FROM claims WHERE token=?",(token,)).fetchone(); c.close(); return r

@app.get("/receipt/<token>")
def receipt(token):
    r=getclaim(token)
    if not r:abort(404)
    title=r["custom_title"] or TMAP.get(r["topic_id"],{}).get("title",r["topic_id"])
    u=url_for("manage",token=token,_external=True)
    return page("Confirmed","""<div class='receipt'><div class='meta'>RESERVATION CONFIRMED</div><h2>{{title}}</h2><p><b>{{r.student_name}}</b> · {{r.email}}</p><p>Save this private management link:</p><p class='code'>{{u}}</p><a class='btn' href='{{u}}'>Manage reservation</a></div>""",r=r,title=title,u=u)

@app.route("/manage/<token>",methods=["GET","POST"])
def manage(token):
    r=getclaim(token)
    if not r:abort(404)
    if request.method=="POST":
        c=con()
        if request.form.get("action")=="release":
            c.execute("UPDATE claims SET released=1 WHERE token=?",(token,)); c.commit(); c.close()
            return page("Released","<p class='ok'>Released. The topic is available again.</p><a class='btn' href='"+url_for("home")+"'>Back to topics</a>")
        if request.form.get("action")=="edit" and r["custom_title"] is not None:
            title=request.form.get("custom_title","").strip()
            if title:c.execute("UPDATE claims SET custom_title=? WHERE token=?",(title,token)); c.commit()
        c.close(); r=getclaim(token)
    title=r["custom_title"] or TMAP.get(r["topic_id"],{}).get("title",r["topic_id"])
    return page("Manage","""<div class='card'><h2>{{title}}</h2><p>{{r.student_name}} · {{r.email}}</p>{% if not r.released %}{% if r.custom_title is not none %}<form method='post'><label>Edit custom topic</label><textarea name='custom_title' rows='4'>{{r.custom_title}}</textarea><button class='btn' name='action' value='edit'>Save</button></form>{% endif %}<form method='post'><button class='btn danger' name='action' value='release'>Release reservation</button></form>{% else %}<p>Released.</p>{% endif %}</div>""",r=r,title=title)

@app.route("/admin",methods=["GET","POST"])
def admin():
    if request.method=="POST" and ADMIN_KEY and request.form.get("admin_key")==ADMIN_KEY:
        session["admin"]=True; return redirect(url_for("admin"))
    if not session.get("admin"):
        return page("Instructor","<div class='card'><h2>Instructor</h2><form method='post'><label>Admin key</label><input type='password' name='admin_key'><br><button class='btn'>Open dashboard</button></form></div>")
    c=con(); rows=c.execute("SELECT * FROM claims ORDER BY released,created_at").fetchall(); c.close()
    return page("Instructor","""<p><a class='btn' href='{{url_for("admin_csv")}}'>Download CSV</a></p><table><tr><th>Status</th><th>Student</th><th>Email</th><th>Topic</th><th>Manage</th></tr>{% for r in rows %}<tr><td>{{"Released" if r.released else "Active"}}</td><td>{{r.student_name}}</td><td>{{r.email}}</td><td>{{("CUSTOM: "+r.custom_title) if r.custom_title else r.topic_id}}</td><td><a href='{{url_for("manage",token=r.token)}}'>open</a></td></tr>{% endfor %}</table>""",rows=rows)

@app.get("/admin.csv")
def admin_csv():
    if not session.get("admin"):return redirect(url_for("admin"))
    c=con(); rows=c.execute("SELECT * FROM claims ORDER BY created_at").fetchall(); c.close()
    s=io.StringIO(); w=csv.writer(s); w.writerow(["status","student","email","section","topic_id","custom_title","created_at","manage_url"])
    for r in rows:w.writerow(["released" if r["released"] else "active",r["student_name"],r["email"],r["section"],r["topic_id"],r["custom_title"],r["created_at"],url_for("manage",token=r["token"],_external=True)])
    return Response(s.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=show_me_claims.csv"})

@app.get("/faq")
def faq():
    return page("FAQ","""<div class='card'><h2>FAQ</h2><h3>How many?</h3><p>Two active investigations total.</p><h3>Can two students claim the same numbered topic?</h3><p>No. First completed reservation wins.</p><h3>Can I create my own?</h3><p>Yes. Every student may use that option once.</p><h3>Picked the wrong one?</h3><p>Use your private management link to release it.</p></div>""")

@app.get("/health")
def health():return {"ok":True,"topics":len(TOPICS)}

if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")))
