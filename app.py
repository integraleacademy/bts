import os, json, re, uuid, threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort

# Envoi des mails
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    f = request.form
    item = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "nom": f.get("nom", ""),
        "prenom": f.get("prenom", ""),
        "mail": f.get("mail", ""),
        "tel": f.get("tel", ""),
        "bts": f.get("bts", ""),
        "entreprise": f.get("entreprise", ""),
        "siret": _digits_only(f.get("siret", "")),
        "resp_nom": f.get("resp_nom", ""),
        "resp_mail": f.get("resp_mail", ""),
        "resp_tel": f.get("resp_tel", ""),
        "date_debut": f.get("date_debut", ""),
        "status": "A traiter",
        "commentaire": ""
    }
    data = _load_data()
    data.append(item)
    _save_data(data)

    # Envoi du mail accusé réception uniquement à l’apprenti
    try:
        if item["mail"]:
            send_ack_mail(item["mail"], item["prenom"], item["nom"])
    except Exception as e:
        print("Erreur envoi mail:", e)

    return render_template("thanks.html", prenom=item["prenom"])


# -----------------------
# Mails
# -----------------------

def _send_html_mail(to_email, subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(FROM_EMAIL, EMAIL_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())

def send_ack_mail(to_email, prenom, nom):
    subject = "✅ Accusé de réception — Intégrale Academy"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width:600px; margin:auto; background:#f9f9f9; padding:20px;">
      <div style="background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); overflow:hidden;">
        <div style="text-align:center; padding:20px 20px 10px 20px;">
          <img src="https://bts-wpfy.onrender.com/static/img/logo.png" alt="Logo" 
               style="max-width:100px; height:auto; display:block; margin:auto;">
          <h2 style="color:#000; font-size:18px; margin:10px 0 0 0;">Intégrale Academy</h2>
        </div>
        <div style="background:#F4C45A; padding:12px; text-align:center;">
          <h3 style="margin:0; font-size:18px; color:#000;">✅ Accusé de réception</h3>
        </div>
        <div style="padding:20px; font-size:15px; color:#333;">
          <p>Bonjour <b>{prenom} {nom}</b>,</p>
          <p>Votre demande a bien été enregistrée ✅</p>
          <p>Notre équipe vous contactera très prochainement.</p>
        </div>
        <div style="padding:15px; font-size:12px; color:#777; text-align:center; border-top:1px solid #eee;">
          Ceci est un accusé de réception automatique — Intégrale Academy
        </div>
      </div>
    </div>
    """
    _send_html_mail(to_email, subject, html)

def send_mail_apprenti_saisi(to_email, prenom, nom, entreprise):
    subject = "📄 Contrat d'apprentissage saisi — Intégrale Academy"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width:600px; margin:auto; background:#f9f9f9; padding:20px;">
      <div style="background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); overflow:hidden;">
        <div style="text-align:center; padding:20px 20px 10px 20px;">
          <img src="https://bts-wpfy.onrender.com/static/img/logo.png" alt="Logo" 
               style="max-width:100px; height:auto; display:block; margin:auto;">
          <h2 style="color:#000; font-size:18px; margin:10px 0 0 0;">Intégrale Academy</h2>
        </div>
        <div style="background:#F4C45A; padding:12px; text-align:center;">
          <h3 style="margin:0; font-size:18px; color:#000;">📄 Contrat saisi</h3>
        </div>
        <div style="padding:20px; font-size:15px; color:#333;">
          <p>Bonjour <b>{prenom} {nom}</b>,</p>
          <p>Nous avons saisi votre contrat d'apprentissage et l’avons transmis à votre entreprise <b>{entreprise}</b> ✅</p>
          <p>L’entreprise doit maintenant compléter sa partie. Nous reviendrons vers vous dès que ce sera validé.</p>
        </div>
        <div style="padding:15px; font-size:12px; color:#777; text-align:center; border-top:1px solid #eee;">
          Ceci est un message automatique — Intégrale Academy
        </div>
      </div>
    </div>
    """
    _send_html_mail(to_email, subject, html)

def send_mail_entreprise_saisi(to_email, entreprise, prenom, nom):
    subject = "📄 Contrat d'apprentissage à compléter — Intégrale Academy"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width:600px; margin:auto; background:#f9f9f9; padding:20px;">
      <div style="background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); overflow:hidden;">
        <div style="text-align:center; padding:20px 20px 10px 20px;">
          <img src="https://bts-wpfy.onrender.com/static/img/logo.png" alt="Logo" 
               style="max-width:100px; height:auto; display:block; margin:auto;">
          <h2 style="color:#000; font-size:18px; margin:10px 0 0 0;">Intégrale Academy</h2>
        </div>
        <div style="background:#F4C45A; padding:12px; text-align:center;">
          <h3 style="margin:0; font-size:18px; color:#000;">📄 Contrat à compléter</h3>
        </div>
        <div style="padding:20px; font-size:15px; color:#333;">
          <p>Bonjour,</p>
          <p>Nous vous avons transmis le contrat d’apprentissage numérique concernant <b>{prenom} {nom}</b> ✅</p>
          <p>Merci de compléter votre partie dans les meilleurs délais.</p>
        </div>
        <div style="padding:15px; font-size:12px; color:#777; text-align:center; border-top:1px solid #eee;">
          Ceci est un message automatique — Intégrale Academy
        </div>
      </div>
    </div>
    """
    _send_html_mail(to_email, subject, html)


# -----------------------
# Routes admin
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

@app.route("/update/<id>", methods=["POST"])
@require_admin
def update(id):
    st = request.form.get("status", "A traiter")
    data = _load_data()
    for r in data:
        if r["id"] == id:
            r["status"] = st
            # ✅ Envoi de mails si "Saisi par l'entreprise"
            if st == "Saisi par l'entreprise":
                try:
                    if r.get("mail"):
                        send_mail_apprenti_saisi(r["mail"], r["prenom"], r["nom"], r["entreprise"])
                    if r.get("resp_mail"):
                        send_mail_entreprise_saisi(r["resp_mail"], r["entreprise"], r["prenom"], r["nom"])
                except Exception as e:
                    print("Erreur envoi mails saisie:", e)
            break
    _save_data(data)
    return redirect(url_for("admin"))

@app.route("/update_comment/<id>", methods=["POST"])
@require_admin
def update_comment(id):
    commentaire = request.form.get("commentaire", "").strip()
    data = _load_data()
    for r in data:
        if r["id"] == id:
            r["commentaire"] = commentaire
            break
    _save_data(data)
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

@app.route("/admin/add", methods=["POST"])
@require_admin
def admin_add():
    f = request.form
    item = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "nom": f.get("nom", ""),
        "prenom": f.get("prenom", ""),
        "bts": f.get("bts", ""),
        "entreprise": f.get("entreprise", ""),
        "siret": _digits_only(f.get("siret", "")),
        "resp_nom": f.get("resp_nom", ""),
        "resp_mail": f.get("resp_mail", ""),
        "resp_tel": f.get("resp_tel", ""),
        "date_debut": f.get("date_debut", ""),
        "status": f.get("status", "A traiter"),
        "commentaire": ""
    }
    data = _load_data()
    data.append(item)
    _save_data(data)
    return redirect(url_for("admin"))

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
        contract["bts"] = request.form.get("bts", "").strip()
        contract["entreprise"] = request.form.get("entreprise", "").strip()
        contract["siret"] = _digits_only(request.form.get("siret", ""))
        contract["resp_nom"] = request.form.get("resp_nom", "").strip()
        contract["resp_mail"] = request.form.get("resp_mail", "").strip()
        contract["resp_tel"] = request.form.get("resp_tel", "").strip()
        contract["date_debut"] = request.form.get("date_debut", "").strip()
        contract["status"] = request.form.get("status", "A traiter")
        contract["commentaire"] = request.form.get("commentaire", "").strip()
        _save_data(data)
        flash("Contrat mis à jour.", "ok")
        return redirect(url_for("admin"))

    return render_template("edit.html", row=contract, statuses=STATUSES)
