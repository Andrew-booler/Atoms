"""后端-集成-09：routers/settings.py — 管理端配置读写。

所有读写都指向 tmp_path 下的临时文件，绝不接触仓库内真实 .env。
"""
import pytest

from core import auth as core_auth
from core.config import settings
from routers import settings as settings_module


@pytest.fixture
def jwt_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "settings-test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    for name in ("jwt_secret_key", "jwt_algorithm", "jwt_expire_minutes"):
        settings.__dict__.pop(name, None)
    yield
    for name in ("jwt_secret_key", "jwt_algorithm", "jwt_expire_minutes"):
        settings.__dict__.pop(name, None)


@pytest.fixture
def temp_env_files(tmp_path, monkeypatch):
    backend = tmp_path / "backend.env"
    frontend = tmp_path / "frontend.env"

    def fake_path(env_type: str):
        if env_type == "backend":
            return backend
        if env_type == "frontend":
            return frontend
        raise ValueError("Invalid env_type")

    monkeypatch.setattr(settings_module, "get_env_file_path", fake_path)
    return backend, frontend


def _token(role: str) -> str:
    return core_auth.create_access_token({"sub": "admin-1", "email": "admin@example.test", "role": role})


def _headers(role: str = "admin") -> dict:
    return {"Authorization": f"Bearer {_token(role)}"}


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


async def test_get_settings_requires_admin(api_client, jwt_env, temp_env_files):
    assert (await api_client.get("/api/v1/admin/settings")).status_code == 401
    forbidden = await api_client.get("/api/v1/admin/settings", headers=_headers("user"))
    assert forbidden.status_code == 403


async def test_get_settings_reads_both_env_files(api_client, jwt_env, temp_env_files):
    backend, frontend = temp_env_files
    _write(backend, "# 注释\nDATABASE_URL=postgresql://demo\nPORT=8000\nUNKNOWN_KEY=1\n")
    _write(frontend, "VITE_API_BASE_URL=http://localhost:8000\n")

    response = await api_client.get("/api/v1/admin/settings", headers=_headers())
    body = response.json()

    assert response.status_code == 200
    assert body["backend_vars"]["DATABASE_URL"]["value"] == "postgresql://demo"
    assert body["backend_vars"]["DATABASE_URL"]["description"] == "Database connection string"
    assert body["backend_vars"]["PORT"]["description"] == "Server port"
    assert body["backend_vars"]["UNKNOWN_KEY"]["description"] == ""
    assert body["frontend_vars"]["VITE_API_BASE_URL"]["description"] == "Base API URL"


async def test_get_settings_returns_empty_for_missing_files(api_client, jwt_env, temp_env_files):
    response = await api_client.get("/api/v1/admin/settings", headers=_headers())

    assert response.status_code == 200
    assert response.json() == {"backend_vars": {}, "frontend_vars": {}}


async def test_put_backend_setting_updates_file(api_client, jwt_env, temp_env_files):
    backend, _ = temp_env_files
    _write(backend, "PORT=8000\nDATABASE_URL=postgresql://demo\n")

    response = await api_client.put(
        "/api/v1/admin/settings/backend/PORT", json={"value": "9000"}, headers=_headers()
    )

    assert response.status_code == 200
    assert "restart required" in response.json()["message"]
    content = backend.read_text(encoding="utf-8").splitlines()
    assert "PORT=9000" in content
    assert "DATABASE_URL=postgresql://demo" in content


async def test_put_frontend_setting_updates_file(api_client, jwt_env, temp_env_files):
    _, frontend = temp_env_files

    response = await api_client.put(
        "/api/v1/admin/settings/frontend/VITE_API_BASE_URL",
        json={"value": "http://localhost:9000"},
        headers=_headers(),
    )

    assert response.status_code == 200
    assert frontend.read_text(encoding="utf-8") == "VITE_API_BASE_URL=http://localhost:9000\n"


async def test_post_setting_adds_new_variable(api_client, jwt_env, temp_env_files):
    backend, frontend = temp_env_files

    backend_response = await api_client.post(
        "/api/v1/admin/settings/backend/NEW_KEY", json={"value": "new-value"}, headers=_headers()
    )
    frontend_response = await api_client.post(
        "/api/v1/admin/settings/frontend/VITE_NEW_KEY", json={"value": "new"}, headers=_headers()
    )

    assert backend_response.status_code == 200
    assert "NEW_KEY=new-value" in backend.read_text(encoding="utf-8")
    assert frontend_response.status_code == 200
    assert "VITE_NEW_KEY=new" in frontend.read_text(encoding="utf-8")


async def test_delete_setting_removes_variable(api_client, jwt_env, temp_env_files):
    backend, frontend = temp_env_files
    _write(backend, "PORT=8000\nKEEP=1\n")
    _write(frontend, "VITE_OLD=1\nVITE_KEEP=1\n")

    backend_response = await api_client.delete("/api/v1/admin/settings/backend/PORT", headers=_headers())
    frontend_response = await api_client.delete("/api/v1/admin/settings/frontend/VITE_OLD", headers=_headers())

    assert backend_response.status_code == 200
    assert "PORT=" not in backend.read_text(encoding="utf-8")
    assert "KEEP=1" in backend.read_text(encoding="utf-8")
    assert frontend_response.status_code == 200
    assert "VITE_KEEP=1" in frontend.read_text(encoding="utf-8")


async def test_delete_missing_setting_reports_server_error(api_client, jwt_env, temp_env_files):
    backend, _ = temp_env_files
    _write(backend, "PORT=8000\n")

    response = await api_client.delete("/api/v1/admin/settings/backend/ABSENT", headers=_headers())

    # 当前实现把 404 包进通用异常分支，因此对外表现为 500；此断言固定现状。
    assert response.status_code == 500
    assert "does not exist" in response.json()["detail"]


def test_get_env_file_path_rejects_unknown_type():
    with pytest.raises(ValueError, match="Invalid env_type"):
        settings_module.get_env_file_path("other")
