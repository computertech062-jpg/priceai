"""
تاقیکردنەوەی API بە FastAPI TestClient.
ڕاکردن:  python -m pytest -q
(پێویستی بە httpx هەیە، کە لە requirements.txt دایە)
"""
import os
import tempfile

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"
# تاقیکردنەوە کۆنەکان وەک میوان کار دەکەن؛ test_login_wall خۆی REQUIRE_LOGIN چالاک دەکات
os.environ["REQUIRE_LOGIN"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def register(client, email, name="Test User", password="password123"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def a55(client):
    pid = client.get("/api/phones/search", params={"q": "a55"}).json()["results"][0]["id"]
    phone = client.get(f"/api/phones/{pid}").json()
    v = phone["variants"][0]
    return phone, {**phone["specs"], "ram_gb": v["ram_gb"], "storage_gb": v["storage_gb"]}


def test_health(client):
    assert client.get("/api/health").json()["model_loaded"] is True


def test_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "PriceAI" in r.text


def test_features_schema(client):
    data = client.get("/api/features").json()
    names = [f["name"] for f in data["features"]]
    assert "ram_gb" in names and "brand" in names


def test_first_user_is_admin_and_second_is_not(client):
    first = register(client, "admin@example.com")
    second = register(client, "user@example.com")
    assert first["user"]["role"] == "admin"
    assert second["user"]["role"] == "user"


def test_duplicate_email(client):
    r = client.post("/api/auth/register", json={"name": "X Y", "email": "user@example.com",
                                                "password": "password123"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "email_taken"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "user@example.com", "password": "nope-nope"})
    assert r.status_code == 401


def test_guest_prediction_is_not_saved(client):
    phone, feats = a55(client)
    r = client.post("/api/predict", json={"features": feats, "phone_id": phone["id"], "asked_price": 999})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prediction_id"] is None
    assert body["low"] < body["price"] < body["high"]
    assert body["verdict"]["status"] in ("cheap", "fair", "expensive")
    assert len(body["explanation"]["items"]) > 0


def test_invalid_feature(client):
    phone, feats = a55(client)
    feats["ram_gb"] = 5000
    r = client.post("/api/predict", json={"features": feats, "phone_id": phone["id"]})
    assert r.status_code == 422
    assert r.json()["detail"]["field"] == "ram_gb"


def test_prediction_requires_real_phone(client):
    """پێشبینی تەنها بۆ مۆبایلێکی ناو کاتالۆگ: بەبێ phone_id یان بە phone_id ی ساختە ڕەت دەکرێتەوە."""
    phone, feats = a55(client)
    r = client.post("/api/predict", json={"features": {"brand": "Vivo", "ram_gb": 6, "storage_gb": 128}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "phone_required"
    r = client.post("/api/predict", json={"features": feats, "phone_id": "no-such-phone"})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "phone_not_found"
    r = client.post("/api/compare", json={"items": [{"features": feats, "phone_id": phone["id"]},
                                                    {"features": feats}]})
    assert r.status_code == 422 and r.json()["detail"]["index"] == 1


def test_catalog_has_only_market_phones(client):
    """تابلێت و براندی دەرەوەی بازاڕی عێراق نییە."""
    brands = client.get("/api/phones/brands").json()["brands"]
    for b in ("Razer", "Thuraya", "Symphony", "Walton", "Helio", "Lava"):
        assert b not in brands, b
    assert brands[0] in ("Vivo", "Xiaomi", "Oppo", "Samsung", "Realme", "Honor")  # زۆرترین مۆبایل
    for q in ("ipad", "galaxy tab", "xiaomi pad"):
        names = [r["name"].lower() for r in client.get("/api/phones/search", params={"q": q}).json()["results"]]
        assert not any(("ipad" in n) or (" tab " in f"{n} ") or (" pad " in f"{n} ") for n in names), (q, names)


def test_history_flow(client):
    token = client.post("/api/auth/login", json={"email": "user@example.com",
                                                 "password": "password123"}).json()["token"]
    phone, feats = a55(client)
    r = client.post("/api/predict", json={"features": feats, "phone_id": phone["id"],
                                          "phone_name": phone["name"]}, headers=auth(token))
    pid = r.json()["prediction_id"]
    assert pid
    hist = client.get("/api/history", headers=auth(token)).json()
    assert hist["total"] == 1 and hist["items"][0]["phone_name"] == phone["name"]
    assert client.get("/api/history", params={"q": "zzz"}, headers=auth(token)).json()["total"] == 0
    dash = client.get("/api/dashboard", headers=auth(token)).json()
    assert dash["total"] == 1 and dash["admin"] is None
    assert client.delete(f"/api/history/{pid}", headers=auth(token)).json()["ok"]
    assert client.get("/api/history", headers=auth(token)).json()["total"] == 0


def test_history_requires_login(client):
    assert client.get("/api/history").status_code == 401


def test_admin_endpoints(client):
    admin = client.post("/api/auth/login", json={"email": "admin@example.com",
                                                 "password": "password123"}).json()["token"]
    user = client.post("/api/auth/login", json={"email": "user@example.com",
                                                "password": "password123"}).json()["token"]
    assert client.get("/api/admin/users", headers=auth(user)).status_code == 403
    users = client.get("/api/admin/users", headers=auth(admin)).json()["items"]
    target = next(u for u in users if u["email"] == "user@example.com")
    r = client.patch(f"/api/admin/users/{target['id']}", json={"is_active": False}, headers=auth(admin))
    assert r.json()["is_active"] is False
    assert client.get("/api/auth/me", headers=auth(user)).status_code == 403
    me = next(u for u in users if u["email"] == "admin@example.com")
    assert client.delete(f"/api/admin/users/{me['id']}", headers=auth(admin)).status_code == 400


def test_compare(client):
    phone, feats = a55(client)
    pid2 = client.get("/api/phones/search", params={"q": "iphone 17 pro"}).json()["results"][0]["id"]
    phone2 = client.get(f"/api/phones/{pid2}").json()
    c2 = phone2["configs"][0]
    feats2 = {**phone2["specs"], "ram_gb": c2["ram_gb"], "storage_gb": c2["storage_gb"]}
    r = client.post("/api/compare", json={"items": [
        {"features": feats, "phone_id": phone["id"], "phone_name": "A", "asked_price": 300},
        {"features": feats2, "phone_id": pid2, "phone_name": "B", "asked_price": 300},
    ]})
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 2


def test_model_info(client):
    info = client.get("/api/model").json()
    assert info["best_model"] and info["results"]


# ---------- چوونەژوورەوەی پێویست (REQUIRE_LOGIN) ----------
@pytest.fixture
def login_required(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "REQUIRE_LOGIN", True)


def test_login_wall_blocks_guests(client, login_required):
    assert client.get("/api/config").json()["require_login"] is True
    assert "ar" in client.get("/api/config").json()["languages"]
    for method, url in [("get", "/api/features"), ("get", "/api/phones/search?q=a55"),
                        ("get", "/api/model"), ("post", "/api/predict"), ("post", "/api/compare")]:
        r = getattr(client, method)(url, **({"json": {"features": {}}} if method == "post" else {}))
        assert r.status_code == 401, (url, r.status_code)
        assert r.json()["detail"]["code"] == "auth_required"
    # تەندروستی و چوونەژوورەوە هەمیشە کراوەن
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"}).status_code == 401


def test_login_wall_allows_users(client, login_required):
    token = register(client, "wall@example.com")["token"]
    assert client.get("/api/phones/search", params={"q": "a55"}, headers=auth(token)).status_code == 200
    assert client.get("/api/features", headers=auth(token)).status_code == 200
    # token ی هەڵە = میوان
    assert client.get("/api/features", headers=auth("not-a-real-token")).status_code == 401


def test_create_admin_script(client, monkeypatch):
    """scripts/create_admin.py: هەژماری Admin بە Gmail دروست دەکات، و هەژماری هەبوو دەکات بە Admin."""
    import importlib.util
    import sys
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "create_admin", Path(__file__).resolve().parents[1] / "scripts" / "create_admin.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.getpass, "getpass", lambda prompt="": "gmail-pass-123")

    monkeypatch.setattr(sys, "argv", ["create_admin.py", "Owner.Test@Gmail.com", "--name", "Owner"])
    mod.main()
    r = client.post("/api/auth/login", json={"email": "owner.test@gmail.com", "password": "gmail-pass-123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"

    # هەژماری ئاسایی هەبوو → دەکرێت بە Admin و وشەی نهێنی دەگۆڕدرێت
    register(client, "promote@gmail.com", password="old-password-1")
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "promote@gmail.com"])
    mod.main()
    assert client.post("/api/auth/login", json={"email": "promote@gmail.com",
                                                "password": "old-password-1"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "promote@gmail.com", "password": "gmail-pass-123"})
    assert r.json()["user"]["role"] == "admin"

    # ئیمەیڵی هەڵە ڕەت دەکرێتەوە
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "not-an-email"])
    with pytest.raises(SystemExit):
        mod.main()
