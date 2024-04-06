import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

owner = "miladhzzzz"
repo = "Power-DNS"

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

def test_revert_changes(revert_type="soft"):
    response = client.get(f"/revert/{owner}/{repo}/{revert_type}")
    assert response.status_code == 200
    assert f"Reverted changes for project {repo} with {revert_type} revert. Rebuilding..." in response.json()["message"]

@pytest.mark.parametrize("action", ["log", "restart", "stop"])
def test_container_management( action):
    response = client.get(f"/docker/{action}/{repo}")
    assert response.status_code == 200
    if action == "stop":
        assert f"Containers for project {repo} stopped and removed successfully." in response.json()["message"]
    elif action == "restart":
        assert f"Containers for project {repo} restarted successfully." in response.json()["message"]
    elif action == "log":
        assert "Containers logs:" in response.json()["message"]
    else:
        assert "use approporiate Actions" in response.json()["message"]
