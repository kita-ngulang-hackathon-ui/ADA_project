"""Error envelope shape (API_CONTRACTS.md "Error shape")."""


def test_missing_auth_header_gives_401_envelope(client):
    resp = client.post("/v1/events", json={
        "client_event_id": "e1", "event_type": "x", "occurred_at": "2026-09-17T10:00:00+07:00",
        "user_ref": "u1",
    })
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "request_id" in body["error"]
    assert body["error"]["request_id"] != "unknown"


def test_console_endpoint_without_session_gives_401(client):
    resp = client.get("/console/v1/users")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_pull_recommendations_without_credentials_is_unauthenticated(client):
    # Auth runs before the `status` query value is ever inspected -- an
    # empty Authorization header is rejected without touching the database.
    resp = client.get("/v1/recommendations", params={"status": "PENDING_APPROVAL"})
    assert resp.status_code == 401


def test_request_id_header_present_on_success(client):
    resp = client.get("/v1/health")
    assert "X-Request-Id" in resp.headers


def test_session_with_unknown_reviewer_is_forbidden(client):
    resp = client.post("/console/v1/session", json={"tenant_slug": "demo-wallet", "reviewer_id": "nobody"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
