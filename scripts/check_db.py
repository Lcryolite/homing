from openemail.storage.database import db

db.connect()
v = db.fetchone("SELECT MAX(version) as v FROM schema_version")
print("Schema version:", v["v"])
cols = db.fetchall("PRAGMA table_info(accounts)")
names = [c["name"] for c in cols]
print("Accounts columns:", names)
print("Has password_enc:", "password_enc" in names)
print("Has oauth_token_enc:", "oauth_token_enc" in names)
print("Has oauth_refresh_enc:", "oauth_refresh_enc" in names)
db.close()
