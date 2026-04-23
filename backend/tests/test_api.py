"""Tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline


class TestAuthAPI:
    """Tests for authentication API endpoints"""

    def test_login_success(self, client: TestClient, test_user: User):
        """Successful login should return token"""
        response = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "testpassword123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["username"] == "testuser"
        assert "session_token" in data

    def test_login_wrong_password(self, client: TestClient, test_user: User):
        """Wrong password should return 401"""
        response = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    def test_login_nonexistent_user(self, client: TestClient):
        """Non-existent user should return 401"""
        response = client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "password"}
        )

        assert response.status_code == 401

    def test_get_current_user(self, client: TestClient, auth_headers: dict):
        """Should get current user info"""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"

    def test_get_current_user_unauthorized(self, client: TestClient):
        """Unauthorized request should return 401"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_logout(self, client: TestClient, auth_headers: dict):
        """Logout should succeed"""
        response = client.post("/api/auth/logout", headers=auth_headers)
        assert response.status_code == 200


class TestProjectsAPI:
    """Tests for projects API endpoints"""

    def test_list_projects_empty(self, client: TestClient, auth_headers: dict):
        """Should return empty list for new user"""
        response = client.get("/api/projects/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["projects"] == []

    def test_create_project(self, client: TestClient, auth_headers: dict, db: Session):
        """Should create a new project"""
        response = client.post(
            "/api/projects/",
            json={"name": "Test Novel", "target_words": 50000},
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Novel"
        assert data["target_words"] == 50000
        assert data["stage"] == "inspiration_collecting"

        # Verify outline was created
        outline = db.query(Outline).filter(Outline.project_id == data["id"]).first()
        assert outline is not None

    def test_create_project_name_required(self, client: TestClient, auth_headers: dict):
        """Should require project name"""
        response = client.post(
            "/api/projects/",
            json={"target_words": 50000},
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_get_project(self, client: TestClient, auth_headers: dict):
        """Should get project details"""
        # Create project first
        create_response = client.post(
            "/api/projects/",
            json={"name": "Test Novel"},
            headers=auth_headers
        )
        project_id = create_response.json()["id"]

        # Get project
        response = client.get(f"/api/projects/{project_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Novel"

    def test_get_nonexistent_project(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent project"""
        response = client.get("/api/projects/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_project(self, client: TestClient, auth_headers: dict):
        """Should update project"""
        # Create project
        create_response = client.post(
            "/api/projects/",
            json={"name": "Original Name"},
            headers=auth_headers
        )
        project_id = create_response.json()["id"]

        # Update project
        response = client.put(
            f"/api/projects/{project_id}",
            json={"name": "Updated Name"},
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_delete_project(self, client: TestClient, auth_headers: dict):
        """Should delete project"""
        # Create project
        create_response = client.post(
            "/api/projects/",
            json={"name": "To Delete"},
            headers=auth_headers
        )
        project_id = create_response.json()["id"]

        # Delete project
        response = client.delete(f"/api/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify deleted
        get_response = client.get(f"/api/projects/{project_id}", headers=auth_headers)
        assert get_response.status_code == 404

    def test_unauthorized_access(self, client: TestClient):
        """Should reject unauthorized access"""
        response = client.get("/api/projects/")
        assert response.status_code == 401


class TestOutlineAPI:
    """Tests for outline API endpoints"""

    @pytest.fixture
    def project_with_outline(self, client: TestClient, auth_headers: dict) -> int:
        """Create a project and return its ID"""
        response = client.post(
            "/api/projects/",
            json={"name": "Test Novel"},
            headers=auth_headers
        )
        return response.json()["id"]

    def test_get_outline(self, client: TestClient, auth_headers: dict, project_with_outline: int):
        """Should get outline for project"""
        response = client.get(
            f"/api/projects/{project_with_outline}/outline",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_with_outline
        assert data["confirmed"] is False

    def test_update_outline(self, client: TestClient, auth_headers: dict, project_with_outline: int):
        """Should update outline"""
        # v0.6.1: plot_points 使用增强的字典格式
        response = client.put(
            f"/api/projects/{project_with_outline}/outline",
            json={
                "title": "My Novel",
                "summary": "A great story",
                "plot_points": [
                    {"order": 1, "event": "Beginning"},
                    {"order": 2, "event": "Middle"},
                    {"order": 3, "event": "End"}
                ]
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "My Novel"
        assert data["summary"] == "A great story"

    def test_confirm_outline(self, client: TestClient, auth_headers: dict, project_with_outline: int):
        """Should confirm outline"""
        # Update outline first
        client.put(
            f"/api/projects/{project_with_outline}/outline",
            json={"title": "My Novel", "summary": "A story"},
            headers=auth_headers
        )

        # Confirm
        response = client.post(
            f"/api/projects/{project_with_outline}/outline/confirm",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["confirmed"] is True

    def test_confirm_outline_without_title(self, client: TestClient, auth_headers: dict, project_with_outline: int):
        """Should not confirm outline without title"""
        response = client.post(
            f"/api/projects/{project_with_outline}/outline/confirm",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "title" in response.json()["detail"].lower()


class TestSettingsAPI:
    """Tests for settings API endpoints"""

    def test_get_settings(self, client: TestClient, auth_headers: dict):
        """Should get user settings"""
        response = client.get("/api/settings/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "model_provider" in data
        assert "review_enabled" in data
        assert data["has_api_key"] is False

    def test_update_settings(self, client: TestClient, auth_headers: dict):
        """Should update user settings"""
        response = client.put(
            "/api/settings/",
            json={
                "model_provider": "openai",
                "review_enabled": False,
                "review_strictness": "loose"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model_provider"] == "openai"
        assert data["review_enabled"] is False

    def test_update_settings_with_api_key(self, client: TestClient, auth_headers: dict):
        """Should encrypt and store API key"""
        response = client.put(
            "/api/settings/",
            json={"api_key": "sk-test-key-12345"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_api_key"] is True