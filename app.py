import os
import psycopg
from flask import Flask, request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'une-cle-tres-secrete-ici')
DATABASE_URL = os.environ.get('DATABASE_URL')

def initialiser_bdd():
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS anagrammes (id SERIAL PRIMARY KEY, signature TEXT NOT NULL, mot TEXT NOT NULL UNIQUE);")
    cur.execute("CREATE TABLE IF NOT EXISTS utilisateurs (id SERIAL PRIMARY KEY, identifiant TEXT NOT NULL UNIQUE, mot_de_passe_hache TEXT NOT NULL);")
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
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT mot_de_passe_hache FROM utilisateurs WHERE identifiant = %s", (identifiant,))
        compte = cur.fetchone()
        cur.close()
        conn.close()
        if compte and check_password_hash(compte[0], mot_de_passe):
            session['utilisateur'] = identifiant
            return redirect(url_for('index'))
        erreur = "Identifiant ou mot de passe incorrect."
    return render_template('connexion.html', erreur=erreur)

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    erreur = None
    if request.method == 'POST':
        identifiant = request.form.get('identifiant', '').strip()
        mot_de_passe = request.form.get('mot_de_passe', '')
        if identifiant and mot_de_passe:
            hache = generate_password_hash(mot_de_passe)
            try:
                conn = psycopg.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("INSERT INTO utilisateurs (identifiant, mot_de_passe_hache) VALUES (%s, %s)", (identifiant, hache))
                conn.commit()
                cur.close()
                conn.close()
                session['utilisateur'] = identifiant
                return redirect(url_for('index'))
            except Exception:
                erreur = "Cet identifiant est déjà pris."
    return render_template('inscription.html', erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.pop('utilisateur', None)
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    if DATABASE_URL: initialiser_bdd()
    app.run(debug=True)
