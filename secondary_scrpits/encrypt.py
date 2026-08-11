from pysqlcipher3 import dbapi2 as sqlite
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv(".env")
SOURCE_DB = "data/base.db"
ENCRYPTED_DB = "data/database_encrypted.sqlite"



KEY = os.environ.get("SECRET_KEY")

# Connexion à la base SQLite originale
conn = sqlite.connect(SOURCE_DB)

# Création de la base chiffrée
conn.execute(
    f"ATTACH DATABASE '{ENCRYPTED_DB}' AS encrypted KEY '{KEY}'"
)

# Copie complète de la base vers la base chiffrée
conn.execute("SELECT sqlcipher_export('encrypted')")

# Fermeture de la connexion
conn.execute("DETACH DATABASE encrypted")
conn.close()

print(f"Base chiffrée créée : {ENCRYPTED_DB}")