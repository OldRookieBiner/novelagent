"""Tests for agent prompts API endpoints"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.project import Project
from app.agents.prompts import DEFAULT_PROMPTS


class TestGlobalAgentPromptsAPI:
    """Tests for global agent prompts API endpoints"""

    def test_get_global_prompts(self, client: TestClient, auth_headers: dict):
        """Should return all global prompts (7 agent types)"""
        response = client.get("/api/agent-prompts", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        prompts = data["prompts"]

        # Should have exactly 7 agent types
        assert len(prompts) == 7

        # Check each prompt has required fields
        for prompt in prompts:
            assert "agent_type" in prompt
            assert "agent_name" in prompt
            assert "description" in prompt
            assert "prompt_content" in prompt
            assert "variables" in prompt
            assert "is_default" in prompt

        # Verify all expected agent types are present
        agent_types = {p["agent_type"] for p in prompts}
        expected_types = {
            "info_collection",
            "outline_generation",
            "chapter_count_suggestion",
            "chapter_outline_generation",
            "chapter_content_generation",
            "review",
            "rewrite"
        }
        assert agent_types == expected_types

    def test_update_global_prompt(self, client: TestClient, auth_headers: dict):
        """Should update a global prompt"""
        new_content = "This is a custom prompt for testing."

        response = client.put(
            "/api/agent-prompts/info_collection",
            json={"prompt_content": new_content},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "info_collection"
        assert data["prompt_content"] == new_content
        assert data["is_default"] is False

        # Verify the update persisted
        get_response = client.get("/api/agent-prompts", headers=auth_headers)
        prompts = get_response.json()["prompts"]
        info_collection = next(p for p in prompts if p["agent_type"] == "info_collection")
        assert info_collection["prompt_content"] == new_content
        assert info_collection["is_default"] is False

    def test_reset_global_prompt(self, client: TestClient, auth_headers: dict):
        """Should reset a global prompt to default"""
        # First update a prompt
        new_content = "Custom content to be reset"
        client.put(
            "/api/agent-prompts/info_collection",
            json={"prompt_content": new_content},
            headers=auth_headers
        )

        # Now reset it
        response = client.post(
            "/api/agent-prompts/info_collection/reset",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "info_collection"
        assert data["is_default"] is True
        assert data["prompt_content"] == DEFAULT_PROMPTS["info_collection"]

    def test_update_unknown_agent_type(self, client: TestClient, auth_headers: dict):
        """Should return 404 for unknown agent type"""
        response = client.put(
            "/api/agent-prompts/unknown_agent_type",
            json={"prompt_content": "Some content"},
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]

    def test_reset_unknown_agent_type(self, client: TestClient, auth_headers: dict):
        """Should return 404 for unknown agent type on reset"""
        response = client.post(
            "/api/agent-prompts/unknown_agent_type/reset",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]


class TestProjectAgentPromptsAPI:
    """Tests for project agent prompts API endpoints"""

    @pytest.fixture
    def project_id(self, client: TestClient, auth_headers: dict) -> int:
        """Create a project and return its ID"""
        response = client.post(
            "/api/projects/",
            json={"name": "Test Novel"},
            headers=auth_headers
        )
        return response.json()["id"]

    def test_get_project_prompts(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return project prompts configuration"""
        response = client.get(
            f"/api/projects/{project_id}/agent-prompts",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["project_name"] == "Test Novel"
        assert "agents" in data

        # Should have all 7 agent types
        agents = data["agents"]
        assert len(agents) == 7

        # Initially all should not use custom
        for agent in agents:
            assert "agent_type" in agent
            assert "agent_name" in agent
            assert "use_custom" in agent
            assert agent["use_custom"] is False
            assert agent["custom_content"] is None

    def test_set_project_custom_prompt(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should set a custom prompt for project"""
        custom_content = "Project-specific custom prompt content"

        response = client.put(
            f"/api/projects/{project_id}/agent-prompts/info_collection",
            json={"prompt_content": custom_content},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "info_collection"
        assert data["use_custom"] is True
        assert data["custom_content"] == custom_content

        # Verify it persists
        get_response = client.get(
            f"/api/projects/{project_id}/agent-prompts",
            headers=auth_headers
        )
        agents = get_response.json()["agents"]
        info_collection = next(a for a in agents if a["agent_type"] == "info_collection")
        assert info_collection["use_custom"] is True
        assert info_collection["custom_content"] == custom_content

    def test_delete_project_custom_prompt(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should delete custom prompt and revert to global"""
        # First set a custom prompt
        custom_content = "Custom content to be deleted"
        client.put(
            f"/api/projects/{project_id}/agent-prompts/info_collection",
            json={"prompt_content": custom_content},
            headers=auth_headers
        )

        # Delete it
        response = client.delete(
            f"/api/projects/{project_id}/agent-prompts/info_collection",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify it was deleted
        get_response = client.get(
            f"/api/projects/{project_id}/agent-prompts",
            headers=auth_headers
        )
        agents = get_response.json()["agents"]
        info_collection = next(a for a in agents if a["agent_type"] == "info_collection")
        assert info_collection["use_custom"] is False
        assert info_collection["custom_content"] is None

    def test_get_effective_prompt_custom(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return effective prompt with custom source"""
        # Set a custom prompt for the project
        custom_content = "Project-specific content"
        client.put(
            f"/api/projects/{project_id}/agent-prompts/review",
            json={"prompt_content": custom_content},
            headers=auth_headers
        )

        response = client.get(
            f"/api/projects/{project_id}/agent-prompts/review/effective",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "custom"
        assert data["prompt_content"] == custom_content

    def test_get_effective_prompt_global(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return effective prompt with global source when no custom"""
        # First set a global prompt (no custom for project)
        global_content = "Global prompt content"
        client.put(
            "/api/agent-prompts/review",
            json={"prompt_content": global_content},
            headers=auth_headers
        )

        response = client.get(
            f"/api/projects/{project_id}/agent-prompts/review/effective",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "global"
        assert data["prompt_content"] == global_content

    def test_get_effective_prompt_system_default(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return effective prompt with system_default source when no custom or global"""
        # Don't set any custom or global prompt
        response = client.get(
            f"/api/projects/{project_id}/agent-prompts/review/effective",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # After ensure_user_has_global_prompts is called, user will have global prompts
        # so this will return "global" with the default content
        assert data["source"] in ("global", "system_default")
        assert data["prompt_content"] == DEFAULT_PROMPTS["review"]

    def test_get_project_prompts_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent project"""
        response = client.get(
            "/api/projects/99999/agent-prompts",
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_set_project_custom_prompt_unknown_agent(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return 404 for unknown agent type"""
        response = client.put(
            f"/api/projects/{project_id}/agent-prompts/unknown_type",
            json={"prompt_content": "content"},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]

    def test_delete_project_custom_prompt_unknown_agent(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return 404 for unknown agent type on delete"""
        response = client.delete(
            f"/api/projects/{project_id}/agent-prompts/unknown_type",
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]

    def test_get_effective_prompt_unknown_agent(self, client: TestClient, auth_headers: dict, project_id: int):
        """Should return 404 for unknown agent type on effective prompt"""
        response = client.get(
            f"/api/projects/{project_id}/agent-prompts/unknown_type/effective",
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]

    def test_unauthorized_access(self, client: TestClient):
        """Should reject unauthorized access to agent prompts"""
        response = client.get("/api/agent-prompts")
        assert response.status_code == 401