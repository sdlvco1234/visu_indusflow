from pysqlcipher3 import dbapi2 as sqlite
import os
from dotenv import load_dotenv

load_dotenv(".env")
SOURCE_DB = "data/base.db"
ENCRYPTED_DB = "data/database_encrypted.sqlite"

KEY = os.environ.get("SECRET_KEY")


conn = sqlite.connect(ENCRYPTED_DB)

conn.execute(
    f"PRAGMA key ='{KEY}'"
)

tables = conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
""").fetchall()

print("Tables :")

for table in tables:
    print(" -", table[0])

conn.close()