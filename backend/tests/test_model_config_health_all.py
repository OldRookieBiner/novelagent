"""测试健康检查并发测试所有模型"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.schemas.model_config import ModelHealthResult, HealthCheckResponse


def test_model_health_result_schema():
    """ModelHealthResult schema 正确构造"""
    r = ModelHealthResult(model_id="gpt-4o", model_name="GPT-4o", status="healthy", latency=150)
    assert r.model_id == "gpt-4o"
    assert r.status == "healthy"
    assert r.latency == 150

    r2 = ModelHealthResult(model_id="bad-model", model_name="Bad", status="unhealthy", error="timeout")
    assert r2.status == "unhealthy"
    assert r2.latency is None


def test_health_check_response_with_model_results():
    """HealthCheckResponse 支持 model_results 字段"""
    resp = HealthCheckResponse(
        status="unhealthy",
        model_results=[
            ModelHealthResult(model_id="m1", model_name="M1", status="healthy", latency=100),
            ModelHealthResult(model_id="m2", model_name="M2", status="unhealthy", error="fail"),
        ],
    )
    assert resp.status == "unhealthy"
    assert len(resp.model_results) == 2
    assert resp.model_results[1].status == "unhealthy"


def test_health_check_response_backward_compatible():
    """HealthCheckResponse 无 model_results 时向后兼容"""
    resp = HealthCheckResponse(status="healthy", latency=100)
    assert resp.model_results is None
