import os
import psycopg
import unicodedata
from psycopg.rows import dict_row
from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'une-cle-tres-secrete-ici')
DATABASE_URL = os.environ.get('DATABASE_URL')

COMPTE_USER = os.environ.get('AUTH_USER', 'admin')
COMPTE_PASSWORD = os.environ.get('AUTH_PASSWORD', 'admin123')

def initialiser_bdd():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS anagrammes (id SERIAL PRIMARY KEY, signature TEXT NOT NULL, mot TEXT NOT NULL UNIQUE);")
    conn.commit()
    cur.close()
    conn.close()

def nettoyer_mot(mot):
    if not mot:
        return ""
    mot_decompose = unicodedata.normalize('NFD', mot.strip())
    mot_propre = "".join([c for c in mot_decompose if unicodedata.category(c) != 'Mn']).upper()
    return mot_propre

def generer_signature(mot):
    return "".join(sorted(nettoyer_mot(mot)))

@app.context_processor
def injecter_compteur_mots():
    if 'utilisateur' not in session or not DATABASE_URL:
        return dict(total_mots=0)
    try:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM anagrammes;")
        res = cur.fetchone()
        cur.close()
        conn.close()
        return dict(total_mots=res['total'] if res else 0)
    except Exception:
        return dict(total_mots=0)

@app.route('/')
def index():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    return render_template('index.html', resultats=None)

@app.route('/rechercher', methods=['GET'])
def rechercher():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    lettres = request.args.get('lettres', '').strip()
    sig = generer_signature(lettres)
    
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes WHERE signature = %s", (sig,))
    resultats = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('index.html', resultats=resultats, tirage=nettoyer_mot(lettres))

@app.route('/ajouter-mot', methods=['GET', 'POST'])
def ajouter_mot():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        mot = nettoyer_mot(request.form.get('nouveau_mot', ''))
        if mot:
            sig = generer_signature(mot)
            try:
                conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
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
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    cur = conn.cursor()
    cur.execute("SELECT mot, signature FROM anagrammes ORDER BY mot ASC;")
    donnees = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('liste.html', mots=donnees)

# --- NOUVELLE ACTION : SUPPRIMER UN MOT ---
@app.route('/supprimer-mot', methods=['POST'])
def supprimer_mot():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    mot_a_supprimer = request.form.get('mot_a_supprimer', '')
    
    if mot_a_supprimer:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        cur = conn.cursor()
        # Supprime le mot exact de la base de données
        cur.execute("DELETE FROM anagrammes WHERE mot = %s;", (mot_a_supprimer,))
        conn.commit()
        cur.close()
        conn.close()
        
    # Une fois supprimé, on recharge la page de la liste automatiquement
    return redirect(url_for('liste_mots'))

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

if DATABASE_URL: 
    initialiser_bdd()

if __name__ == '__main__':
    app.run(debug=True)
