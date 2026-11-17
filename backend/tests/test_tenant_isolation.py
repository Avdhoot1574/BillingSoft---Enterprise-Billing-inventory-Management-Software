import uuid

from tests.helpers import API, create_company, signup, with_company


def _two_tenants(client):
    a = signup(client, "a@alpha-tests.org", "Alpha Owner")
    b = signup(client, "b@beta-tests.org", "Beta Owner")
    ca = create_company(client, a, "Alpha Traders")
    cb = create_company(client, b, "Beta Stores")
    return a, b, ca, cb


def test_company_creation_sets_up_period_sequences_and_owner(client, db_engine):
    from sqlalchemy import text

    h = signup(client, "a@alpha-tests.org")
    co = create_company(client, h, "Alpha Traders", gstin="27ABCDE1234F1Z5")
    assert co["state_code"] == "27" and co["is_owner"] is True

    r = client.get(f"{API}/companies/current", headers=with_company(h, co["id"]))
    assert r.status_code == 200
    assert "settings.users.manage" in r.json()["permissions"]

    with db_engine.connect() as conn:
        n_periods = conn.execute(text("SELECT count(*) FROM financial_periods WHERE company_id = :c"),
                                 {"c": co["id"]}).scalar_one()
        n_seq = conn.execute(text("SELECT count(*) FROM document_sequences WHERE company_id = :c"),
                             {"c": co["id"]}).scalar_one()
    assert n_periods == 1 and n_seq >= 5


def test_gstin_must_match_state_and_format(client):
    h = signup(client, "a@alpha-tests.org")
    r = client.post(f"{API}/companies", json={"name": "X", "gstin": "NOT-A-GSTIN"}, headers=h)
    assert r.status_code == 422
    r = client.post(f"{API}/companies", json={"name": "X", "gstin": "27ABCDE1234F1Z5", "state_code": "29"}, headers=h)
    assert r.status_code == 422


def test_user_cannot_use_another_tenants_company(client):
    a, b, ca, cb = _two_tenants(client)
    for path in ("/companies/current", "/members", "/roles", "/audit-events"):
        r = client.get(f"{API}{path}", headers=with_company(b, ca["id"]))
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "COMPANY_ACCESS_DENIED", path


def test_unknown_company_is_indistinguishable_from_forbidden(client):
    a, b, ca, cb = _two_tenants(client)
    forbidden = client.get(f"{API}/companies/current", headers=with_company(b, ca["id"]))
    missing = client.get(f"{API}/companies/current", headers=with_company(b, uuid.uuid4()))
    assert forbidden.status_code == missing.status_code == 403
    assert forbidden.json()["error"]["code"] == missing.json()["error"]["code"]


def test_company_header_validation(client):
    a, _, ca, _ = _two_tenants(client)
    r = client.get(f"{API}/companies/current", headers=a)
    assert r.status_code == 400 and r.json()["error"]["code"] == "COMPANY_HEADER_REQUIRED"
    r = client.get(f"{API}/companies/current", headers={**a, "X-Company-Id": "not-a-uuid"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "COMPANY_HEADER_INVALID"


def test_company_list_only_shows_own_companies(client):
    a, b, ca, cb = _two_tenants(client)
    assert [c["id"] for c in client.get(f"{API}/companies", headers=a).json()] == [ca["id"]]
    assert [c["id"] for c in client.get(f"{API}/companies", headers=b).json()] == [cb["id"]]


def test_audit_events_are_scoped_to_company(client):
    a, b, ca, cb = _two_tenants(client)
    events = client.get(f"{API}/audit-events", headers=with_company(a, ca["id"])).json()
    assert events and all(e["after_data"] is None or "Beta" not in str(e["after_data"]) for e in events)
    assert any(e["action"] == "company.create" for e in events)
    events_b = client.get(f"{API}/audit-events", headers=with_company(b, cb["id"])).json()
    assert {e["id"] for e in events}.isdisjoint({e["id"] for e in events_b})


def test_cannot_touch_member_of_another_company_by_guessing_membership_id(client):
    a, b, ca, cb = _two_tenants(client)
    members_a = client.get(f"{API}/members", headers=with_company(a, ca["id"])).json()
    a_membership = members_a[0]["membership_id"]
    roles_b = {r["name"]: r["id"] for r in client.get(f"{API}/roles", headers=with_company(b, cb["id"])).json()}
    r = client.patch(f"{API}/members/{a_membership}/role", json={"role_id": roles_b["Auditor"]},
                     headers=with_company(b, cb["id"]))
    assert r.status_code == 404
    r = client.delete(f"{API}/members/{a_membership}", headers=with_company(b, cb["id"]))
    assert r.status_code == 404


def test_cannot_assign_role_from_another_tenant(client):
    a, b, ca, cb = _two_tenants(client)
    roles_a = {r["name"]: r["id"] for r in client.get(f"{API}/roles", headers=with_company(a, ca["id"])).json()}
    r = client.post(f"{API}/invitations", json={"email": "x@beta-tests.org", "role_id": roles_a["Auditor"]},
                    headers=with_company(b, cb["id"]))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ROLE_NOT_FOUND"
