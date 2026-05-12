"""Phase 4 인증 엔드포인트 통합 테스트.

검증:
  - /v1/auth/login: bootstrap admin 로그인 성공
  - /v1/auth/refresh: refresh token 으로 새 access 발급
  - /v1/auth/me: 토큰 사용자 정보
  - /v1/auth/password: 비밀번호 변경 (현재 검증 + 복잡도)
  - 보호된 엔드포인트 401: 토큰 없음 / 잘못된 토큰
  - 권한별 403: viewer 가 admin 전용 엔드포인트 접근
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _raw_client():
    """헤더 주입 안 된 깨끗한 client — 인증 실패 케이스 검증용."""
    from src.main import app
    return TestClient(app)


# ──────────────────────────────────────────────────────────────
# 로그인 / 토큰
# ──────────────────────────────────────────────────────────────


def test_login_with_bootstrap_admin_succeeds(client):
    """conftest 의 client 가 이미 로그인했지만, 별도 raw 클라이언트로 재확인."""
    raw = _raw_client()
    with raw:
        r = raw.post("/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


def test_login_wrong_password_returns_401(client):
    raw = _raw_client()
    with raw:
        r = raw.post("/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_login_unknown_user_returns_same_401(client):
    """사용자 enumeration 방지 — 동일한 detail."""
    raw = _raw_client()
    with raw:
        r = raw.post("/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_refresh_token_issues_new_access(client):
    raw = _raw_client()
    with raw:
        login = raw.post("/v1/auth/login", json={"username": "admin", "password": "changeme"})
        rt = login.json()["refresh_token"]
        r = raw.post("/v1/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_with_access_token_rejected(client):
    """access token 을 refresh 로 보내면 wrong_token_type."""
    raw = _raw_client()
    with raw:
        login = raw.post("/v1/auth/login", json={"username": "admin", "password": "changeme"})
        at = login.json()["access_token"]
        r = raw.post("/v1/auth/refresh", json={"refresh_token": at})
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────
# /me
# ──────────────────────────────────────────────────────────────


def test_me_returns_current_user(client):
    r = client.get("/v1/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_me_without_token_401():
    raw = _raw_client()
    with raw:
        r = raw.get("/v1/auth/me")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_me_with_invalid_token_401():
    raw = _raw_client()
    with raw:
        raw.headers["Authorization"] = "Bearer not-a-real-jwt"
        r = raw.get("/v1/auth/me")
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────
# 비밀번호 변경
# ──────────────────────────────────────────────────────────────


def test_change_password_succeeds(client):
    r = client.post(
        "/v1/auth/password",
        json={"current_password": "changeme", "new_password": "NewPass123Secure"},
    )
    assert r.status_code == 204
    # 새 비밀번호로 로그인 가능
    raw = _raw_client()
    with raw:
        login = raw.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "NewPass123Secure"},
        )
    assert login.status_code == 200


def test_change_password_wrong_current_returns_401(client):
    r = client.post(
        "/v1/auth/password",
        json={"current_password": "wrong", "new_password": "NewPass123Secure"},
    )
    assert r.status_code == 401


def test_change_password_complexity_enforced(client):
    """글자만 / 숫자만 / 짧은 비밀번호는 422."""
    for bad in ("onlyletters", "12345678", "short1A"):
        r = client.post(
            "/v1/auth/password",
            json={"current_password": "changeme", "new_password": bad},
        )
        assert r.status_code == 422, f"expected 422 for '{bad}', got {r.status_code}"


# ──────────────────────────────────────────────────────────────
# 권한 가드 (require_role)
# ──────────────────────────────────────────────────────────────


def test_protected_endpoint_without_token_401():
    raw = _raw_client()
    with raw:
        r = raw.get("/api/agents")
    assert r.status_code == 401


def test_viewer_can_read_but_cannot_create_api_key(viewer_client, client, seeded_agent):
    # viewer 는 /api/agents/{id}/api-keys GET 가능 (require_role admin/operator/viewer)
    list_r = viewer_client.get(f"/api/agents/{seeded_agent['id']}/api-keys")
    assert list_r.status_code == 200
    # 발급은 admin/operator 만 — viewer 는 403
    create_r = viewer_client.post(
        f"/api/agents/{seeded_agent['id']}/api-keys",
        json={"description": "should fail"},
    )
    assert create_r.status_code == 403
