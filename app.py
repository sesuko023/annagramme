import os
import psycopg
from flask import Flask, request, render_template, render_template_string, redirect, url_for, session
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

def compter_mots():
    try:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM anagrammes;")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        return total
    except Exception:
        return 0

# --- INLINE TEMPLATES POUR COMPLÉTER LE LAYOUT ---
HTML_INDEX = """{% extends "layout.html" %}{% block content %}
<h1>🔎 Code Query (Recherche)</h1>
<form method="GET" action="/rechercher">
    <input type="text" name="lettres" placeholder="Entrez vos lettres (ex: ehcin)" required style="width:75%; margin-right:10px;">
    <input type="submit" value="Search">
</form>
{% endblock %}"""

HTML_RECHERCHE = """{% extends "layout.html" %}{% block content %}
<h1>🔎 Code Query (Recherche)</h1>
<form method="GET" action="/rechercher">
    <input type="text" name="lettres" value="{{ tirage }}" required style="width:75%; margin-right:10px;">
    <input type="submit" value="Search">
</form>
<h3>Results for "{{ tirage }}" :</h3>
{% if resultats %}
    <ul>{% for mot in resultats %}<li><strong>{{ mot }}</strong> <span class="badge">{{ sig }}</span></li>{% endfor %}</ul>
{% else %}<p>Aucun anagramme trouvé dans la base.</p>{% endif %}
{% endblock %}"""

HTML_AJOUTER = """{% extends "layout.html" %}{% block content %}
<h1>📥 Push un mot (Ajout manuel)</h1>
{{ msg | safe }}
<form method="POST">
    <input type="text" name="nouveau_mot" placeholder="Ex: niche" required style="width:75%; margin-right:10px;">
    <input type="submit" value="Commit Mot">
</form>
{% endblock %}"""

HTML_IMPORT = """{% extends "layout.html" %}{% block content %}
<h1>⚡ Bulk Import (Importation en masse)</h1>
{{ msg | safe }}
<p style="font-size: 0.9em; color: var(--text-badge);">Collez votre liste de mots. Séparateurs acceptés : retours à la ligne, espaces ou virgules.</p>
<form method="POST">
    <textarea name="liste_mots" rows="12" placeholder="chien&#10;niche&#10;chine" required></textarea>
    <input type="submit" value="Execute Bulk Load">
</form>
{% endblock %}"""

HTML_LISTE = """{% extends "layout.html" %}{% block content %}
<h1>📋 Main Database (Tous les mots)</h1>
<p style="font-size: 0.9em; color: var(--text-badge);">Liste complète des mots dans votre dictionnaire cloud.</p>
{% if mots %}
    <ul>
    {% for row in mots %}
        <li><strong>{{ row[0] }}</strong> <span class="badge">Signature : {{ row[1] }}</span></li>
    {% endfor %}
    </ul>
{% else %}<p>La base de données est vide.</p>{% endif %}
{% endblock %}"""



