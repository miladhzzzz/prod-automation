import hmac , os , json, subprocess ,logging , uvicorn, sqlite3, uuid, sentry_sdk
from hashlib import sha1
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict


sentry_sdk.init(
    dsn="https://4f856c3765722c946a61baf82463fd8a@o4503956234764288.ingest.sentry.io/4506832041017344",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,

    enable_tracing=True
)

app = FastAPI()

# Define a secret token to verify webhook requests from GitHub
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

# Configure logging
LOGS_DIR = "build_logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
logging.basicConfig(filename=os.path.join(LOGS_DIR, "builds.log"), level=logging.INFO, format="%(asctime)s - %(message)s")

# Create or connect to SQLite database
DB_FILE = "builds.db"
conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

# Initialize database tables if they don't exist
cur.execute('''CREATE TABLE IF NOT EXISTS projects 
               (id INTEGER PRIMARY KEY, name TEXT UNIQUE, success_count INTEGER DEFAULT 0, failure_count INTEGER DEFAULT 0)''')

cur.execute('''CREATE TABLE IF NOT EXISTS jobs 
               (id TEXT PRIMARY KEY, project_id INTEGER, status TEXT, log_file TEXT,
               FOREIGN KEY(project_id) REFERENCES projects(id))''')
conn.commit()

class Payload(BaseModel):
    repository: Optional[dict]

def verify_signature(payload: bytes, signature: str):
    if GITHUB_WEBHOOK_SECRET:
        secret = bytes(GITHUB_WEBHOOK_SECRET, "utf-8")
        hashed_payload = hmac.new(secret, payload, sha1).hexdigest()
        expected_signature = f"sha1={hashed_payload}"
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    event = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature")

    if not event or not signature:
        raise HTTPException(status_code=400, detail="Missing GitHub headers")

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if event == "push":
        # Verify the signature using the secret
        verify_signature(request.body(), signature)

        owner = payload["repository"]["owner"]["name"]
        repo = payload["repository"]["name"]
        project_name = repo
        log_file = f"{project_name}.log"
        repo_url = f"https://github.com/{owner}/{repo}.git"
        project_dir = os.path.abspath(os.path.join("projects", project_name))
        log_dir = os.path.abspath(os.path.join(LOGS_DIR, project_name))
        log_file_path = os.path.join(log_dir, log_file)
        job_id = uuid.uuid4().hex

        try:
            # Check if project already exists locally
            if os.path.exists(project_dir):
                subprocess.run(["git", "fetch"], cwd=project_dir, check=True)
            else:
                # Clone the repository if it doesn't exist
                subprocess.run(["git", "clone", repo_url, project_dir], check=True)
            
            # Create the log directory if it doesn't exist
            os.makedirs(log_dir, exist_ok=True)
            
            # Execute deployment in background task
            background_tasks.add_task(deploy_project_background, project_name, project_dir, log_file_path, job_id)
            
            # Log the job
            log_build_request(project_name, "started")
            
            # Provide immediate response to the user
            return {"message": f"Deployment started for {project_name}. Check status at /status/{job_id}"}
        
        except subprocess.CalledProcessError as e:
            print(f"Error deploying {project_name}: {e}")
            log_build_request(project_name, "failure")
            return {"message": f"Failed to deploy {project_name}"}
    
    return {"message": f"Ignored event: {event}"}



def log_build_request(project_name: str, status: str):
    conn = sqlite3.connect(DB_FILE)  # Establish connection
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO jobs (id, project_id, status, log_file) VALUES (?, ?, ?, ?)", 
                    (uuid.uuid4().hex, get_or_create_project_id(project_name), status, f"{project_name}.log"))
        conn.commit()
    finally:
        conn.close()  # Close the connection

