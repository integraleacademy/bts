import os, json, re, uuid, threading
from datetime import datetime
import pytz   # heure française
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort

# Envoi des mails
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -----------------------
# Config & constantes
# -----------------------
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "contracts.json")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# ✅ Variables d’environnement Gmail
FROM_EMAIL = os.environ.get("FROM_EMAIL", "ecole@integraleacademy.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

app = Flask(__name__)
app.secret_key = SECRET_KEY
_SAVE_LOCK = threading.Lock()

STATUSES = [
    "A traiter",
    "Saisi par l'entreprise",
    "Signature en cours",
    "Transmis à l'OPCO"
]

# -----------------------
# Utilitaires data & auth
# -----------------------
def _load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_data(data):
    with _SAVE_LOCK:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)

def _digits_only(s):
    return re.sub(r"\D", "", s or "")

def require_admin(view):
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    wrapper.__name__ = view.__name__
    return wrapper

def add_log(contract, message):
    """Ajoute une entrée dans l'historique des mails (heure française)."""
    tz = pytz.timezone("Europe/Paris")
    ts = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    if "logs" not in contract:
        contract["logs"] = []
    contract["logs"].append(f"[{ts}] {message}")

# filtre couleur statuts
@app.template_filter("status_color")
def status_color(status):
    mapping = {
        "A traiter": "red",
        "Saisi par l'entreprise": "orange",
        "Signature en cours": "gold",
        "Transmis à l'OPCO": "green"
    }
    return mapping.get(status, "gray")

# -----------------------
# Pages publiques
# -----------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    f = request.form
    item = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "nom": f.get("nom", "").strip(),
        "prenom": f.get("prenom", "").strip(),
        "mail": f.get("mail", "").strip(),
        "tel": f.get("tel", "").strip(),
        "bts": f.get("bts", "").strip(),
        "entreprise": f.get("entreprise", "").strip(),
        "siret": _digits_only(f.get("siret", "")),
        "resp_nom": f.get("resp_nom", "").strip(),
        "resp_mail": f.get("resp_mail", "").strip(),
        "resp_tel": f.get("resp_tel", "").strip(),
        "date_debut": f.get("date_debut", "").strip(),
        "status": "A traiter",
        "commentaire": "",
        "logs": []
    }
    data = _load_data()
    data.append(item)
    _save_data(data)

    # Mail accusé de réception (apprenti)
    try:
        if item["mail"]:
            send_ack_mail(item["mail"], item["prenom"], item["nom"])
            add_log(item, f"Mail accusé de réception envoyé à {item['mail']}")
            _save_data(data)
    except Exception as e:
        print("Erreur envoi mail:", e)

    return render_template("thanks.html", prenom=item["prenom"])

# -----------------------
# Helpers mails
# -----------------------
def _send_html_mail(to_email, subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    # 👇 Ajout d’une copie systématique à Clément
    recipients = [to_email, "clement@integraleacademy.com"]

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(FROM_EMAIL, EMAIL_PASSWORD)
        server.sendmail(FROM_EMAIL, recipients, msg.as_string())

def _mail_wrapper(title_html, body_html):
    """Habillage visuel commun + bloc assistance."""
    assistance = """
      <div style="margin-top:20px; text-align:center;">
        <a href="https://assistance-alw9.onrender.com/" 
           style="display:inline-block; padding:10px 20px; background:#F4C45A; color:#000; 
                  text-decoration:none; border-radius:6px; font-weight:bold;">
           💬 Cliquez ici pour contacter l’assistance Intégrale Academy
        </a>
        <p style="margin-top:8px; font-size:14px; color:#333;">
          ou par téléphone : <b>04 22 47 07 68</b>
        </p>
      </div>
    """
    return f"""
    <div style="font-family: Arial, sans-serif; max-width:600px; margin:auto; background:#f9f9f9; padding:20px;">
      <div style="background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); overflow:hidden;">
        <div style="text-align:center; padding:20px 20px 10px 20px;">
          <img src="https://bts-wpfy.onrender.com/static/img/logo.png" alt="Logo"
               style="max-width:100px; height:auto; display:block; margin:auto;">
          <h2 style="color:#000; font-size:18px; margin:10px 0 0 0;">Intégrale Academy</h2>
        </div>
        <div style="background:#F4C45A; padding:12px; text-align:center;">
          {title_html}
        </div>
        <div style="padding:20px; font-size:15px; color:#333;">
          {body_html}
          {assistance}
        </div>
        <div style="padding:15px; font-size:12px; color:#777; text-align:center; border-top:1px solid #eee;">
          Ceci est un message automatique — Intégrale Academy
        </div>
      </div>
    </div>
    """

# -----------------------
# Modèles de mails
# -----------------------
# (inchangés, je ne les recopie pas ici pour alléger)

# -----------------------
# Auth & Admin views
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Mot de passe incorrect.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("login"))

@app.route("/admin")
@require_admin
def admin():
    data = _load_data()
    return render_template("admin.html", rows=data, statuses=STATUSES)

