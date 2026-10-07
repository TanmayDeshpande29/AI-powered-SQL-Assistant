from app.core.security import create_token, hash_password, verify_password
from tests.conftest import signup_and_login


def test_password_is_hashed_and_salted():
    first, second = hash_password("same-password"), hash_password("same-password")
    assert first != "same-password"
    assert first != second  # random salt per hash
    assert verify_password("same-password", first)
    assert not verify_password("wrong-password", first)


async def test_signup_returns_user_without_password(client):
    res = await client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada", "email": "  Ada@Example.com ", "password": "s3cret-pass"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "ada@example.com"  # normalized
    assert "password" not in body and "hashed_password" not in body


async def test_duplicate_signup_conflicts(client):
    payload = {"name": "Ada", "email": "ada@example.com", "password": "s3cret-pass"}
    await client.post("/api/v1/auth/signup", json=payload)
    res = await client.post("/api/v1/auth/signup", json=payload)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "conflict"


async def test_short_password_rejected(client):
    res = await client.post(
        "/api/v1/auth/signup", json={"name": "Ada", "email": "a@example.com", "password": "short"}
    )
    assert res.status_code == 422
    assert res.json()["error"]["details"][0]["field"] == "password"


async def test_login_wrong_password_and_unknown_email_look_identical(client):
    await signup_and_login(client)
    wrong_pw = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope-nope"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


async def test_me_requires_token(client):
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


async def test_me_with_token(client):
    _, headers = await signup_and_login(client)
    res = await client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "ada@example.com"


async def test_refresh_token_cannot_be_used_as_access_token(client):
    tokens, _ = await signup_and_login(client)
    res = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert res.status_code == 401


async def test_refresh_issues_new_pair(client):
    tokens, _ = await signup_and_login(client)
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    new_access = res.json()["access_token"]
    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


async def test_access_token_rejected_at_refresh(client):
    tokens, _ = await signup_and_login(client)
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert res.status_code == 401


async def test_token_for_unknown_user_rejected(client):
    token = create_token("00000000-0000-0000-0000-000000000000", "access")
    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


async def test_change_password(client):
    _, headers = await signup_and_login(client)
    bad = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": "wrong-one", "new_password": "brand-new-pass"},
        headers=headers,
    )
    assert bad.status_code == 400  # wrong form input, NOT an invalid session
    ok = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": "s3cret-pass", "new_password": "brand-new-pass"},
        headers=headers,
    )
    assert ok.status_code == 204
    login = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "brand-new-pass"}
    )
    assert login.status_code == 200
