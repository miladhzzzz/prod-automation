from hashlib import sha1
import hmac, os , sqlite3
from fastapi import HTTPException

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def verify_signature(payload: bytes, signature: str):
    if GITHUB_WEBHOOK_SECRET:
        secret = bytes(GITHUB_WEBHOOK_SECRET, "utf-8")
        hashed_payload = hmac.new(secret, payload, sha1).hexdigest()
        expected_signature = f"sha1={hashed_payload}"
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

def first_time_database_init(connection_pool):
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
                # Initialize database tables if they don't exist
            cur.execute('''CREATE TABLE IF NOT EXISTS projects 
                            (id INTEGER PRIMARY KEY, name TEXT UNIQUE, success_count INTEGER DEFAULT 0, failure_count INTEGER DEFAULT 0)''')

            cur.execute('''CREATE TABLE IF NOT EXISTS jobs 
                            (id TEXT PRIMARY KEY, project_id INTEGER, status TEXT, log_file TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(id))''')
            
            cur.execute('''CREATE TABLE IF NOT EXISTS project_environment_variables (
                            id INTEGER PRIMARY KEY,
                            project_name TEXT UNIQUE,
                            environment_variables TEXT)''')
            conn.commit()

    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")