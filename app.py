import os
import psycopg
from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'une-cle-tres-secrete-ici')
DATABASE_URL = os.environ.get('DATABASE_URL')

COMPTE_USER = os.environ.get('AUTH_USER', 'admin')
COMPTE_PASSWORD = os.environ.get('AUTH_PASSWORD', 'admin123')

def initialiser_bdd():
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS anagrammes (id SERIAL PRIMARY KEY, signature TEXT NOT NULL, mot TEXT NOT NULL UNIQUE);")
    conn.commit()
    cur.close()
    conn.close()

def generer_signature(mot):
    return "".join(sorted(mot.lower().strip()))

# --- INJECTION DU COMPTEUR DE MOTS DANS TOUTES LES PAGES ---
@app.context_processor
def injecter_compteur_mots():
    """Compte automatiquement le nombre total de mots pour l'afficher dans le menu."""
    if 'utilisateur' not in session or not DATABASE_URL:
        return dict(total_mots=0)
    try:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM anagrammes;")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        return dict(total_mots=total)
    except Exception:
        return dict(total_mots=0)

# --- ROUTES DE L'APPLICATION ---

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
    
    # CORRECTION ICI : On extrait proprement le texte [row[0]] au lieu de garder toute la ligne SQL
    resultats = [row[0] for row in cur.fetchall()]
    
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

@app.route('/liste-mots')
def liste_mots():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot, signature FROM anagrammes ORDER BY mot ASC;")
    donnees = cur.fetchall()
    cur.close()
    conn.close()
    
    # CORRECTION ICI : Extraction propre du mot et de sa signature
    mots = [row[0] for row in donnees]
    signatures = [row[1] for row in donnees]
    return render_template('liste.html', mots=mots, mot_signatures=signatures)


@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    erreur = None
    if request.method == 'POST':
        identifiant = request.form.get('identifiant', '').strip()
        mot_de_passe = request.form.get('mot_de_passe', '')
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
