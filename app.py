import os, json, re, uuid, threading
from datetime import datetime
import pytz   # ✅ pour heure française
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
    def wrapper(*a,**kw):
        if not session.get("is_admin"):
            return redirect(url_for("login", next=request.path))
        return view(*a,**kw)
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
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(FROM_EMAIL, EMAIL_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())

def _mail_wrapper(title_html, body_html):
    """Habillage visuel commun (logo + bandeau doré + carte blanche)."""
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

def send_ack_mail(to_email, prenom, nom):
    subject = "✅ Accusé de réception — Intégrale Academy"
    title = '<h3 style="margin:0; font-size:18px; color:#000;">✅ Accusé de réception</h3>'
    body = f"""
      <p>Bonjour <b>{prenom} {nom}</b>,</p>
      <p>Votre demande a bien été enregistrée ✅</p>
      <p>Notre équipe vous contactera très prochainement.</p>
    """
    _send_html_mail(to_email, subject, _mail_wrapper(title, body))

# ... (les autres fonctions send_mail_* restent inchangées, avec add_log après chaque envoi dans /update)

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
