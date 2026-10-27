import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from tests.conftest import AUTH, make_settings


def test_health_needs_no_credentials_or_database(bare_client: TestClient) -> None:
    res = bare_client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert res.headers["x-request-id"].startswith("req_")


def test_request_id_is_echoed(bare_client: TestClient) -> None:
    res = bare_client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["x-request-id"] == "abc-123"


def test_readiness_without_database_is_503(bare_client: TestClient) -> None:
    res = bare_client.get("/api/v1/health/ready")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "DATABASE_NOT_CONFIGURED"


def test_readiness_with_database(client: TestClient) -> None:
    assert client.get("/api/v1/health/ready").json() == {"status": "ok", "database": "ok"}


def test_protected_route_rejects_missing_and_wrong_token(client: TestClient) -> None:
    missing = client.get("/api/v1/runs")
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["error"]["code"] == "UNAUTHORIZED"
    wrong = client.get("/api/v1/runs", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401


def test_protected_route_accepts_token(client: TestClient) -> None:
    res = client.get("/api/v1/runs", headers=AUTH)
    assert res.status_code == 200
    assert res.json() == {"items": [], "nextCursor": None}


def test_auth_fails_closed_when_token_unconfigured() -> None:
    from app.main import create_app

    with TestClient(create_app(make_settings(api_auth_token=None))) as c:
        assert c.get("/api/v1/runs", headers=AUTH).status_code == 503


def test_error_envelope_for_validation_and_not_found(client: TestClient) -> None:
    bad = client.get("/api/v1/runs", headers=AUTH, params={"limit": 0})
    assert bad.status_code == 422
    body = bad.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["requestId"]
    assert body["details"][0]["loc"][-1] == "limit"
    missing = client.get("/api/v1/runs/run_nope", headers=AUTH)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_log_formatter_redacts_secrets() -> None:
    record = logging.LogRecord("t", logging.INFO, "f", 1, "hello", (), None)
    record.authorization = "Bearer secret"
    record.nested = {"api_key": "k", "ok": 1}
    out = json.loads(JsonFormatter().format(record))
    assert out["authorization"] == "[REDACTED]"
    assert out["nested"] == {"api_key": "[REDACTED]", "ok": 1}
    assert "secret" not in json.dumps(out)
