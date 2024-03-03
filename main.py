import hmac , os , json, subprocess ,logging , uvicorn, sqlite3, uuid, sentry_sdk
from hashlib import sha1
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from db import ConnectionPool

sentry_sdk.init(
    dsn="https://4f856c3765722c946a61baf82463fd8a@o4503956234764288.ingest.sentry.io/4506832041017344",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    enable_tracing=True
)

# initialize FastAPI
app = FastAPI()

# Initialize connection pool
connection_pool = ConnectionPool()

# Define a secret token to verify webhook requests from GitHub
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

# Configure logging
LOGS_DIR = "build_logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
logging.basicConfig(filename=os.path.join(LOGS_DIR, "builds.log"), level=logging.INFO, format="%(asctime)s - %(message)s")

class Payload(BaseModel):
    repository: Optional[dict]

# Logic / Global / Background functions
def first_time_database_init():
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
                # Initialize database tables if they don't exist
            cur.execute('''CREATE TABLE IF NOT EXISTS projects 
                            (id INTEGER PRIMARY KEY, name TEXT UNIQUE, success_count INTEGER DEFAULT 0, failure_count INTEGER DEFAULT 0)''')

            cur.execute('''CREATE TABLE IF NOT EXISTS jobs 
                            (id TEXT PRIMARY KEY, project_id INTEGER, status TEXT, log_file TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(id))''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")

    finally:
        conn.close()
    
def read_exposed_ports_from_dockerfile(dockerfile_path: str) -> List[int]:
    exposed_ports = []
    with open(dockerfile_path, "r") as dockerfile:
        for line in dockerfile:
            line = line.strip()
            if line.startswith("EXPOSE"):
                ports_str = line.split()[1]
                ports = ports_str.split()
                for port in ports:
                    try:
                        exposed_ports.append(int(port))
                    except ValueError:
                        print(f"Invalid port number: {port}")
    return exposed_ports

def verify_signature(payload: bytes, signature: str):
    if GITHUB_WEBHOOK_SECRET:
        secret = bytes(GITHUB_WEBHOOK_SECRET, "utf-8")
        hashed_payload = hmac.new(secret, payload, sha1).hexdigest()
        expected_signature = f"sha1={hashed_payload}"
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

def log_build_request(project_name: str, status: str):
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO jobs (id, project_id, status, log_file) VALUES (?, ?, ?, ?)", 
                        (uuid.uuid4().hex, get_or_create_project_id(project_name), status, f"{project_name}.log"))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")

    finally:
        conn.close()

def get_build_status(project_name: str) -> Dict[str, str]:
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
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
    except sqlite3.Error as e:
        print(f"Error retrieving build status: {e}")
    finally:
        conn.close()

def deploy_with_docker_compose(project_name: str, compose_file_path: str, log_file_path: str):
    try:
        # Check if there are existing containers for the project
        existing_containers = subprocess.run(["docker-compose", "-f", compose_file_path, "ps", "-q"], capture_output=True, text=True)
        if existing_containers.stdout:
            # Stop and remove existing containers for the project
            subprocess.run(["docker-compose", "-f", compose_file_path, "down"], check=True)

        # Build and start the services defined in the docker-compose file
        with open(log_file_path, "a") as log:
            subprocess.run(["docker-compose", "-f", compose_file_path, "up", "-d"], stdout=log, stderr=subprocess.STDOUT, check=True)

        log_build_request(project_name, "success")
        update_project_counts(project_name, True)
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name} with Docker Compose: {e}")
        log_build_request(project_name, "failure")
        update_project_counts(project_name, False)

def deploy_project_logic(owner: str, repo: str, background_tasks: BackgroundTasks):
    project_name = repo
    log_file = f"{project_name}.log"
    repo_url = f"https://github.com/{owner}/{repo}.git"
    project_dir = os.path.abspath(os.path.join("projects", project_name))
    log_dir = os.path.abspath(os.path.join(LOGS_DIR, project_name))
    log_file_path = os.path.join(log_dir, log_file)

    try:
        # Check if project already exists locally
        if os.path.exists(project_dir):
            subprocess.run(["git", "pull"], cwd=project_dir, check=True)
        else:
            # Clone the repository if it doesn't exist
            subprocess.run(["git", "clone", repo_url, project_dir], check=True)
        
        # Create the log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)

        # Check if Docker Compose file exists
        compose_file_path = os.path.join(project_dir, "docker-compose.yml")
        if compose_file_path and os.path.exists(compose_file_path):
            # Use docker-compose to deploy the project
            background_tasks.add_task(deploy_with_docker_compose, project_name, compose_file_path, log_file_path)
        else:
            # Read exposed ports from Dockerfile
            dockerfile_path = os.path.join(project_dir, "Dockerfile")
            exposed_ports = read_exposed_ports_from_dockerfile(dockerfile_path)

            # Execute deployment using Dockerfile
            background_tasks.add_task(deploy_project_background, project_name, project_dir, log_file_path, exposed_ports)

        # Log the job
        log_build_request(project_name, "started")
        
        # Provide immediate response to the user
        return {"message": f"Deployment started for {project_name}. Check status at /status/{project_name}"}
    
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        log_build_request(project_name, "failure")
        return {"message": f"Failed to deploy {project_name}"}

# HTTP REST API ENDPOINTS
@app.get("/status/{project_name:path}")
async def show_build_status(project_name: str):
    # Return the status and output of the build process for a specific project
    status = get_build_status(project_name)
    return status

@app.get("/projects")
async def get_projects() -> List[str]:
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
            # Return the names of all projects for which build logs are available
            cur.execute("SELECT DISTINCT name FROM projects")
            projects = [row[0] for row in cur.fetchall()]
            return projects
        
    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")
    finally:
        conn.close()

@app.get("/jobs")
async def get_jobs() -> List[Dict[str, str]]:

    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
            # Return the details of all jobs including project details
            cur.execute('''SELECT j.id, j.status, j.log_file, p.name as project_name, p.success_count, p.failure_count 
                        FROM jobs j
                        JOIN projects p ON j.project_id = p.id''')
            jobs = []
            for row in cur.fetchall():
                job = {
                    "id": row[0],
                    "status": row[1],
                    "log_file": row[2],
                    "project_name": row[3],
                    "success_count": str(row[4]),  # Convert to string
                    "failure_count": str(row[5])   # Convert to string
                }
                jobs.append(job)
            return jobs
        
    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")

    finally:
        conn.close()
    

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
        
        return deploy_project_logic(owner, repo, background_tasks)
    
    return {"message": f"Ignored event: {event}"}

@app.get("/deploy/{owner}/{repo}")
async def deploy_project(owner: str, repo: str, background_tasks: BackgroundTasks):
    return deploy_project_logic(owner, repo, background_tasks)

@app.get("/revert/{owner}/{repo}/{revert_type}")
async def revert_changes(
    owner: str ,
    repo: str ,
    revert_type: str ,
    background_tasks: BackgroundTasks
):
    if revert_type not in ["soft", "hard"]:
        return {"message": "Invalid revert type. Use 'soft' or 'hard'."}, 400
    
    # Logic to determine which type of revert to perform
    if revert_type == "soft":
        # Perform soft revert
        subprocess.run(["git", "revert", "--soft", "HEAD~1"], cwd=f"projects/{owner}/{repo}", check=True)
    else:
        # Perform hard revert
        subprocess.run(["git", "revert", "--hard", "HEAD~1"], cwd=f"projects/{owner}/{repo}", check=True)

    # Call deploy_project_logic to rebuild the project
    background_tasks.add_task(
        deploy_project_logic,
        owner,
        repo
    )
    
    # Return response indicating success or failure
    return {"message": f"Reverted changes for project {repo} with {revert_type} revert. Rebuilding..."}

@app.get("/stop/{project_name}")
async def stop_and_remove_containers(project_name: str):
    # Stop and remove containers associated with the project name
    try:
        # Run the function to stop and remove containers
        stop_and_remove_container(project_name)
        return {"message": f"Containers for project {project_name} stopped and removed successfully."}
    except Exception as e:
        return {"message": f"Failed to stop and remove containers for project {project_name}. Error: {str(e)}"}, 500

# Helper functions
def stop_and_remove_container(container_name: str):
    try:
        subprocess.run(["docker", "inspect", container_name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return

    subprocess.run(["docker", "stop", container_name], check=True)
    subprocess.run(["docker", "rm", container_name], check=True)

def deploy_project_background(project_name: str, project_dir: str, log_file_path: str, exposed_ports: List[int]):
    try:
        stop_and_remove_container(project_name)
        with open(log_file_path, "a") as log:
            subprocess.run(["docker", "build", "-t", project_name.lower(), project_dir], stdout=log, stderr=subprocess.STDOUT, check=True)
        
        # Construct the command to run the container
        run_command = ["docker", "run", "-d", "--name", project_name]
        
        # Add exposed ports to the run command
        if exposed_ports:
            for port in exposed_ports:
                run_command.extend(["-p", f"{port}:{port}"])
        
        # Add the image name
        run_command.append(project_name.lower())
        
        # Run the container
        subprocess.run(run_command)
        
        log_build_request(project_name, "success")
        update_project_counts(project_name, True)
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        log_build_request(project_name, "failure")
        update_project_counts(project_name, False)

def get_or_create_project_id(project_name: str) -> int:
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM projects WHERE name=?", (project_name,))
            row = cur.fetchone()
            if row:
                return row[0]
            else:
                cur.execute("INSERT INTO projects (name) VALUES (?)", (project_name,))
                conn.commit()
                return cur.lastrowid
            
    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")
    finally:
        conn.close()

def update_project_counts(project_name: str, success: bool):
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
        if success:
            cur.execute("UPDATE projects SET success_count = success_count + 1 WHERE name=?", (project_name,))
        else:
            cur.execute("UPDATE projects SET failure_count = failure_count + 1 WHERE name=?", (project_name,))
        conn.commit()

    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    
    first_time_database_init()
    uvicorn.run("main:app", host="0.0.0.0", port=1111)