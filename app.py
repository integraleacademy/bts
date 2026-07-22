import os, json, re, uuid, threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
import secrets

# -----------------------
# Config & constantes
# -----------------------
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "contracts.json")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
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

# filtre couleur statuts

@app.template_filter("format_pairs")
def format_pairs(value):
    """Affiche une suite de chiffres groupée 2 par 2."""
    digits = _digits_only(value)
    if not digits:
        return "-"
    return " ".join(digits[i:i + 2] for i in range(0, len(digits), 2))

@app.template_filter("format_phone")
def format_phone(value):
    """Affiche les numéros de téléphone avec des chiffres groupés 2 par 2."""
    return format_pairs(value)

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
    # Génère un token unique pour ce formulaire
    token = secrets.token_urlsafe(32)
    # On le stocke en session pour pouvoir le vérifier au POST
    session["form_token"] = token
    # On l’envoie au template
    return render_template("index.html", form_token=token)


@app.route("/submit", methods=["POST"])
def submit():
    f = request.form

    # Anti-doublon : vérifie le token
    token_form = request.form.get("form_token")
    token_session = session.get("form_token")

    if not token_form or token_form != token_session:
        return "Formulaire déjà soumis ou invalide.", 400

    # Invalide le token après utilisation
    session["form_token"] = None


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
        "caisse_retraite": f.get("caisse_retraite", "").strip(),
        "opco": f.get("opco", "").strip(),
        "numero_convention_collective": f.get("numero_convention_collective", "").strip(),
        "resp_nom": f.get("resp_nom", "").strip(),
        "resp_mail": f.get("resp_mail", "").strip(),
        "resp_tel": f.get("resp_tel", "").strip(),
        "maitre_nom": f.get("maitre_nom", "").strip(),
        "maitre_prenom": f.get("maitre_prenom", "").strip(),
        "maitre_mail": f.get("maitre_mail", "").strip(),
        "maitre_date_naissance": f.get("maitre_date_naissance", "").strip(),
        "maitre_emploi": f.get("maitre_emploi", "").strip(),
        "maitre_diplome": f.get("maitre_diplome", "").strip(),
        "date_debut": f.get("date_debut", "").strip(),
        "status": "A traiter",
        "commentaire": ""
    }
    data = _load_data()
    data.append(item)
    _save_data(data)

    return render_template("thanks.html", prenom=item["prenom"])

# -----------------------
# Auth & Admin views
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session.permanent = True
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Mot de passe incorrect.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("login"))

def _created_at_sort_key(row):
    """Return a robust timestamp key so the newest dossiers appear first."""
    created_at = row.get("created_at") or ""
    if created_at.endswith("Z"):
        created_at = created_at[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(created_at).timestamp()
    except (TypeError, ValueError):
        return 0


@app.route("/admin")
@require_admin
def admin():
    data = sorted(_load_data(), key=_created_at_sort_key, reverse=True)
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
        "caisse_retraite": f.get("caisse_retraite", "").strip(),
        "opco": f.get("opco", "").strip(),
        "numero_convention_collective": f.get("numero_convention_collective", "").strip(),
        "resp_nom": f.get("resp_nom", "").strip(),
        "resp_mail": f.get("resp_mail", "").strip(),
        "resp_tel": f.get("resp_tel", "").strip(),
        "maitre_nom": f.get("maitre_nom", "").strip(),
        "maitre_prenom": f.get("maitre_prenom", "").strip(),
        "maitre_mail": f.get("maitre_mail", "").strip(),
        "maitre_date_naissance": f.get("maitre_date_naissance", "").strip(),
        "maitre_emploi": f.get("maitre_emploi", "").strip(),
        "maitre_diplome": f.get("maitre_diplome", "").strip(),
        "date_debut": f.get("date_debut", "").strip(),
        "status": f.get("status", "A traiter"),
        "commentaire": ""
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
        contract["mail"] = request.form.get("mail", "").strip()
        contract["bts"] = request.form.get("bts", "").strip()
        contract["entreprise"] = request.form.get("entreprise", "").strip()
        contract["siret"] = _digits_only(request.form.get("siret", ""))
        contract["caisse_retraite"] = request.form.get("caisse_retraite", "").strip()
        contract["opco"] = request.form.get("opco", "").strip()
        contract["numero_convention_collective"] = request.form.get("numero_convention_collective", "").strip()
        contract["resp_nom"] = request.form.get("resp_nom", "").strip()
        contract["resp_mail"] = request.form.get("resp_mail", "").strip()
        contract["resp_tel"] = request.form.get("resp_tel", "").strip()
        contract["maitre_nom"] = request.form.get("maitre_nom", "").strip()
        contract["maitre_prenom"] = request.form.get("maitre_prenom", "").strip()
        contract["maitre_mail"] = request.form.get("maitre_mail", "").strip()
        contract["maitre_date_naissance"] = request.form.get("maitre_date_naissance", "").strip()
        contract["maitre_emploi"] = request.form.get("maitre_emploi", "").strip()
        contract["maitre_diplome"] = request.form.get("maitre_diplome", "").strip()
        contract["date_debut"] = request.form.get("date_debut", "").strip()
        contract["status"] = request.form.get("status", "A traiter")
        contract["commentaire"] = request.form.get("commentaire", "").strip()
        _save_data(data)
        flash("Contrat mis à jour.","ok")
        return redirect(url_for("admin"))

    return render_template("edit.html", row=contract, statuses=STATUSES)

# -----------------------
# Route publique pour exposer contracts.json (avec CORS)
# -----------------------
@app.route("/data.json")
def data_json():
    """Renvoie les statistiques des contrats pour la plateforme principale"""
    try:
        if not os.path.exists(DATA_FILE):
            result = {
                "contracts": [],
                "summary": {"a_traiter": 0, "signature_en_cours": 0, "saisi_entreprise": 0}
            }
        else:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []

            result = {
                "contracts": data,
                "summary": {
                    "a_traiter": sum(1 for d in data if d.get("status") == "A traiter"),
                    "signature_en_cours": sum(1 for d in data if d.get("status") == "Signature en cours"),
                    "saisi_entreprise": sum(1 for d in data if d.get("status") == "Saisi par l'entreprise")
                }
            }

        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
        return json.dumps(result, ensure_ascii=False), 200, headers

    except Exception as e:
        print("Erreur lecture contracts.json:", e)
        return json.dumps({"error": str(e)}), 500, {
            "Access-Control-Allow-Origin": "*"
        }
