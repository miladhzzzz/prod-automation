from hashlib import sha1
import hmac, os , sqlite3, socket
from fastapi import HTTPException

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def set_project_env(envs):

    for key, value in envs.items():
        os.environ[key] = value
        print(f"set key as : {key}")
    
def get_vault_secrets(project_name: str, connection_pool, crypt):
    env_variables = {}

    try:
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT variable_name, variable_value FROM project_environment_variables WHERE project_name = ?",
                (project_name,)
            )
            rows = cursor.fetchall()

            for row in rows:
                variable_name = row[0]
                encrypted_value = row[1]
                decrypted_value = crypt.de(encrypted_value)  # Decrypt the value
                env_variables[variable_name] = decrypted_value

    except sqlite3.Error as e:
        # Handle the error as needed
        print(f"Error retrieving environment variables: {e}")

    return env_variables

def get_container_ip():

    # Get the container's hostname
    hostname = socket.gethostname()

    # Get the container's IP address
    container_ip = socket.gethostbyname(hostname)

    return container_ip

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
                            (id TEXT PRIMARY KEY, project_id INTEGER, status TEXT, commit_hash TEXT, trigger TEXT, log_file TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(id))''')
            
            cur.execute('''CREATE TABLE IF NOT EXISTS project_environment_variables (
                            id INTEGER PRIMARY KEY,
                            project_name TEXT,
                            variable_name TEXT,
                            variable_value TEXT)''')
            conn.commit()

    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")

def is_valid_kubeconfig(config_content: str) -> bool:
    # Perform basic validation by checking for common kubeconfig keywords
    required_keywords = ["apiVersion", "kind", "clusters", "users", "contexts"]
    for keyword in required_keywords:
        if keyword not in config_content:
            return False
    return True