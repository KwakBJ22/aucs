from aucs_api import settings
from aucs_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_admin_needs_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "")
    assert client.get("/admin/status").status_code in (401, 403)
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "abc")
    assert client.get("/admin/status", headers={"X-Admin-Token": "wrong"}).status_code in (401, 403)


def test_admin_flags_unknown_key(monkeypatch) -> None:
    from aucs_api.services import admin_ops

    monkeypatch.setattr(settings, "ADMIN_TOKEN", "abc")
    monkeypatch.setattr(admin_ops, "set_flag", lambda a, k, e: None)
    r = client.put("/admin/flags/nope", json={"enabled": True}, headers={"X-Admin-Token": "abc"})
    assert r.status_code == 404


def test_admin_roles_and_mfa(monkeypatch) -> None:
    """2단계 인증 전이면 막고, 보기 역할은 바꾸는 주소를 못 씀(11/2)."""
    from aucs_api.auth.admin import Admin, admin_login
    from aucs_api.services import admin_ops

    monkeypatch.setattr(admin_ops, "request_job", lambda a, k: {"req_id": 1, "dup": False})
    try:
        app.dependency_overrides[admin_login] = lambda: Admin("u", "owner", False)
        r = client.post("/admin/job-requests", json={"job_key": "daily"})
        assert r.status_code == 403 and r.json()["detail"] == "mfa"
        assert client.get("/admin/me").json() == {"role": "owner", "mfa": False}
        app.dependency_overrides[admin_login] = lambda: Admin("u", "viewer", True)
        assert client.post("/admin/job-requests", json={"job_key": "daily"}).status_code == 403
        app.dependency_overrides[admin_login] = lambda: Admin("u", "operator", True)
        assert client.post("/admin/job-requests", json={"job_key": "daily"}).status_code == 200
        assert client.post("/admin/users/x/email").status_code == 403  # 메일 보기는 대표만
    finally:
        app.dependency_overrides.clear()


def test_limited_member_cannot_write(monkeypatch) -> None:
    """이용 제한된 회원: 읽기·문의·탈퇴는 되고 저장은 403(11/2)."""
    from aucs_api.routers import me as me_router
    from aucs_api.services import admin_ops

    monkeypatch.setattr(me_router, "current_user_id", lambda authorization: "u1")
    monkeypatch.setattr(admin_ops, "is_limited", lambda uid: True)
    monkeypatch.setattr(admin_ops, "ask", lambda uid, body: 1)
    h = {"Authorization": "Bearer x"}
    r = client.put("/me/watch/B1", headers=h)
    assert r.status_code == 403
    assert client.post("/me/inquiries", json={"body": "문의해요"}, headers=h).status_code != 403


def test_admin_screen_bundles(monkeypatch) -> None:
    """메뉴 한 화면 묶음(11/3): 설정은 대표만 감사 기록까지."""
    from aucs_api.auth.admin import Admin, admin_login
    from aucs_api.services import admin, admin_ops

    for name in ("rule_tables", "dong_alias", "admins", "audit_log"):
        monkeypatch.setattr(admin_ops, name, lambda n=name: [n])
    monkeypatch.setattr(admin, "flags", lambda: ["flags"])
    try:
        app.dependency_overrides[admin_login] = lambda: Admin("u", "operator", True)
        r = client.get("/admin/screen/settings").json()
        assert set(r) == {"rules", "flags", "dongs", "admins", "audit"} and r["audit"] == []
        app.dependency_overrides[admin_login] = lambda: Admin("u", "owner", True)
        assert client.get("/admin/screen/settings").json()["audit"] != []
        assert client.get("/admin/screen/nope").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_cron_needs_secret(monkeypatch) -> None:
    """예약 실행 주소는 비밀값이 맞을 때만(11/3)."""
    from aucs_workers.jobs import notify

    monkeypatch.setattr(notify, "run_once", lambda *, morning, push=True: f"morning={morning}")
    monkeypatch.setattr(settings, "CRON_SECRET", "")
    assert client.get("/cron/notify").status_code == 401
    monkeypatch.setattr(settings, "CRON_SECRET", "s3")
    assert client.get("/cron/notify", headers={"Authorization": "Bearer no"}).status_code == 401
    r = client.get("/cron/notify?morning=true", headers={"Authorization": "Bearer s3"})
    assert r.json()["result"] == "morning=True"
