import os , json, subprocess ,logging , uvicorn, sqlite3, sentry_sdk
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from db import ConnectionPool
import dockr , log , helpers

sentry_sdk.init(
    dsn="https://4f856c3765722c946a61baf82463fd8a@o4503956234764288.ingest.sentry.io/4506832041017344",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    enable_tracing=True
)

# initialize FastAPI
app = FastAPI(docs_url=None, redoc_url=None, openapi_url= None)

# Initialize connection pool
connection_pool = ConnectionPool()

# Configure logging
LOGS_DIR = "build_logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
logging.basicConfig(filename=os.path.join(LOGS_DIR, "builds.log"), level=logging.INFO, format="%(asctime)s - %(message)s")

class Payload(BaseModel):
    repository: Optional[dict]

class EnvironmentVariables(BaseModel):
    key: str
    value: str

# Logic / Global / Background functions
    
def deploy_project_logic(owner: str, repo: str, background_tasks: BackgroundTasks , envs:str = None ):
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
            background_tasks.add_task(dockr.deploy_docker_compose, project_name, compose_file_path, log_file_path)
        else:
            # Read exposed ports from Dockerfile
            dockerfile_path = os.path.join(project_dir, "Dockerfile")
            exposed_ports = dockr.read_exposed_ports_from_dockerfile(dockerfile_path)

            # Execute deployment using Dockerfile
            background_tasks.add_task(dockr.deploy_docker_run, project_name, project_dir, log_file_path, exposed_ports, envs)

        # Log the job
        log.log_build_request(project_name, "started")
        
        # Provide immediate response to the user
        return {"message": f"Deployment started for {project_name}. Check status at /status/{project_name}"}
    
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        log.log_build_request(project_name, "failure")
        return {"message": f"Failed to deploy {project_name}"}

# HTTP REST API ENDPOINTS
@app.get("/status/{project_name:path}")
async def show_build_status(project_name: str):
    # Return the status and output of the build process for a specific project
    status = log.get_build_status(project_name)
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
        helpers.verify_signature(request.body(), signature)

        owner = payload["repository"]["owner"]["name"]
        repo = payload["repository"]["name"]
        
        return deploy_project_logic(owner, repo, background_tasks)
    
    return {"message": f"Ignored event: {event}"}

@app.get("/deploy/{owner}/{repo}")
async def deploy_project(owner: str, repo: str, background_tasks: BackgroundTasks):
    return deploy_project_logic(owner, repo, background_tasks)

@app.post("/deploy")
async def deploy_with_env(
    owner: str,
    repo: str,
    env_vars: List[EnvironmentVariables],
    background_tasks: BackgroundTasks
):
    # Build environment variables string in format "key1=value1 key2=value2 ..."
    env_string = " ".join([f"{var.key}={var.value}" for var in env_vars])

    # Run the container with environment variables using Docker command
    return deploy_project_logic(owner, repo, background_tasks, env_string)

# TODO : needs fixing
@app.post("/set_env/{project_name}")
async def set_environment_variables(project_name: str, variables: dict):
    try:
        # Encrypt and store each environment variable in the database
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            for key, value in variables.items():
                encrypted_value = "encrypt_data(value)"
                cursor.execute(
                    "INSERT OR REPLACE INTO project_environment_variables (project_name, variable_name, variable_value) VALUES (?, ?, ?)",
                    (project_name, key, encrypted_value)
                )
            conn.commit()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error setting environment variables: {e}")
    
    return {"message": "Environment variables set successfully"}

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
        dockr.stop_and_remove_container(project_name)
        return {"message": f"Containers for project {project_name} stopped and removed successfully."}
    except Exception as e:
        return {"message": f"Failed to stop and remove containers for project {project_name}. Error: {str(e)}"}, 500

if __name__ == "__main__":
    helpers.first_time_database_init(connection_pool)
    container_ip = helpers.get_container_ip()
    uvicorn.run("main:app", host=container_ip, port=1111)