import os
import psycopg
import unicodedata
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

def nettoyer_mot(texte):
    """Met en majuscules et supprime tous les accents (ex: niché -> NICHE)."""
    if not texte: return ""
    texte_normalise = unicodedata.normalize('NFD', texte.strip())
    texte_sans_accent = "".join(c for c in texte_normalise if unicodedata.category(c) != 'Mn')
    return "".join(c for c in texte_sans_accent if c.isalpha()).upper()

def generer_signature(mot_propre):
    return "".join(sorted(mot_propre))

def compter_mots():
    """Compte le nombre de mots de manière sécurisée en extrayant l'entier brut."""
    try:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM anagrammes;")
        resultat = cur.fetchone()
        cur.close()
        conn.close()
        return resultat[0] if resultat else 0  # Extraction de l'entier du tuple (ex: 868)
    except Exception: return 0

@app.route('/')
def index():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    return render_template("index.html", total_mots=compter_mots(), page="index", resultats=None)

@app.route('/rechercher', methods=['GET'])
def rechercher():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    lettres = request.args.get('lettres', '').strip()
    lettres_propres = nettoyer_mot(lettres)
    sig = generer_signature(lettres_propres)
    
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes WHERE signature = %s ORDER BY mot ASC", (sig,))
    resultats = [row[0] for row in cur.fetchall()]  # Extraction du texte propre de chaque ligne
    cur.close()
    conn.close()
    return render_template("index.html", total_mots=compter_mots(), resultats=resultats, tirage=lettres, sig=sig, page="index")

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg, err = "", ""
    if request.method == 'POST':
        mot_brut = request.form.get('nouveau_mot', '')
        mot_propre = nettoyer_mot(mot_brut)
        if mot_propre:
            sig = generer_signature(mot_propre)
            try:
                conn = psycopg.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s) ON CONFLICT (mot) DO NOTHING", (sig, mot_propre))
                conn.commit()
                msg = f'✔️ Mot "{mot_propre}" indexé !'
                cur.close()
                conn.close()
            except Exception: err = "Erreur d'écriture."
    return render_template("ajouter.html", total_mots=compter_mots(), msg=msg, err=err, page="ajouter")

@app.route('/importation-masse', methods=['GET', 'POST'])

@app.route('/importation-masse', methods=['GET', 'POST'])
def importation_masse():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        texte_brut = ""
        
        if 'fichier_mots' in request.files:
            fichier = request.files['fichier_mots']
            if fichier and fichier.filename != '':
                if fichier.filename.endswith('.txt'):
                    texte_brut = fichier.read().decode('utf-8', errors='ignore')
        
        if not texte_brut:
            texte_brut = request.form.get('liste_mots', '').strip()
            
        mots_bruts = texte_brut.replace(',', ' ').split()
        
        if mots_bruts:
            # 1. On stocke le nombre de mots AVANT l'importation (vrai entier)
            avant = compter_mots()
            
            conn = psycopg.connect(DATABASE_URL)
            cur = conn.cursor()
            
            tuples_mots = []
            mots_vus = set()
            for m in mots_bruts:
                mot_propre = nettoyer_mot(m)
                if mot_propre and mot_propre not in mots_vus:
                    mots_vus.add(mot_propre)
                    sig = generer_signature(mot_propre)
                    tuples_mots.append((sig, mot_propre))
            
            if tuples_mots:
                cur.executemany(
                    "INSERT INTO anagrammes (signature, mot) VALUES (%s, %s) ON CONFLICT (mot) DO NOTHING",
                    tuples_mots
                )
                
            conn.commit()
            cur.close()
            conn.close()
            
            # 2. On calcule la différence avec le nombre APRES l'importation
            apres = compter_mots()
            mots_ajoutes = apres - avant
            
            msg = f'<i class="fa-solid fa-circle-check"></i> Importation réussie ! {mots_ajoutes} nouveaux mots ont été ajoutés à la base.'
        else:
            msg = '<i class="fa-solid fa-circle-exclamation"></i> Aucun mot trouvé. Veuillez sélectionner un fichier ou écrire du texte.'
            
    return render_template("import.html", total_mots=compter_mots(), bulk_msg=msg, page="import")


@app.route('/liste-mots')
def liste_mots():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes ORDER BY mot ASC;")
    mots = [row[0] for row in cur.fetchall()]  # Extraction du texte propre de chaque ligne
    cur.close()
    conn.close()
    return render_template("liste.html", total_mots=compter_mots(), mots=mots, page="liste")

@app.route('/supprimer-mot', methods=['POST'])
def supprimer_mot():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    mot = request.form.get('mot_a_supprimer', '').strip().upper()
    if mot:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("DELETE FROM anagrammes WHERE mot = %s", (mot,))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('liste_mots'))

@app.route('/vider-base', methods=['POST'])
def vider_base():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    try:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE anagrammes;")
        conn.commit()
        cur.close()
        conn.close()
    except Exception: pass
    return redirect(url_for('liste_mots'))

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
        if compte and check_password_hash(compte[0], mot_de_passe):  # Extraction du hash propre
            session['utilisateur'] = identifiant
            return redirect(url_for('index'))
        erreur = "Identifiant ou mot de passe incorrect."
    return render_template("auth.html", auth_mode="login", erreur=erreur)

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
            except Exception: erreur = "Identifiant déjà pris."
    return render_template("auth.html", auth_mode="register", erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.pop('utilisateur', None)
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    if DATABASE_URL: initialiser_bdd()
    app.run(debug=True)