@app.route("/admin/add", methods=["POST"])
@require_admin
def admin_add():
    f = request.form
    item = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "nom": f.get("nom", "").strip(),
        "prenom": f.get("prenom", "").strip(),
        "bts": f.get("bts", "").strip(),
        "entreprise": f.get("entreprise", "").strip(),
        "siret": _digits_only(f.get("siret", "")),
        "resp_nom": f.get("resp_nom", "").strip(),
        "resp_mail": f.get("resp_mail", "").strip(),
        "resp_tel": f.get("resp_tel", "").strip(),
        "date_debut": f.get("date_debut", "").strip(),
        "status": f.get("status", "A traiter"),
        "commentaire": "",
        "logs": []
    }
    data = _load_data()
    data.append(item)
    _save_data(data)
    return redirect(url_for("admin"))

@app.route("/update/<id>", methods=["POST"])
@require_admin
def update(id):
    st = request.form.get("status", "A traiter")
    data = _load_data()
    for r in data:
        if r["id"] == id:
            r["status"] = st
            try:
                if st == "Saisi par l'entreprise":
                    if r.get("mail"):
                        send_mail_apprenti_saisi(r["mail"], r["prenom"], r["nom"], r.get("entreprise",""))
                        add_log(r, f"Mail 'Saisi par l'entreprise' envoyé à {r['mail']}")
                    if r.get("resp_mail"):
                        send_mail_entreprise_saisi(r["resp_mail"], r.get("entreprise",""), r["prenom"], r["nom"])
                        add_log(r, f"Mail 'Saisi par l'entreprise' envoyé à {r['resp_mail']}")
                elif st == "Signature en cours":
                    if r.get("mail"):
                        send_mail_apprenti_signature(r["mail"], r["prenom"], r["nom"])
                        add_log(r, f"Mail 'Signature en cours' envoyé à {r['mail']}")
                    if r.get("resp_mail"):
                        send_mail_entreprise_signature(r["resp_mail"], r.get("entreprise",""), r["prenom"], r["nom"])
                        add_log(r, f"Mail 'Signature en cours' envoyé à {r['resp_mail']}")
                elif st == "Transmis à l'OPCO":
                    if r.get("mail"):
                        send_mail_apprenti_opco(r["mail"], r["prenom"], r["nom"])
                        add_log(r, f"Mail 'Transmis à l’OPCO' envoyé à {r['mail']}")
                    if r.get("resp_mail"):
                        send_mail_entreprise_opco(r["resp_mail"], r.get("entreprise",""), r["prenom"], r["nom"])
                        add_log(r, f"Mail 'Transmis à l’OPCO' envoyé à {r['resp_mail']}")
            except Exception as e:
                print("Erreur envoi mails statut:", e)
            _save_data(data)
            break
    return redirect(url_for("admin"))

@app.route("/update_comment/<id>", methods=["POST"])
@require_admin
def update_comment(id):
    commentaire = request.form.get("commentaire", "").strip()
    data = _load_data()
    for r in data:
        if r["id"] == id:
            r["commentaire"] = commentaire
            _save_data(data)
            break
    return redirect(url_for("admin"))

@app.route("/delete/<id>", methods=["POST"])
@require_admin
def delete(id):
    data = _load_data()
    new = [r for r in data if r["id"] != id]
    _save_data(new)
    return redirect(url_for("admin"))

@app.route("/fiche/<id>")
@require_admin
def fiche(id):
    for r in _load_data():
        if r["id"] == id:
            return render_template("fiche.html", row=r)
    abort(404)

@app.route("/edit/<id>", methods=["GET", "POST"])
@require_admin
def edit(id):
    data = _load_data()
    contract = None
    for r in data:
        if r["id"] == id:
            contract = r
            break
    if not contract:
        abort(404, "Contrat introuvable")

    if request.method == "POST":
        contract["nom"] = request.form.get("nom", "").strip()
        contract["prenom"] = request.form.get("prenom", "").strip()
        contract["mail"] = request.form.get("mail", "").strip()   # ✅ Correction ici
        contract["bts"] = request.form.get("bts", "").strip()
        contract["entreprise"] = request.form.get("entreprise", "").strip()
        contract["siret"] = _digits_only(request.form.get("siret", ""))
        contract["resp_nom"] = request.form.get("resp_nom", "").strip()
        contract["resp_mail"] = request.form.get("resp_mail", "").strip()
        contract["resp_tel"] = request.form.get("resp_tel", "").strip()
        contract["date_debut"] = request.form.get("date_debut", "").strip()
        contract["status"] = request.form.get("status", "A traiter")
        contract["commentaire"] = request.form.get("commentaire", "").strip()
        if "logs" not in contract:
            contract["logs"] = []
        _save_data(data)
        flash("Contrat mis à jour.","ok")
        return redirect(url_for("admin"))

    return render_template("edit.html", row=contract, statuses=STATUSES)
