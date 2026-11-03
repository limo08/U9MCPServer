"""`u9-mcp --check` 配置检查：U9 接口或数据库直连，至少一种可用。"""

import pytest

from u9_mcp import server
from u9_mcp.config import settings


def _clear_u9(monkeypatch):
    for name in ("SERVER_URL", "TOKEN", "CLIENT_ID", "CLIENT_SECRET",
                 "ENT_CODE", "ORG_CODE", "USERNAME"):
        monkeypatch.setattr(server, name, "")


def _set_u9(monkeypatch, url="https://u9.example.com"):
    monkeypatch.setattr(server, "SERVER_URL", url)
    monkeypatch.setattr(server, "TOKEN", "")
    monkeypatch.setattr(server, "CLIENT_ID", "client-1")
    monkeypatch.setattr(server, "CLIENT_SECRET", "secret")
    monkeypatch.setattr(server, "ENT_CODE", "ent-1")
    monkeypatch.setattr(server, "ORG_CODE", "org-1")
    monkeypatch.setattr(server, "USERNAME", "demo")


def _clear_db(monkeypatch):
    monkeypatch.setattr(settings, "_SQL_HOST", "")
    monkeypatch.setattr(settings, "_SQL_PORT", "1433")
    monkeypatch.setattr(settings, "_SQL_DATABASE", "")
    monkeypatch.setattr(settings, "_SQL_USER", "")
    monkeypatch.setattr(settings, "_SQL_PASSWORD", "")


def _set_db(monkeypatch):
    monkeypatch.setattr(settings, "_SQL_HOST", "db.example.com")
    monkeypatch.setattr(settings, "_SQL_PORT", "1433")
    monkeypatch.setattr(settings, "_SQL_DATABASE", "U9DB")
    monkeypatch.setattr(settings, "_SQL_USER", "reader")
    monkeypatch.setattr(settings, "_SQL_PASSWORD", "secret")


class _FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query):
        self.executed.append(query)

    def fetchone(self):
        return (1,)

    def close(self):
        pass


class _FakeConnection:
    def cursor(self):
        return _FakeCursor()

    def close(self):
        pass


@pytest.fixture
def fake_login(monkeypatch):
    async def login():
        return "0123456789abcdef"

    monkeypatch.setattr(server, "_login", login)


@pytest.fixture
def fake_db(monkeypatch):
    monkeypatch.setattr("u9_mcp.utils.sql._sql_connect", lambda: _FakeConnection())


def test_no_access_method_configured(monkeypatch, capsys):
    _clear_u9(monkeypatch)
    _clear_db(monkeypatch)

    assert server._run_check() == 1
    out = capsys.readouterr().out
    assert "至少需要配置一种" in out
    assert "U9 接口缺少" in out
    assert "数据库缺少" in out


def test_placeholder_u9_url_is_not_configured(monkeypatch, capsys):
    _set_u9(monkeypatch, url="https://your-server/u9c")
    _clear_db(monkeypatch)

    assert server._run_check() == 1
    assert "U9_API_SERVER_URL" in capsys.readouterr().out


def test_u9_only_passes(monkeypatch, capsys, fake_login):
    _set_u9(monkeypatch)
    _clear_db(monkeypatch)

    assert server._run_check() == 0
    out = capsys.readouterr().out
    assert "U9C 认证成功" in out
    assert "SQL Server 直连未完整配置，跳过数据库检查" in out


def test_database_only_passes(monkeypatch, capsys, fake_db):
    _clear_u9(monkeypatch)
    _set_db(monkeypatch)

    assert server._run_check() == 0
    out = capsys.readouterr().out
    assert "数据库连接成功" in out
    assert "U9 接口未完整配置，跳过登录检查" in out


def test_both_methods_present_and_passing(monkeypatch, capsys, fake_login, fake_db):
    _set_u9(monkeypatch)
    _set_db(monkeypatch)

    assert server._run_check() == 0
    out = capsys.readouterr().out
    assert "U9C 认证成功" in out
    assert "数据库连接成功" in out


def test_partial_u9_with_database_still_passes(monkeypatch, capsys, fake_db):
    _set_u9(monkeypatch)
    monkeypatch.setattr(server, "CLIENT_SECRET", "")
    _set_db(monkeypatch)

    assert server._run_check() == 0
    out = capsys.readouterr().out
    assert "缺少: U9_API_CLIENT_SECRET" in out
    assert "数据库连接成功" in out


def test_u9_auth_failure_returns_3(monkeypatch, capsys):
    _set_u9(monkeypatch)
    _clear_db(monkeypatch)

    async def bad_login():
        raise RuntimeError("账号或密码错误")

    monkeypatch.setattr(server, "_login", bad_login)

    assert server._run_check() == 3
    assert "账号或密码错误" in capsys.readouterr().out


def test_database_failure_returns_5(monkeypatch, capsys):
    _clear_u9(monkeypatch)
    _set_db(monkeypatch)

    def bad_connect():
        raise RuntimeError("pyodbc 未安装")

    monkeypatch.setattr("u9_mcp.utils.sql._sql_connect", bad_connect)

    assert server._run_check() == 5
    out = capsys.readouterr().out
    assert "数据库连接失败" in out
    assert "pyodbc 未安装" in out


def test_env_reads_u9_prefix(monkeypatch):
    from u9_mcp.config.settings import _env

    monkeypatch.setenv("U9_DEMO_TOKEN", "u9-value")
    assert _env("DEMO_TOKEN") == "u9-value"

    monkeypatch.delenv("U9_DEMO_TOKEN")
    assert _env("DEMO_TOKEN", "default-value") == "default-value"


def test_api_env_reads_only_api_prefix(monkeypatch):
    """接口变量只认 U9_API_*，旧版 U9_* 不再生效。"""
    from u9_mcp.config.settings import _api_env

    monkeypatch.setenv("U9_API_DEMO_TOKEN", "new-value")
    monkeypatch.setenv("U9_DEMO_TOKEN", "old-value")
    assert _api_env("DEMO_TOKEN") == "new-value"

    monkeypatch.delenv("U9_API_DEMO_TOKEN")
    assert _api_env("DEMO_TOKEN", "default-value") == "default-value"


def test_one_failing_method_still_passes_if_other_works(monkeypatch, capsys, fake_db):
    """U9 登录失败但数据库可用：服务仍可启动，检查返回 0 并给出 WARN。"""
    _set_u9(monkeypatch)
    _set_db(monkeypatch)

    async def bad_login():
        raise RuntimeError("U9 登录失败")

    monkeypatch.setattr(server, "_login", bad_login)

    assert server._run_check() == 0
    out = capsys.readouterr().out
    assert "部分访问方式未通过检查" in out
    assert "数据库连接成功" in out
