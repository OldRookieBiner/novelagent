"""Tests for WorkflowState model"""

import pytest
from datetime import datetime
from app.models.workflow_state import WorkflowState
from app.models.project import Project
from app.models.user import User


def test_workflow_state_defaults():
    """Test WorkflowState default values"""
    state = WorkflowState(project_id=1)
    assert state.thread_id == "main"
    assert state.stage == "inspiration"
    assert state.workflow_mode == "hybrid"
    assert state.max_rewrite_count == 3
    assert state.current_chapter == 1
    assert state.waiting_for_confirmation == False
    assert state.confirmation_type == None


def test_workflow_state_stage_values():
    """Test valid stage values"""
    valid_stages = [
        "inspiration", "outline", "chapter_outlines",
        "writing", "review", "complete"
    ]
    for stage in valid_stages:
        state = WorkflowState(project_id=1, stage=stage)
        assert state.stage == stage


def test_workflow_state_workflow_mode_values():
    """Test valid workflow_mode values"""
    valid_modes = ["step_by_step", "hybrid", "auto"]
    for mode in valid_modes:
        state = WorkflowState(project_id=1, workflow_mode=mode)
        assert state.workflow_mode == mode
