"""Tests for system prompts API"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.system_config import SystemConfig


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_header(client):
    """Get authentication header"""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    token = response.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


class TestSystemPromptsAPI:
    """Tests for system prompts API endpoints"""

    def test_get_system_prompts(self, client, auth_header):
        """Test getting all system prompts"""
        response = client.get("/api/system/prompts/", headers=auth_header)
        assert response.status_code == 200

        data = response.json()
        assert "prompts" in data
        assert len(data["prompts"]) == 5

        # Check structure of first prompt
        prompt = data["prompts"][0]
        assert "agent_type" in prompt
        assert "agent_name" in prompt
        assert "description" in prompt
        assert "prompt_content" in prompt
        assert "variables" in prompt

    def test_update_system_prompt(self, client, auth_header):
        """Test updating a system prompt"""
        new_content = "Test prompt content for outline generation."

        response = client.put(
            "/api/system/prompts/outline_generation",
            headers=auth_header,
            json={"prompt_content": new_content}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["prompt_content"] == new_content
        assert data["agent_type"] == "outline_generation"

    def test_update_unknown_agent_type(self, client, auth_header):
        """Test updating with unknown agent type"""
        response = client.put(
            "/api/system/prompts/unknown_type",
            headers=auth_header,
            json={"prompt_content": "test"}
        )
        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]

    def test_reset_system_prompt(self, client, auth_header):
        """Test resetting a system prompt to default"""
        # First update the prompt
        client.put(
            "/api/system/prompts/review",
            headers=auth_header,
            json={"prompt_content": "Modified content"}
        )

        # Then reset it
        response = client.post(
            "/api/system/prompts/review/reset",
            headers=auth_header
        )
        assert response.status_code == 200

        data = response.json()
        # The content should be back to default
        assert "你是一个专业的小说编辑" in data["prompt_content"]

    def test_reset_unknown_agent_type(self, client, auth_header):
        """Test resetting with unknown agent type"""
        response = client.post(
            "/api/system/prompts/unknown_type/reset",
            headers=auth_header
        )
        assert response.status_code == 404
        assert "Unknown agent type" in response.json()["detail"]
