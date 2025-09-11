from flask import Flask
app = Flask(__name__)
@app.route("/")
def index():
    return "Plateforme Contrats d’Apprentissage – Flask Render"
