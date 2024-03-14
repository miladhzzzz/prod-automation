from db import ConnectionPool
from typing import Optional, List, Dict
import sqlite3, uuid, os

LOGS_DIR = "build_logs"

connection_pool = ConnectionPool()

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

def get_env_vars(project_name):
    try:
        # Retrieve encrypted environment variables from the database
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT variable_name, variable_value FROM project_environment_variables WHERE project_name = ?",
                (project_name,)
            )
            records = cursor.fetchall()

        # if records:
        #     # Decrypt the encrypted values and return the decrypted environment variables
        #     decrypted_variables = {record[0]: decrypt_data(record[1]) for record in records}
        #     return decrypted_variables
              
        return None
    except sqlite3.Error as e:
        raise "Error retrieving environment variables: {e}"