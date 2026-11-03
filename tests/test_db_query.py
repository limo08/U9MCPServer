"""数据库直连查询（只读）回归测试。

覆盖：
- 只读 SQL 守卫（拒绝 DML/DDL/多语句/EXEC/SELECT INTO）
- 结构化过滤条件编译（参数化、列名白名单）
- query_table 的分页、截断、总数、JSON 安全转换
- 未配置数据库时的明确错误
"""

import datetime
import decimal

import pytest

from u9_mcp.config import settings
from u9_mcp.services import db_query
from u9_mcp.services.db_query import (
    SqlQueryError,
    _build_where,
    _guard_readonly_sql,
    database_status,
    execute_readonly_sql,
    query_table,
)
from u9_mcp.utils.sql import _json_safe, _json_safe_rows


# ─── 只读 SQL 守卫 ─────────────────────────────

@pytest.mark.parametrize("sql", [
    "SELECT * FROM PM_PurchaseOrder",
    "select h.DocNo from PM_PurchaseOrder h where h.Status = ?",
    "WITH x AS (SELECT 1 AS n) SELECT n FROM x",
    "SELECT [Update] FROM [PM_PurchaseOrder];",
])
def test_guard_allows_readonly(sql):
    assert _guard_readonly_sql(sql).startswith(("SELECT", "select", "WITH", "WITH"))


@pytest.mark.parametrize("sql,keyword", [
    ("UPDATE PM_PurchaseOrder SET Status = 1", "UPDATE"),
    ("DELETE FROM PM_PurchaseOrder", "DELETE"),
    ("INSERT INTO PM_PurchaseOrder (ID) VALUES (1)", "INSERT"),
    ("DROP TABLE PM_PurchaseOrder", "DROP"),
    ("ALTER TABLE PM_PurchaseOrder ADD X INT", "ALTER"),
    ("EXEC sp_who", "EXEC"),
    ("SELECT * INTO tmp FROM PM_PurchaseOrder", "INTO"),
    ("SELECT 1; SELECT 2", "分号"),
    ("SELECT * FROM OPENROWSET('x','y','z')", "OPENROWSET"),
    ("SELECT * FROM PM_PurchaseOrder -- ; DROP TABLE x", None),
])
def test_guard_rejects_unsafe(sql, keyword):
    if keyword is None:
        # 注释里的内容不应触发误报，但 -- 后的 DROP 已被注释掉，SQL 本身是只读的
        assert _guard_readonly_sql(sql)
        return
    with pytest.raises(SqlQueryError) as exc:
        _guard_readonly_sql(sql)
    assert keyword in str(exc.value) or keyword == "分号"


def test_guard_ignores_keywords_in_string_literals():
    sql = "SELECT * FROM PM_PurchaseOrder WHERE DocNo = 'DELETE;DROP TABLE X'"
    assert _guard_readonly_sql(sql) == sql


def test_guard_allows_trailing_semicolon_only():
    assert _guard_readonly_sql("SELECT 1;") == "SELECT 1"
    with pytest.raises(SqlQueryError):
        _guard_readonly_sql("SELECT 1;;")


# ─── 过滤条件编译 ─────────────────────────────

COLUMN_MAP = {"id": "ID", "docno": "DocNo", "businessdate": "BusinessDate", "status": "Status"}


def test_build_where_parameterizes_all_values():
    where, params = _build_where([
        {"column": "DocNo", "operator": "contains", "value": "PO'26"},
        {"column": "status", "operator": "in", "value": [1, 2]},
        {"column": "BusinessDate", "operator": "between", "value": ["2026-01-01", "2026-01-31"]},
        {"column": "ID", "operator": "is not null"},
    ], COLUMN_MAP)

    assert "[DocNo] LIKE ?" in where
    assert "[Status] IN (?, ?)" in where
    assert "[BusinessDate] BETWEEN ? AND ?" in where
    assert "[ID] IS NOT NULL" in where
    assert params == ["%PO'26%", 1, 2, "2026-01-01", "2026-01-31"]


