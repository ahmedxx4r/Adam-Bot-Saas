import jwt

from auth import create_access_token, hash_password, verify_password
from main import scoped_session_id


def test_password_hashing():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_contains_user_id(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-with-at-least-32-characters")
    token = create_access_token(42)
    payload = jwt.decode(
        token,
        "test-secret-key-with-at-least-32-characters",
        algorithms=["HS256"],
    )
    assert payload["sub"] == "42"


def test_session_ids_are_scoped_per_user():
    class Account:
        def __init__(self, user_id):
            self.id = user_id

    assert scoped_session_id(Account(1), "same-session") != scoped_session_id(Account(2), "same-session")
    assert scoped_session_id(Account(1), "same-session") == scoped_session_id(Account(1), "same-session")
