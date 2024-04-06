import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

owner = "miladhzzzz"
repo = "Power-DNS"

def test_set_vault_secrets():
    variables = {"key1": "value1", "key2": "value2"}
    response = client.post(f"/vault/{repo}", json=variables)  
    assert response.status_code == 200
    assert response.json() == {"message": "Environment variables set successfully"}

def test_deploy_project():
    response = client.get(f"/deploy/{owner}/{repo}")
    assert response.status_code == 200
    assert response.json()["message"] == f"Deployment started for {repo}. Check status at /status/{repo}"

def test_get_projects():
    response = client.get("/projects")
    assert response.status_code == 200
    assert response.json() is not None

def test_get_projects_status():
    response = client.get(f"/status/{repo}")
    assert response.status_code == 200
    assert response.json() is not None

def test_get_jobs():
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() is not None

def test_revert_changes():
    response = client.get(f"/revert/{owner}/{repo}")
    assert response.status_code == 200
    assert f"Reverted changes for project {repo}. Rebuilding..." in response.json()["message"]

# >>>>>>!!!! IF YOU WANT TO test THE CONTAINER MANAGEMENT MAKE SURE YOU HAVE ALL THE COMPONENTS UP AND RUNNING!!!!!<<<<<

# @pytest.mark.parametrize("action", ["log", "restart", "stop"])
# def test_container_management( action):
#     response = client.get(f"/docker/{action}/{repo}")
#     assert response.status_code == 200
#     if action == "stop":
#         assert f"Containers for project {repo} stopped and removed successfully." in response.json()["message"]
#     elif action == "restart":
#         assert f"Containers for project {repo} restarted successfully." in response.json()["message"]
#     elif action == "log":
#         assert "Containers logs:" in response.json()["message"]
#     else:
#         assert "use approporiate Actions" in response.json()["message"]