def test_build_where_rejects_unknown_column():
    with pytest.raises(SqlQueryError) as exc:
        _build_where([{"column": "DocNo]; DROP TABLE x --", "value": 1}], COLUMN_MAP)
    assert "不存在" in str(exc.value)


def test_build_where_rejects_unknown_operator():
    with pytest.raises(SqlQueryError):
        _build_where([{"column": "DocNo", "operator": "regexp", "value": "x"}], COLUMN_MAP)


def test_build_where_in_requires_values():
    with pytest.raises(SqlQueryError):
        _build_where([{"column": "DocNo", "operator": "in", "value": []}], COLUMN_MAP)


# ─── query_table ─────────────────────────────

class FakeConn:
    def __init__(self):
        self.timeout = None
        self.closed = False

    def close(self):
        self.closed = True


DICTIONARY = {
    "name": "PM_PurchaseOrder",
    "purpose": "采购订单主表",
    "columns": [
        {"name": "ID", "primary_key": "是"},
        {"name": "DocNo", "primary_key": "否"},
        {"name": "BusinessDate", "primary_key": "否"},
        {"name": "TotalMoney", "primary_key": "否"},
        {"name": "CreatedOn", "primary_key": "否"},
    ],
}


def _patch_query_env(monkeypatch, rows):
    conn = FakeConn()
    calls = []

    monkeypatch.setattr(settings, "_SQL_ENABLED", True)
    monkeypatch.setattr(settings, "_SQL_DATABASE", "U9TEST")
    monkeypatch.setattr(settings, "_SQL_SCHEMA", "dbo")
    monkeypatch.setattr(db_query, "_sql_connect", lambda: conn)
    monkeypatch.setattr(db_query, "get_table", lambda name: DICTIONARY)

    def fake_columns(_conn, _schema, _table):
        return ["ID", "DocNo", "BusinessDate", "TotalMoney", "CreatedOn", "SysVersion"]

    monkeypatch.setattr(db_query, "_sql_columns", fake_columns)

    def fake_rows(_conn, sql, params=()):
        calls.append((sql, list(params)))
        if "INFORMATION_SCHEMA.TABLES" in sql:
            return [{"TABLE_NAME": "PM_PurchaseOrder"}]
        if "COUNT(*)" in sql:
            return [{"total": 123}]
        return rows

    monkeypatch.setattr(db_query, "_sql_rows_params", fake_rows)
    return conn, calls


def test_query_table_paginates_and_truncates(monkeypatch):
    rows = [
        {"ID": 1, "DocNo": "PO001", "BusinessDate": datetime.datetime(2026, 1, 2, 3, 4, 5),
         "TotalMoney": decimal.Decimal("100.50")},
        {"ID": 2, "DocNo": "PO002", "BusinessDate": datetime.date(2026, 1, 3),
         "TotalMoney": decimal.Decimal("200")},
        {"ID": 3, "DocNo": "PO003", "BusinessDate": datetime.date(2026, 1, 4),
         "TotalMoney": decimal.Decimal("300")},
    ]
    conn, calls = _patch_query_env(monkeypatch, rows)

    result = query_table(
        "PM_PurchaseOrder",
        filters=[{"column": "DocNo", "operator": "contains", "value": "PO00"}],
        order_by="BusinessDate DESC",
        limit=2,
        offset=10,
        include_total=True,
    )

    assert conn.closed is True
    assert result["table"] == "PM_PurchaseOrder"
    assert result["count"] == 2
    assert result["has_more"] is True
    assert result["total"] == 123
    assert result["data"][0]["TotalMoney"] == 100.5
    assert result["data"][0]["BusinessDate"] == "2026-01-02 03:04:05"
    assert result["data"][1]["TotalMoney"] == 200

    # 默认列：主键 + 业务字段，跳过审计列
    assert result["columns"][0] == "ID"
    assert "CreatedOn" not in result["columns"]
    assert "SysVersion" not in result["columns"]

    select_sql, select_params = calls[1]
    assert "OFFSET 10 ROWS FETCH NEXT 3 ROWS ONLY" in select_sql
    assert "[BusinessDate] DESC" in select_sql
    assert select_params == ["%PO00%"]

    count_sql, count_params = calls[2]
    assert count_sql.startswith("SELECT COUNT(*)")
    assert count_params == ["%PO00%"]


