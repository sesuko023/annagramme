import os
import psycopg2
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Récupère l'URL de connexion sécurisée fournie par l'hébergeur de la base de données
DATABASE_URL = os.environ.get('DATABASE_URL')

def initialiser_bdd():
    """Crée la table des mots si elle n'existe pas encore."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anagrammes (
            id SERIAL PRIMARY KEY,
            signature TEXT NOT NULL,
            mot TEXT NOT NULL UNIQUE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def generer_signature(mot):
    """Trie les lettres d'un mot par ordre alphabétique."""
    return "".join(sorted(mot.lower().strip()))

# Page web de l'application (Identique à la précédente)
HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Mon Anagrammeur Web Pro</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        .section { background: #f4f4f9; padding: 20px; margin-bottom: 20px; border-radius: 8px; }
        input[type="text"] { width: 70%; padding: 8px; margin-right: 10px; }
        input[type="submit"] { padding: 8px 15px; background: #007BFF; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .message { color: green; font-weight: bold; }
        ul { background: #e2e2e2; padding: 10px 30px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>🔤 Anagrammeur Cloud</h1>
    {% if message %}<p class="message">{{ message }}</p>{% endif %}
    <div class="section">
        <h2>📥 Ajouter un mot</h2>
        <form method="POST" action="/ajouter">
            <input type="text" name="nouveau_mot" placeholder="Ex: chien" required>
            <input type="submit" value="Ajouter">
        </form>
    </div>
    <div class="section">
        <h2>🔎 Rechercher par lettres</h2>
        <form method="GET" action="/rechercher">
            <input type="text" name="lettres" placeholder="Ex: ehcin" required>
            <input type="submit" value="Rechercher">
        </form>
        {% if resultats is not none %}
            <h3>Résultats pour "{{ tirage }}" :</h3>
            {% if resultats %}
                <ul>{% for mot in resultats %}<li><strong>{{ mot }}</strong></li>{% endfor %}</ul>
            {% else %}<p>Aucun anagramme trouvé.</p>{% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, resultats=None)

@app.route('/ajouter', methods=['POST'])
def ajouter():
    mot = request.form.get('nouveau_mot', '').strip().lower()
    msg = ""
    if mot:
        sig = generer_signature(mot)
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("INSERT INTO anagrammes (signature, mot) VALUES (%s, %s)", (sig, mot))
            conn.commit()
            msg = f"Le mot '{mot}' a bien été enregistré dans le cloud !"
        except psycopg2.errors.UniqueViolation:
            msg = f"Le mot '{mot}' existe déjà."
        finally:
            cur.close()
            conn.close()
    return render_template_string(HTML_PAGE, message=msg, resultats=None)

@app.route('/rechercher', methods=['GET'])
def rechercher():
    lettres = request.args.get('lettres', '').strip()
    sig = generer_signature(lettres)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT mot FROM anagrammes WHERE signature = %s", (sig,))
    resultats = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    return render_template_string(HTML_PAGE, resultats=resultats, tirage=lettres)

if __name__ == '__main__':
    if DATABASE_URL:
        initialiser_bdd()
    app.run(debug=True)
