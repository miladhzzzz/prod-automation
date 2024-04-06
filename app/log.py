from db import ConnectionPool
from typing import Optional, List, Dict
import sqlite3, uuid, os, dockr, json

LOGS_DIR = "build_logs"

connection_pool = ConnectionPool()

def log_build_request(project_name: str, status: str, webhook: bool, commit_hash: str):
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
            if webhook:
                trigger = "webhook"
            else:
                trigger = "manual"   
            cur.execute("INSERT INTO jobs (id, project_id, status, commit_hash, trigger, log_file) VALUES (?, ?, ?, ?, ?, ?)", 
                        (uuid.uuid4().hex, get_or_create_project_id(project_name), status, commit_hash, trigger,f"{project_name}.log"))
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

def get_jobs():
    try:
        with connection_pool.get_connection() as conn:
            cur = conn.cursor()
            # Return the details of all jobs including project details
            cur.execute('''SELECT j.id, j.status, j.commit_hash, j.trigger, j.log_file, p.name as project_name, p.success_count, p.failure_count 
                        FROM jobs j
                        JOIN projects p ON j.project_id = p.id''')
            jobs = []
            for row in cur.fetchall():
                # Get container data associated with the project name
                container_data = dockr.get_project_containers(row[5])

                job = {
                    "id": row[0],
                    "status": row[1],
                    "commit_hash": row[2],
                    "trigger": row[3],
                    "log_file": row[4],
                    "project_name": row[5],
                    "success_count": str(row[6]),  # Convert to string
                    "failure_count": str(row[7])   # Convert to string
                }

                if row[1] == "success" and container_data:
                    job["containers"] = json.dumps(container_data)
                
                if row[1] == "failed" and container_data:
                    for container in container_data:
                        if container.get("status") == "exited":
                            container_logs = dockr.get_container_logs(row[5])
                            job["container_name"] = container.get("name")
                            job["container_status"] = container.get("status")
                            job["container_logs"] = container_logs

                jobs.append(job)
            return jobs
        
    except sqlite3.Error as e:
        print(f"Error logging build request: {e}")