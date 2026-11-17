from tests.helpers import API, bearer, create_company, login, register, signup, with_company


def _setup(client):
    owner = signup(client, "owner@acme-tests.org", "Owner")
    co = create_company(client, owner, "Acme Traders")
    h = with_company(owner, co["id"])
    roles = {r["name"]: r["id"] for r in client.get(f"{API}/roles", headers=h).json()}
    return owner, co, h, roles


def _invite_and_accept(client, h, roles, email, role_name):
    r = client.post(f"{API}/invitations", json={"email": email, "role_id": roles[role_name]}, headers=h)
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    assert token
    register(client, email, role_name)
    staff = bearer(login(client, email))
    r = client.post(f"{API}/invitations/accept", json={"token": token}, headers=staff)
    assert r.status_code == 200, r.text
    return staff, r.json()


def test_system_roles_exist(client):
    _, _, _, roles = _setup(client)
    assert set(roles) == {"Owner", "Administrator", "Accountant", "Salesperson", "Inventory Manager", "Auditor"}


def test_salesperson_has_billing_but_not_admin_permissions(client):
    _, co, h, roles = _setup(client)
    staff, _ = _invite_and_accept(client, h, roles, "sales@acme-tests.org", "Salesperson")
    sh = with_company(staff, co["id"])

    perms = set(client.get(f"{API}/companies/current", headers=sh).json()["permissions"])
    assert "sales.invoice.create" in perms
    assert not perms & {"settings.users.manage", "reports.profit_loss.read", "items.cost.read", "bank.balance.read"}

    r = client.get(f"{API}/members", headers=sh)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"
    assert r.json()["error"]["details"]["required"] == "settings.users.manage"
    assert client.get(f"{API}/audit-events", headers=sh).status_code == 403
    assert client.post(f"{API}/invitations", json={"email": "z@acme-tests.org", "role_id": roles["Auditor"]},
                       headers=sh).status_code == 403


def test_changing_role_changes_access_immediately(client):
    _, co, h, roles = _setup(client)
    staff, _ = _invite_and_accept(client, h, roles, "sales@acme-tests.org", "Salesperson")
    sh = with_company(staff, co["id"])
    assert client.get(f"{API}/audit-events", headers=sh).status_code == 403

    members = client.get(f"{API}/members", headers=h).json()
    membership = next(m for m in members if m["email"] == "sales@acme-tests.org")
    assert membership["roles"] == ["Salesperson"]
    r = client.patch(f"{API}/members/{membership['membership_id']}/role", json={"role_id": roles["Auditor"]},
                     headers=h)
    assert r.status_code == 204
    assert client.get(f"{API}/audit-events", headers=sh).status_code == 200


def test_owner_role_cannot_be_assigned_or_changed(client):
    _, co, h, roles = _setup(client)
    r = client.post(f"{API}/invitations", json={"email": "x@acme-tests.org", "role_id": roles["Owner"]}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "ROLE_NOT_ASSIGNABLE"

    owner_membership = client.get(f"{API}/members", headers=h).json()[0]
    r = client.patch(f"{API}/members/{owner_membership['membership_id']}/role",
                     json={"role_id": roles["Auditor"]}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "OWNER_ROLE_LOCKED"
    r = client.delete(f"{API}/members/{owner_membership['membership_id']}", headers=h)
    assert r.status_code == 409


def test_invitation_must_be_accepted_by_the_invited_email(client):
    _, co, h, roles = _setup(client)
    r = client.post(f"{API}/invitations", json={"email": "invited@acme-tests.org", "role_id": roles["Auditor"]},
                    headers=h)
    token = r.json()["token"]
    intruder = signup(client, "intruder@acme-tests.org")
    r = client.post(f"{API}/invitations/accept", json={"token": token}, headers=intruder)
    assert r.status_code == 403 and r.json()["error"]["code"] == "INVITATION_EMAIL_MISMATCH"


def test_invitation_single_use_and_duplicate_pending_blocked(client):
    _, co, h, roles = _setup(client)
    body = {"email": "dup@acme-tests.org", "role_id": roles["Auditor"]}
    first = client.post(f"{API}/invitations", json=body, headers=h)
    assert first.status_code == 201
    again = client.post(f"{API}/invitations", json=body, headers=h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVITATION_PENDING"

    register(client, "dup@acme-tests.org")
    staff = bearer(login(client, "dup@acme-tests.org"))
    assert client.post(f"{API}/invitations/accept", json={"token": first.json()["token"]}, headers=staff).status_code == 200
    r = client.post(f"{API}/invitations/accept", json={"token": first.json()["token"]}, headers=staff)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVITATION_NOT_PENDING"


def test_removed_member_loses_access(client):
    _, co, h, roles = _setup(client)
    staff, _ = _invite_and_accept(client, h, roles, "acct@acme-tests.org", "Accountant")
    sh = with_company(staff, co["id"])
    assert client.get(f"{API}/companies/current", headers=sh).status_code == 200

    membership = next(m for m in client.get(f"{API}/members", headers=h).json() if m["email"] == "acct@acme-tests.org")
    assert client.delete(f"{API}/members/{membership['membership_id']}", headers=h).status_code == 204
    r = client.get(f"{API}/companies/current", headers=sh)
    assert r.status_code == 403 and r.json()["error"]["code"] == "COMPANY_ACCESS_DENIED"


def test_audit_trail_records_security_events_without_secrets(client):
    _, co, h, roles = _setup(client)
    _invite_and_accept(client, h, roles, "acct@acme-tests.org", "Accountant")
    events = client.get(f"{API}/audit-events", headers=h).json()
    actions = {e["action"] for e in events}
    assert {"company.create", "member.invite", "member.accept_invitation"} <= actions
    assert all(e["request_id"] for e in events)
    blob = str(events).lower()
    assert "token" not in blob and "password" not in blob
