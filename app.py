import os
import psycopg
from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'une-cle-tres-secrete-ici')
DATABASE_URL = os.environ.get('DATABASE_URL')

# Vos identifiants uniques configurés dans Render (ou valeurs par défaut ci-dessous)
COMPTE_USER = os.environ.get('AUTH_USER', 'admin')
COMPTE_PASSWORD = os.environ.get('AUTH_PASSWORD', 'admin123')

def initialiser_bdd():
    """Crée uniquement la table des anagrammes."""
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS anagrammes (id SERIAL PRIMARY KEY, signature TEXT NOT NULL, mot TEXT NOT NULL UNIQUE);")
    conn.commit()
    cur.close()
    conn.close()

def generer_signature(mot):
    return "".join(sorted(mot.lower().strip()))

@app.route('/')
def index():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    return render_template('index.html', resultats=None)

@app.route('/rechercher', methods=['GET'])
def rechercher():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    lettres = request.args.get('lettres', '').strip()
    sig = generer_signature(lettres)
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes WHERE signature = %s", (sig,))
    resultats = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', resultats=resultats, tirage=lettres)

@app.route('/ajouter-mot', methods=['GET', 'POST'])
def ajouter_mot():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        mot = request.form.get('nouveau_mot', '').strip().lower()
        if mot:
            sig = generer_signature(mot)
            try:
                conn = psycopg.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s)", (sig, mot))
                conn.commit()
                msg = f"Le mot '{mot}' a bien été enregistré !"
            except Exception:
                msg = f"Le mot '{mot}' existe déjà ou une erreur est survenue."
            finally:
                cur.close()
                conn.close()
    return render_template('ajouter.html', message=msg)

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    erreur = None
    if request.method == 'POST':
        identifiant = request.form.get('identifiant', '').strip()
        mot_de_passe = request.form.get('mot_de_passe', '')
        
        # Vérification directe avec les variables d'environnement
        if identifiant == COMPTE_USER and mot_de_passe == COMPTE_PASSWORD:
            session['utilisateur'] = identifiant
            return redirect(url_for('index'))
        
        erreur = "Identifiant ou mot de passe incorrect."
    return render_template('connexion.html', erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.pop('utilisateur', None)
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    if DATABASE_URL: initialiser_bdd()
    app.run(debug=True)
