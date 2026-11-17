PASSWORD = "correct-horse-battery"
API = "/api/v1"


def register(client, email, full_name="Test User", password=PASSWORD):
    r = client.post(f"{API}/auth/register", json={"email": email, "password": password, "full_name": full_name})
    assert r.status_code == 201, r.text
    return r.json()


def login(client, email, password=PASSWORD):
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def signup(client, email, full_name="Test User"):
    """Register + login; returns auth headers."""
    register(client, email, full_name)
    return bearer(login(client, email))


def create_company(client, headers, name="Acme Traders", **extra):
    r = client.post(f"{API}/companies", json={"name": name, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def with_company(headers, company_id):
    return {**headers, "X-Company-Id": str(company_id)}