def get_build_status(project_name: str) -> Dict[str, str]:
    # Check the status of the build process for a specific project
    cur.execute('''SELECT j.status, j.log_file 
                   FROM jobs j
                   JOIN projects p ON j.project_id = p.id
                   WHERE p.name=?''', (project_name,))
    row = cur.fetchone()
    if row:
        status = row[0]
        log_file = row[1]
        log_file_path = os.path.join(LOGS_DIR, project_name, log_file)
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as log:
                log_content = log.read()
            return {"status": status, "output": log_content}
        else:
            return {"status": "not_started", "output": f"Build log for {project_name} not available."}
    else:
        return {"status": "not_started", "output": f"No build record found for {project_name}."}


@app.get("/status/{project_name:path}")
async def show_build_status(project_name: str):
    # Return the status and output of the build process for a specific project
    status = get_build_status(project_name)
    return status

@app.get("/projects")
async def get_projects() -> List[str]:
    # Return the names of all projects for which build logs are available
    cur.execute("SELECT DISTINCT name FROM projects")
    projects = [row[0] for row in cur.fetchall()]
    return projects

@app.get("/jobs")
async def get_jobs() -> List[Dict[str, str]]:
    # Return the details of all jobs including project details
    cur.execute('''SELECT j.id, j.status, j.log_file, p.name as project_name, p.success_count, p.failure_count 
                   FROM jobs j
                   JOIN projects p ON j.project_id = p.id''')
    jobs = [{"id": row[0], "status": row[1], "log_file": row[2], "project_name": row[3], "success_count": row[4], "failure_count": row[5]} for row in cur.fetchall()]
    return jobs

@app.get("/deploy/{owner}/{repo}")
async def deploy_project(owner: str, repo: str, background_tasks: BackgroundTasks):
    project_name = repo
    log_file = f"{project_name}.log"
    repo_url = f"https://github.com/{owner}/{repo}.git"
    project_dir = os.path.abspath(os.path.join("projects", project_name))
    log_dir = os.path.abspath(os.path.join(LOGS_DIR, project_name))

    try:
        # Check if project already exists locally
        if os.path.exists(project_dir):
            subprocess.run(["git", "fetch"], cwd=project_dir, check=True)
        else:
            # Clone the repository if it doesn't exist
            subprocess.run(["git", "clone", repo_url, project_dir], check=True)
        
        # Create the log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Construct the log file path
        log_file_path = os.path.join(log_dir, log_file)
        
        # Execute deployment in background task
        background_tasks.add_task(deploy_project_background, project_name, project_dir, log_file_path)
        
        # Log the job
        log_build_request(project_name, "started")
        
        # Provide immediate response to the user
        return {"message": f"Deployment started for {project_name}. Check status at /status/{project_name}"}
    
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        log_build_request(project_name, "failure")
        return {"message": f"Failed to deploy {project_name}"}

def stop_and_remove_container(container_name: str):
    try:
        subprocess.run(["docker", "inspect", container_name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return

    subprocess.run(["docker", "stop", container_name], check=True)
    subprocess.run(["docker", "rm", container_name], check=True)

def deploy_project_background(project_name: str, project_dir: str, log_file_path: str):
    try:
        stop_and_remove_container(project_name)
        with open(log_file_path, "a") as log:
            subprocess.run(["docker", "build", "-t", project_name.lower(), project_dir], stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(["docker", "run", "-d", "--name", project_name, project_name.lower()])
        log_build_request(project_name, "success")
        update_project_counts(project_name, True)
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        log_build_request(project_name, "failure")
        update_project_counts(project_name, False)

def get_or_create_project_id(project_name: str) -> int:
    conn = sqlite3.connect(DB_FILE)  # Establish connection
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM projects WHERE name=?", (project_name,))
        row = cur.fetchone()
        if row:
            return row[0]
        else:
            cur.execute("INSERT INTO projects (name) VALUES (?)", (project_name,))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()  # Close the connection


def update_project_counts(project_name: str, success: bool):
    conn = sqlite3.connect(DB_FILE)  # Establish connection
    cur = conn.cursor()
    try:
        if success:
            cur.execute("UPDATE projects SET success_count = success_count + 1 WHERE name=?", (project_name,))
        else:
            cur.execute("UPDATE projects SET failure_count = failure_count + 1 WHERE name=?", (project_name,))
        conn.commit()
    finally:
        conn.close()  # Close the connection


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=1111)
