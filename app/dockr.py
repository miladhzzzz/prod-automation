from typing import Optional, List, Dict
import subprocess, os
import log as logs

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

def stop_and_remove_container(container_name: str):
    project_dir = os.path.abspath(os.path.join("projects", container_name))
    compose_file_path = os.path.join(project_dir, "docker-compose.yml")

    if os.path.exists(compose_file_path):
        try:
            existing_containers = subprocess.run(["docker-compose", "-f", compose_file_path, "ps", "-q"], capture_output=True, text=True)
            if existing_containers.stdout:
                subprocess.run(["docker-compose", "-f", compose_file_path, "down"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error stopping and removing containers for {container_name} with docker-compose: {e}")
            return

    try:
        subprocess.run(["docker", "inspect", container_name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print(f"Container {container_name} not found.")
        return

    try:
        subprocess.run(["docker", "stop", container_name], check=True)
        subprocess.run(["docker", "rm", container_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error stopping and removing container {container_name} with docker: {e}")

def deploy_docker_compose(project_name: str, compose_file_path: str, log_file_path: str):
    try:
        # Check if there are existing containers for the project
        existing_containers = subprocess.run(["docker-compose", "-f", compose_file_path, "ps", "-q"], capture_output=True, text=True)
        if existing_containers.stdout:
            # Stop and remove existing containers for the project
            subprocess.run(["docker-compose", "-f", compose_file_path, "down"], check=True)

        # Build and start the services defined in the docker-compose file
        with open(log_file_path, "a") as log:
            subprocess.run(["docker-compose", "-f", compose_file_path, "build"], stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(["docker-compose", "-f", compose_file_path, "up", "-d"], stdout=log, stderr=subprocess.STDOUT, check=True)

        logs.log_build_request(project_name, "success")
        logs.update_project_counts(project_name, True)
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name} with Docker Compose: {e}")
        logs.log_build_request(project_name, "failure")
        logs.update_project_counts(project_name, False)

def deploy_docker_run(project_name: str, project_dir: str, log_file_path: str, exposed_ports: List[int], envs:str = None):
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

        if envs:
            run_command.extend(["-e", f"{envs}"])

        # Add the image name
        run_command.append(project_name.lower())
        
        # Run the container
        subprocess.run(run_command)
        
        logs.log_build_request(project_name, "success")
        logs.update_project_counts(project_name, True)  
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        logs.log_build_request(project_name, "failure")
        logs.update_project_counts(project_name, False)