def test_query_table_explicit_columns_and_all_columns(monkeypatch):
    rows = [{"ID": 1, "DocNo": "PO001", "CreatedOn": None, "SysVersion": 2}]
    _patch_query_env(monkeypatch, rows)

    result = query_table("PM_PurchaseOrder", columns=["docno", "id"], limit=1)
    assert result["columns"] == ["DocNo", "ID"]

    result = query_table("PM_PurchaseOrder", all_columns=True, limit=1)
    assert result["columns"] == ["ID", "DocNo", "BusinessDate", "TotalMoney", "CreatedOn", "SysVersion"]
    assert "columns_truncated" not in result


def test_query_table_requires_database(monkeypatch):
    monkeypatch.setattr(settings, "_SQL_ENABLED", False)
    with pytest.raises(RuntimeError) as exc:
        query_table("PM_PurchaseOrder")
    assert "MCP_SQLSERVER" in str(exc.value)


def test_query_table_rejects_bad_table_identifier(monkeypatch):
    monkeypatch.setattr(settings, "_SQL_ENABLED", True)
    with pytest.raises(ValueError):
        query_table("PM_PurchaseOrder; DROP TABLE X")


# ─── execute_readonly_sql ─────────────────────

class FakeCursor:
    def __init__(self, columns, rows):
        self.description = [(c,) for c in columns]
        self._rows = rows
        self.closed = False
        self.executed = None

    def execute(self, sql, params=None):
        self.executed = (sql, params)

    def fetchmany(self, n):
        return self._rows[:n]

    def close(self):
        self.closed = True


class FakeCursorConn(FakeConn):
    def __init__(self, cursor):
        super().__init__()
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_execute_readonly_sql_truncates(monkeypatch):
    rows = [{"ID": 1}, {"ID": 2}, {"ID": 3}]
    cursor = FakeCursor(["ID"], rows)
    conn = FakeCursorConn(cursor)
    monkeypatch.setattr(settings, "_SQL_ENABLED", True)
    monkeypatch.setattr(settings, "_SQL_DATABASE", "U9TEST")
    monkeypatch.setattr(settings, "_SQL_SCHEMA", "dbo")
    monkeypatch.setattr(db_query, "_sql_connect", lambda: conn)

    result = execute_readonly_sql("SELECT ID FROM PM_PurchaseOrder WHERE ID > ?", [0], max_rows=2)

    assert result["count"] == 2
    assert result["truncated"] is True
    assert result["columns"] == ["ID"]
    assert cursor.executed == ("SELECT ID FROM PM_PurchaseOrder WHERE ID > ?", [0])
    assert cursor.closed is True
    assert conn.closed is True


def test_execute_readonly_sql_rejects_before_connecting(monkeypatch):
    monkeypatch.setattr(settings, "_SQL_ENABLED", True)

    called = []
    monkeypatch.setattr(db_query, "_sql_connect", lambda: called.append(True))

    with pytest.raises(SqlQueryError):
        execute_readonly_sql("DELETE FROM PM_PurchaseOrder")
    assert called == []


# ─── JSON 安全 / 状态 ─────────────────────────────

def test_json_safe_converts_decimal_and_dates():
    assert _json_safe(decimal.Decimal("10.00")) == 10
    assert _json_safe(decimal.Decimal("10.25")) == 10.25
    assert _json_safe(datetime.date(2026, 1, 2)) == "2026-01-02"
    assert _json_safe(b"abc") == "YWJj"
    assert _json_safe_rows([{"x": decimal.Decimal("1.5")}]) == [{"x": 1.5}]


def test_database_status_readonly(monkeypatch):
    monkeypatch.setattr(settings, "_SQL_ENABLED", True)
    status = database_status()
    assert status["configured"] is True
    assert status["readonly"] is True