PAGE_AUTH = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Connexion</title>
<style>
    body { font-family: Arial, sans-serif; background: #f6f8fa; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
    .box { background: #ffffff; padding: 34px; border: 1px solid #d0d7de; border-radius: 8px; width: 300px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    h2 { font-size: 1.3em; font-weight: 600; margin-top: 0; text-align: center; }
    input[type="text"], input[type="password"] { width: 100%; padding: 8px 12px; margin: 10px 0; border: 1px solid #d0d7de; border-radius: 6px; box-sizing: border-box; }
    input[type="submit"] { width: 100%; padding: 8px; background: #1f883d; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
    .error { color: #cf222e; font-size: 0.85em; text-align: center; margin-bottom: 10px; }
    .links { margin-top: 15px; text-align: center; font-size: 0.85em; } .links a { color: #0969da; text-decoration: none; }
</style></head><body><div class="box"><h2>{{ titre }}</h2>{% if erreur %}<div class="error">{{ erreur }}</div>{% endif %}
<form method="POST"><input type="text" name="identifiant" placeholder="Identifiant" required><input type="password" name="mot_de_passe" placeholder="Mot de passe" required><input type="submit" value="Valider"></form>
<div class="links">{% if titre == '🔒 Sign in' %}<a href="/inscription">Créer un compte</a>{% else %}<a href="/connexion">Se connecter</a>{% endif %}</div>
</div></body></html>"""

@app.route('/')
def index():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    return render_template_string(HTML_INDEX, total_mots=compter_mots())

@app.route('/rechercher', methods=['GET'])
def rechercher():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    lettres = request.args.get('lettres', '').strip()
    sig = generer_signature(lettres)
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes WHERE signature = %s", (sig,))
    resultats = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return render_template_string(HTML_RECHERCHE, total_mots=compter_mots(), resultats=resultats, tirage=lettres, sig=sig)

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        mot = request.form.get('nouveau_mot', '').strip().lower()
        if mot:
            sig = generer_signature(mot)
            try:
                conn = psycopg.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s) ON CONFLICT (mot) DO NOTHING", (sig, mot))
                conn.commit()
                msg = f'<div class="message">✔️ Mot "{mot}" indexé !</div>' if cur.rowcount > 0 else '<div class="error">⚠️ Existe déjà.</div>'
                cur.close()
                conn.close()
            except Exception: msg = '<div class="error">Erreur d\'écriture.</div>'
    return render_template_string(HTML_AJOUTER, total_mots=compter_mots(), msg=msg)

@app.route('/importation-masse', methods=['GET', 'POST'])
def importation_masse():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        texte_brut = request.form.get('liste_mots', '')
        mots_bruts = texte_brut.replace(',', ' ').split()
        mots_ajoutes = 0
        if mots_bruts:
            conn = psycopg.connect(DATABASE_URL)
            cur = conn.cursor()
            for m in mots_bruts:
                mot_propre = m.strip().lower()
                if mot_propre.isalpha():
                    sig = generer_signature(mot_propre)
                    cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s) ON CONFLICT (mot) DO NOTHING", (sig, mot_propre))
                    if cur.rowcount > 0: mots_ajoutes += 1
            conn.commit()
            cur.close()
            conn.close()
            msg = f'<div class="message">🚀 {mots_ajoutes} mots ajoutés !</div>'
    return render_template_string(HTML_IMPORT, total_mots=compter_mots(), msg=msg)

@app.route('/liste-mots')
def liste_mots():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot, signature FROM anagrammes ORDER BY mot ASC;")
    mots = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(HTML_LISTE, total_mots=compter_mots(), mots=mots)


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
    return render_template_string(PAGE_AUTH, titre="🔒 Sign in", erreur=erreur)

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
    return render_template_string(PAGE_AUTH, titre="📝 Sign up", erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.pop('utilisateur', None)
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    if DATABASE_URL: initialiser_bdd()
    app.run(debug=True)
import os
import psycopg
from flask import Flask, request, render_template, render_template_string, redirect, url_for, session
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

def compter_mots():
    try:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM anagrammes;")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        return total
    except Exception:
        return 0

# --- INLINE TEMPLATES POUR COMPLÉTER LE LAYOUT ---
HTML_INDEX = """{% extends "layout.html" %}{% block content %}
<h1>🔎 Code Query (Recherche)</h1>
<form method="GET" action="/rechercher">
    <input type="text" name="lettres" placeholder="Entrez vos lettres (ex: ehcin)" required style="width:75%; margin-right:10px;">
    <input type="submit" value="Search">
</form>
{% endblock %}"""

HTML_RECHERCHE = """{% extends "layout.html" %}{% block content %}
<h1>🔎 Code Query (Recherche)</h1>
<form method="GET" action="/rechercher">
    <input type="text" name="lettres" value="{{ tirage }}" required style="width:75%; margin-right:10px;">
    <input type="submit" value="Search">
</form>
<h3>Results for "{{ tirage }}" :</h3>
{% if resultats %}
    <ul>{% for mot in resultats %}<li><strong>{{ mot }}</strong> <span class="badge">{{ sig }}</span></li>{% endfor %}</ul>
{% else %}<p>Aucun anagramme trouvé dans la base.</p>{% endif %}
{% endblock %}"""

HTML_AJOUTER = """{% extends "layout.html" %}{% block content %}
<h1>📥 Push un mot (Ajout manuel)</h1>
{{ msg | safe }}
<form method="POST">
    <input type="text" name="nouveau_mot" placeholder="Ex: niche" required style="width:75%; margin-right:10px;">
    <input type="submit" value="Commit Mot">
</form>
{% endblock %}"""

HTML_IMPORT = """{% extends "layout.html" %}{% block content %}
<h1>⚡ Bulk Import (Importation en masse)</h1>
{{ msg | safe }}
<p style="font-size: 0.9em; color: var(--text-badge);">Collez votre liste de mots. Séparateurs acceptés : retours à la ligne, espaces ou virgules.</p>
<form method="POST">
    <textarea name="liste_mots" rows="12" placeholder="chien&#10;niche&#10;chine" required></textarea>
    <input type="submit" value="Execute Bulk Load">
</form>
{% endblock %}"""

PAGE_AUTH = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Connexion</title>
<style>
    body { font-family: Arial, sans-serif; background: #f6f8fa; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
    .box { background: #ffffff; padding: 34px; border: 1px solid #d0d7de; border-radius: 8px; width: 300px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    h2 { font-size: 1.3em; font-weight: 600; margin-top: 0; text-align: center; }
    input[type="text"], input[type="password"] { width: 100%; padding: 8px 12px; margin: 10px 0; border: 1px solid #d0d7de; border-radius: 6px; box-sizing: border-box; }
    input[type="submit"] { width: 100%; padding: 8px; background: #1f883d; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
    .error { color: #cf222e; font-size: 0.85em; text-align: center; margin-bottom: 10px; }
    .links { margin-top: 15px; text-align: center; font-size: 0.85em; } .links a { color: #0969da; text-decoration: none; }
</style></head><body><div class="box"><h2>{{ titre }}</h2>{% if erreur %}<div class="error">{{ erreur }}</div>{% endif %}
<form method="POST"><input type="text" name="identifiant" placeholder="Identifiant" required><input type="password" name="mot_de_passe" placeholder="Mot de passe" required><input type="submit" value="Valider"></form>
<div class="links">{% if titre == '🔒 Sign in' %}<a href="/inscription">Créer un compte</a>{% else %}<a href="/connexion">Se connecter</a>{% endif %}</div>
</div></body></html>"""

@app.route('/')
def index():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    return render_template_string(HTML_INDEX, total_mots=compter_mots())

@app.route('/rechercher', methods=['GET'])
def rechercher():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    lettres = request.args.get('lettres', '').strip()
    sig = generer_signature(lettres)
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes WHERE signature = %s", (sig,))
    resultats = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return render_template_string(HTML_RECHERCHE, total_mots=compter_mots(), resultats=resultats, tirage=lettres, sig=sig)

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        mot = request.form.get('nouveau_mot', '').strip().lower()
        if mot:
            sig = generer_signature(mot)
            try:
                conn = psycopg.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s) ON CONFLICT (mot) DO NOTHING", (sig, mot))
                conn.commit()
                msg = f'<div class="message">✔️ Mot "{mot}" indexé !</div>' if cur.rowcount > 0 else '<div class="error">⚠️ Existe déjà.</div>'
                cur.close()
                conn.close()
            except Exception: msg = '<div class="error">Erreur d\'écriture.</div>'
    return render_template_string(HTML_AJOUTER, total_mots=compter_mots(), msg=msg)

@app.route('/importation-masse', methods=['GET', 'POST'])
def importation_masse():
    if 'utilisateur' not in session: return redirect(url_for('connexion'))
    msg = ""
    if request.method == 'POST':
        texte_brut = request.form.get('liste_mots', '')
        mots_bruts = texte_brut.replace(',', ' ').split()
        mots_ajoutes = 0
        if mots_bruts:
            conn = psycopg.connect(DATABASE_URL)
            cur = conn.cursor()
            for m in mots_bruts:
                mot_propre = m.strip().lower()
                if mot_propre.isalpha():
                    sig = generer_signature(mot_propre)
                    cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s) ON CONFLICT (mot) DO NOTHING", (sig, mot_propre))
                    if cur.rowcount > 0: mots_ajoutes += 1
            conn.commit()
            cur.close()
            conn.close()
            msg = f'<div class="message">🚀 {mots_ajoutes} mots ajoutés !</div>'
    return render_template_string(HTML_IMPORT, total_mots=compter_mots(), msg=msg)

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
    return render_template_string(PAGE_AUTH, titre="🔒 Sign in", erreur=erreur)

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
    return render_template_string(PAGE_AUTH, titre="📝 Sign up", erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.pop('utilisateur', None)
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    if DATABASE_URL: initialiser_bdd()
    app.run(debug=True)
