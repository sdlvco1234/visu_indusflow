import os
from dotenv import load_dotenv
from pysqlcipher3 import dbapi2 as sqlite

load_dotenv(".env")

DB_PATH = "data/database_encrypted.sqlite"
KEY = "3ff8070761f0abdcf0323f868952a214f9b4a60207504d29befd396bb9ad2be4"

conn = sqlite.connect(DB_PATH)

conn.execute(f'PRAGMA key = "x\{KEY}\'"')

result = conn.execute(
    "SELECT count(*) FROM sqlite_master"
).fetchone()

print("Connexion SQLCipher OK")
print("Nombre d'objets :", result[0])

conn.close()