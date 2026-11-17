from tests.helpers import API, PASSWORD, bearer, login, register, signup


def test_register_login_me(client):
    register(client, "owner@acme-tests.org", "Asha Owner")
    tokens = login(client, "owner@acme-tests.org")
    r = client.get(f"{API}/auth/me", headers=bearer(tokens))
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "owner@acme-tests.org"
    assert r.json()["companies"] == []


def test_email_is_case_insensitive_and_unique(client):
    register(client, "Owner@Acme-Tests.org")
    r = client.post(f"{API}/auth/register",
                    json={"email": "owner@acme-tests.org", "password": PASSWORD, "full_name": "Dup"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_OR_PHONE_ALREADY_REGISTERED"
    login(client, "OWNER@acme-tests.org")


def test_weak_password_rejected(client):
    r = client.post(f"{API}/auth/register",
                    json={"email": "a@acme-tests.org", "password": "short", "full_name": "A"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_wrong_password_and_unknown_user_look_identical(client):
    register(client, "owner@acme-tests.org")
    wrong = client.post(f"{API}/auth/login", json={"email": "owner@acme-tests.org", "password": "nope-nope-nope"})
    unknown = client.post(f"{API}/auth/login", json={"email": "ghost@acme-tests.org", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_account_locks_after_repeated_failures(client):
    register(client, "owner@acme-tests.org")
    for _ in range(5):
        r = client.post(f"{API}/auth/login", json={"email": "owner@acme-tests.org", "password": "wrong-wrong-wrong"})
        assert r.status_code == 401
    r = client.post(f"{API}/auth/login", json={"email": "owner@acme-tests.org", "password": PASSWORD})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_protected_endpoint_requires_token(client):
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"
    r = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_refresh_rotates_and_reuse_revokes_everything(client):
    register(client, "owner@acme-tests.org")
    t1 = login(client, "owner@acme-tests.org")
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert r.status_code == 200
    t2 = r.json()
    assert t2["refresh_token"] != t1["refresh_token"]
    assert client.get(f"{API}/auth/me", headers=bearer(t2)).status_code == 200

    # Presenting the already-used refresh token again = suspected theft: all sessions die.
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert r.status_code == 401
    assert client.get(f"{API}/auth/me", headers=bearer(t2)).status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 401


def test_logout_invalidates_access_token(client):
    headers = signup(client, "owner@acme-tests.org")
    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 204
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_request_id_is_returned_and_echoed_in_errors(client):
    r = client.get(f"{API}/auth/me", headers={"X-Request-ID": "req-12345678"})
    assert r.headers["X-Request-ID"] == "req-12345678"
    assert r.json()["error"]["request_id"] == "req-12345678"
