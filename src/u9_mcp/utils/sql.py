"""SQL Server 只读探查/查询工具。"""

import base64
import datetime as _dt
import decimal
import os
import re
from typing import Any, Iterable, List, Sequence, Tuple

from ..config.settings import _SQL_DATABASE, _SQL_ENABLED, _SQL_HOST, _SQL_PASSWORD, _SQL_PORT, _SQL_USER



# ─────────────────────────────────────────────
# SQL Server 探查工具（可选功能）
# ─────────────────────────────────────────────

# U9 数据字典中的表名/字段名均只含字母、数字、下划线和少量 #/$，不接受空格、
# 引号、分号等，避免把调用方传入的内容直接拼进 SQL（旧实现存在注入风险）。
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]{0,127}$")


def _validate_sql_identifier(name: str, kind: str = "标识符") -> str:
    """校验并返回 SQL 标识符（表名/列名/Schema）。

    只允许字母/数字/下划线/$/#，且必须以字母或下划线开头。U9 的真实表名
    （PM_PurchaseOrder、CBO_ItemMaster）和字段名（FBillNo、Code）都符合该规则。

    Raises:
        ValueError: 非法标识符。
    """
    value = (name or "").strip()
    if not value or not _SQL_IDENTIFIER_RE.match(value):
        raise ValueError(
            f"非法{kind}「{name}」。只允许字母、数字、下划线、$、#，"
            "且必须以字母或下划线开头（U9 表名/字段名符合此规则）。"
        )
    return value


def _quote_sql_identifier(name: str, kind: str = "标识符") -> str:
    """校验并以 ``[name]`` 形式引用标识符，供 SQL Server 使用。"""
    return "[" + _validate_sql_identifier(name, kind) + "]"


def _sql_connect():
    """建立 SQL Server 连接"""
    try:
        import pyodbc
    except ImportError:
        raise RuntimeError(
            "pyodbc 未安装，请运行：pip install pyodbc\n"
            "SQL Server 探查功能需要 pyodbc 驱动。"
        )
    if not _SQL_ENABLED:
        raise RuntimeError(
            "SQL Server 未配置。请设置以下环境变量：\n"
            "MCP_SQLSERVER_HOST / MCP_SQLSERVER_USER / MCP_SQLSERVER_PASSWORD / MCP_SQLSERVER_DATABASE"
        )
    driver = os.getenv("MCP_SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={_SQL_HOST},{_SQL_PORT};"
        f"DATABASE={_SQL_DATABASE};"
        f"UID={_SQL_USER};PWD={_SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=10)


def _sql_rows(conn, query: str) -> List[dict]:
    """执行只读查询，返回行列表（字典格式）"""
    return _sql_rows_params(conn, query)


def _sql_rows_params(conn, query: str, params: Sequence[Any] = ()) -> List[dict]:
    """执行参数化只读查询，返回行列表（字典格式）。

    使用 ``?`` 占位符 + 参数列表，避免把用户输入直接拼进 SQL。
    """
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(query, list(params))
        else:
            cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(zip(columns, row)))
        return rows
    finally:
        cursor.close()


def _json_safe(value: Any) -> Any:
    """把 pyodbc 返回的 SQL 类型转换成 JSON 可序列化类型。

    Decimal → int/float，datetime/date/time → ISO 字符串，bytes → base64 字符串。
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        # 整数金额保持整数形态，避免 100.0 这种噪声
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat(sep=" ") if isinstance(value, _dt.datetime) else value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    return str(value)


def _json_safe_rows(rows: Iterable[dict]) -> List[dict]:
    """逐行转换 SQL 返回值，保证能被 json.dumps 序列化。"""
    return [{key: _json_safe(value) for key, value in row.items()} for row in rows]


def _sql_columns(conn, schema: str, table: str) -> List[str]:
    """读取指定表的真实列名（参数化查询 INFORMATION_SCHEMA）。"""
    rows = _sql_rows_params(
        conn,
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """,
        (schema, table),
    )
    return [row["COLUMN_NAME"] for row in rows]

