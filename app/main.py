import os , json, subprocess ,logging , uvicorn, sqlite3, sentry_sdk, requests
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from db import ConnectionPool
from encrypt import Encryptor
import dockr , log , helpers

sentry_sdk.init(
    dsn="https://4f856c3765722c946a61baf82463fd8a@o4503956234764288.ingest.sentry.io/4506832041017344",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    enable_tracing=True
)

# initilize cryptography
crypt = Encryptor()

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

class ConfigPayload(BaseModel):
    config: str
# Logic / Global / Background functions
    
def deploy_project_logic(owner: str, repo: str, background_tasks: BackgroundTasks, webhook = False, revert = False, commit_hash = ""):
    project_name = repo
    log_file = f"{project_name}.log"
    repo_url = f"https://github.com/{owner}/{repo}.git"
    project_dir = os.path.abspath(os.path.join("projects", project_name))
    log_dir = os.path.abspath(os.path.join(LOGS_DIR, project_name))
    log_file_path = os.path.join(log_dir, log_file)
    project_envs = helpers.get_vault_secrets(project_name, connection_pool, crypt)

    try:
        # Check if project already exists locally
        if os.path.exists(project_dir):
            if not revert:
                subprocess.run(["git", "pull"], cwd=project_dir, check=True)
                # If revert is True, Do Nothing!
        else:
            # Clone the repository if it doesn't exist
            subprocess.run(["git", "clone", repo_url, project_dir], check=True)
        
        # Create the log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)

        # Get the Current Commit information
        if commit_hash == "":
            result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_dir, stdout=subprocess.PIPE, text=True)
            commit_hash = result.stdout.strip()

        # Check if Docker Compose file exists
        compose_file_path = os.path.join(project_dir, "docker-compose.yml")
        if compose_file_path and os.path.exists(compose_file_path):

            # check if the project has any ENV variables and set them before deployment
            if project_envs:
                background_tasks.add_task(helpers.set_project_env, project_envs)

            # Use docker-compose to deploy the project
            background_tasks.add_task(dockr.deploy_docker_compose, project_name, compose_file_path, log_file_path, webhook, commit_hash)
        else:
            # Read exposed ports from Dockerfile
            dockerfile_path = os.path.join(project_dir, "Dockerfile")
            exposed_ports = dockr.read_exposed_ports_from_dockerfile(dockerfile_path)

            if project_envs:
                # convert the dictionary to a string
                envs_str = ' '.join([f'{key}={value}' for key, value in project_envs.items()])
            else :
                envs_str = ""

            # Execute deployment using Dockerfile
            background_tasks.add_task(dockr.deploy_docker_run, project_name, project_dir, log_file_path, exposed_ports, webhook , commit_hash, envs=envs_str)
        
        # Provide immediate response to the user
        return {"message": f"Deployment started for {project_name}. Check status at /status/{project_name}"}
    
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        log.log_build_request(project_name, "failure", webhook, commit_hash)
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
    return log.get_jobs()

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

        owner = payload["repository"]["owner"]["login"]
        repo = payload["repository"]["name"]
        commit_hash = payload["commits"][-1]["id"]
        
        return deploy_project_logic(owner, repo, background_tasks, webhook=True, revert=False, commit_hash=commit_hash)
    
    return {"message": f"Ignored event: {event}"}

@app.get("/deploy/{owner}/{repo}")
async def deploy_project(owner: str, repo: str, background_tasks: BackgroundTasks):
    return deploy_project_logic(owner, repo, background_tasks)

@app.post("/kubeconfig")
async def kubectl_config(file: UploadFile = File(...)):
    try:
        # Validate kubeconfig
        kubeconfig_content = await file.read()
        if not helpers.is_valid_kubeconfig(kubeconfig_content.decode()):
            raise HTTPException(status_code=422, detail="Invalid kubeconfig content provided.")

        # Check if continuous integration is reachable
        if requests.get("http://kube-o-matic:8555/").status_code != 200:
            raise HTTPException(status_code=503, detail="Continuous integration is not reachable or running. Make sure you use 'make cd' in your root dir to set this up!")

        cd_url = "http://kube-o-matic:8555/"

        # Prepare file data
        files = {"file": (file.filename, kubeconfig_content, "application/octet-stream")}

        # Send kubeconfig as file
        r = requests.post(cd_url + "upload", files=files)

        # Check if the request was successful
        r.raise_for_status()

        return {"message": "Kubeconfig content saved successfully."}

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error occurred while communicating with the server: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")    
    
@app.post("/vault/{project_name}")
async def set_vault_secrets(project_name: str, request: Request):
    variables = await request.json()
    
    try:
        # Encrypt and store each environment variable in the database
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            for key, value in variables.items():
                encrypted_value = crypt.en(value)
                
                # Try to update the existing variable
                cursor.execute(
                    "UPDATE project_environment_variables SET variable_value = ? WHERE project_name = ? AND variable_name = ?",
                    (encrypted_value, project_name, key)
                )
                
                # If no rows were affected by the update, insert a new record
                if cursor.rowcount == 0:
                    cursor.execute(
                        "INSERT INTO project_environment_variables (project_name, variable_name, variable_value) VALUES (?, ?, ?)",
                        (project_name, key, encrypted_value)
                    )
                    
            conn.commit()
            
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error setting environment variables: {e}")
    
    return {"message": "Environment variables set successfully"}

@app.get("/revert/{owner}/{repo}")
async def revert_changes(
    owner: str ,
    repo: str ,
    background_tasks: BackgroundTasks
):
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD^"], cwd=f"projects/{repo}", check=True)
    except Exception as e:
            return {"message": f"Failed to git reset {repo}. Error: {str(e)}"}, 500

    # Call deploy_project_logic to rebuild the project
    background_tasks.add_task(deploy_project_logic, owner, repo ,background_tasks, revert=True)
    
    # Return response indicating success or failure
    return {"message": f"Reverted changes for project {repo}. Rebuilding..."}

@app.get("/docker/{action}/{project_name}")
async def container_management(project_name: str, action:str):
# Stop and remove containers associated with the project name
    if action == "stop":
        try:
            dockr.stop_and_remove_container(project_name)
            return {"message": f"Containers for project {project_name} stopped and removed successfully."}
        
        except Exception as e:
            return {"message": f"Failed to stop and remove containers for project {project_name}. Error: {str(e)}"}, 500
        
    elif action == "restart":
        try:
            dockr.docker_restart_container(project_name)
            return {"message": f"Containers for project {project_name} restarted successfully."}
        
        except Exception as e:
            return {"message": f"Failed to restart containers for project {project_name}. Error: {str(e)}"}, 500
        
    elif action == "log":
        try:
            logs = dockr.get_container_logs(project_name)
            if logs:
                return {"message": f"Containers logs: {logs}."}
            else:
                return {"message": f"No Container Logs found for {project_name}"}
        
        except Exception as e:
            return {"message": f"Failed to restart containers for project {project_name}. Error: {str(e)}"}, 500
        
    else:
        return {"message": "use approporiate Actions : stop , restart , log"}

if __name__ == "__main__":
    helpers.first_time_database_init(connection_pool)
    container_ip = helpers.get_container_ip()
    uvicorn.run("main:app", host=container_ip, port=1111)