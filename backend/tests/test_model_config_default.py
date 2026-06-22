"""模型配置默认值行为测试

覆盖 #1：用户尚无默认配置时，创建的首个配置应自动成为默认；
后续创建的配置不应抢占默认，避免后端无显式 config_id 时静默降级。
"""


def _payload(name: str) -> dict:
    return {
        "name": name,
        "provider": "custom",
        "provider_type": "single",
        "base_url": "https://example.com/v1",
        "model_name": "test-model",
        "api_key": "sk-test",
    }


def test_first_config_becomes_default(client, auth_headers):
    """首个创建的配置自动设为默认"""
    resp = client.post("/api/model_configs/", json=_payload("第一个"), headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True


def test_second_config_not_default(client, auth_headers):
    """已有默认配置时，新建配置不抢占默认"""
    first = client.post("/api/model_configs/", json=_payload("第一个"), headers=auth_headers)
    assert first.status_code == 200, first.text
    assert first.json()["is_default"] is True

    second = client.post("/api/model_configs/", json=_payload("第二个"), headers=auth_headers)
    assert second.status_code == 200, second.text
    assert second.json()["is_default"] is False

    # 全列表中有且仅有一个默认
    listing = client.get("/api/model_configs/", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    defaults = [m for m in listing.json()["models"] if m["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "第一个"
