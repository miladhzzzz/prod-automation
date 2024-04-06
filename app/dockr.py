from typing import Optional, List, Dict
import subprocess, os, requests
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

def docker_restart_container(container_name: str):
    try:
        # Check if the container exists
        subprocess.run(["docker", "inspect", container_name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Check if the container was deployed using docker-compose
        compose_file_path = os.path.join("projects", container_name, "docker-compose.yml")

        if os.path.exists(compose_file_path):
            subprocess.run(["docker-compose", "-f", compose_file_path, "restart", container_name], check=True)
            print(f"Container {container_name} restarted successfully using docker-compose.")
        else:
            subprocess.run(["docker", "restart", container_name], check=True)
            print(f"Container {container_name} restarted successfully using docker run.")

    except subprocess.CalledProcessError as e:
        print(f"Error restarting container {container_name}: {e}")

def stop_and_remove_container(container_name: str):

    compose_file_path = os.path.join("projects", container_name, "docker-compose.yml")

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

# TODO: need to fix the dynamic image registry url in push command
def docker_push_images(registry_url: str = "registry:5000", project_name: str = None):
    try:
        images_output = subprocess.check_output(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]).decode("utf-8")
        images_list = images_output.strip().split("\n")
        last_three_images = images_list[-3:]
        
        if project_name is not None:
            project_images = [image for image in images_list if project_name.lower() in image]

            for image in project_images:
                # Tag the image with the registry URL and project name
                tagged_image = f"{registry_url}/{image}"
                subprocess.run(["docker", "tag", image, tagged_image], check=True)
                
                # Push the tagged image to the registry
                subprocess.run(["docker", "push", tagged_image], check=True)
                
                print(f"Image {tagged_image} pushed to {registry_url} successfully.")
        else:
            for image in last_three_images:
                # Tag the image with the registry URL
                tagged_image = f"{registry_url}/{image}"
                subprocess.run(["docker", "tag", image, tagged_image], check=True)

                # Push the tagged image to the registry
                subprocess.run(["docker", "push", tagged_image], check=True)
                print(f"Image {tagged_image} pushed to {registry_url} successfully.")

        
    except subprocess.CalledProcessError as e:
        print(f"Error pushing images to {registry_url}: {e}")

def deploy_docker_compose(project_name: str, compose_file_path: str, log_file_path: str, webhook: bool , commit_hash: str):
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

        # push build images to registry
        # docker_push_images(project_name=project_name)

        logs.log_build_request(project_name, "success", webhook, commit_hash)
        logs.update_project_counts(project_name, True)
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name} with Docker Compose: {e}")
        logs.log_build_request(project_name, "failure", webhook, commit_hash)
        logs.update_project_counts(project_name, False)

def deploy_docker_run(project_name: str, project_dir: str, log_file_path: str, exposed_ports: List[int], webhook: bool, commit_hash: str, envs:str = None):
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

        # push build images to registry
        # docker_push_images(project_name=project_name)
        
        logs.log_build_request(project_name, "success", webhook, commit_hash)
        logs.update_project_counts(project_name, True)  
    except subprocess.CalledProcessError as e:
        print(f"Error deploying {project_name}: {e}")
        logs.log_build_request(project_name, "failure", webhook, commit_hash)
        logs.update_project_counts(project_name, False)

def get_container_logs(container_name: str) -> Dict[str, str]:
    container_logs = {}

    logs_result = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
    
    if logs_result.returncode == 0:
        container_logs[container_name] = logs_result.stdout
    else:
        all_container_names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
        for name in all_container_names.stdout.splitlines():
            if container_name in name:
                logs_result = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
                if logs_result.returncode == 0:
                    container_logs[name] = logs_result.stdout

    return container_logs

def get_project_containers(project_name: str) -> List[Dict[str, str]]:
    container_info = []
    
    all_container_names = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True)
    for name in all_container_names.stdout.splitlines():
        if project_name.lower() in name:
            container_details = subprocess.run(["docker", "inspect", "--format='{{.State.Status}} {{.State.StartedAt}} {{.State.FinishedAt}}'", name], capture_output=True, text=True)
            details = container_details.stdout.strip().split()
            status = details[0]
            started_at = details[1]
            finished_at = details[2]
            
            container_info.append({
                "container_name": name,
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at
            })
    return container_info
