"""U9 数据库直连查询（只读）。

与 ``api/sql.py`` 的「表结构探查」不同，本模块真正读取业务数据：
- ``query_table``：按 ``u9_schema.json`` 校验表名/字段名后，生成安全的
  SELECT 语句（标识符白名单 + 参数化 WHERE），支持过滤、排序、分页、总数。
- ``execute_readonly_sql``：执行单条只读 SELECT/WITH，供复杂查询使用；
  执行前做严格守卫，拒绝任何 DML/DDL、多语句、存储过程等。

⚠️ 数据库直连仅用于查询/排查。U9 的业务规则、审核流、编号规则都在服务端
（WebAPI）执行，绕过 WebAPI 直接写库会破坏数据一致性，因此本模块只读。
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, List, Optional, Sequence

from ..config import settings
from ..utils.sql import (
    _json_safe_rows,
    _quote_sql_identifier,
    _sql_columns,
    _sql_connect,
    _sql_rows_params,
    _validate_sql_identifier,
)
from ..utils.u9_schema import get_table, schema_status


# WHERE 支持的运算符（统一小写）
_FILTER_OPS = {
    "=", "==", "!=", "<>", ">", ">=", "<", "<=",
    "like", "not like", "in", "not in", "between",
    "is null", "is not null",
    "contains", "not contains", "startswith", "endswith",
}

# 禁止出现在只读 SQL 中的关键字（DML / DDL / 权限 / 过程 / 危险功能）
_FORBIDDEN_SQL_KEYWORDS = {
    "insert", "update", "delete", "merge", "upsert",
    "drop", "alter", "create", "truncate", "rename",
    "grant", "revoke", "deny",
    "exec", "execute", "call",
    "backup", "restore", "dbcc", "shutdown", "reconfigure",
    "bulk", "into", "waitfor", "openrowset", "openquery",
    "opendatasource", "openxml", "xp_cmdshell", "sp_executesql",
}

_ORDER_TOKEN_RE = re.compile(
    r"^(?P<col>[A-Za-z_][A-Za-z0-9_$#]{0,127})(?:\s+(?P<dir>ASC|DESC))?$",
    re.IGNORECASE,
)


class SqlQueryError(ValueError):
    """数据库直连查询的参数/安全问题。"""


def _require_db() -> None:
    if not settings._SQL_ENABLED:
        raise RuntimeError(
            "SQL Server 未配置，无法直接查询数据库。请设置 "
            "MCP_SQLSERVER_HOST / MCP_SQLSERVER_DATABASE / "
            "MCP_SQLSERVER_USER / MCP_SQLSERVER_PASSWORD 后重启服务。"
        )


def _db_schema() -> str:
    return _validate_sql_identifier(settings._SQL_SCHEMA or "dbo", "Schema")


def _column_map(columns: Iterable[str]) -> dict[str, str]:
    """小写列名 → 真实列名，用于大小写不敏感的参数校验。"""
    return {str(c).lower(): str(c) for c in columns if c}


def _resolve_column(name: str, column_map: dict[str, str]) -> str:
    key = (name or "").strip()
    if not key:
        raise SqlQueryError("字段名不能为空")
    hit = column_map.get(key.lower())
    if not hit:
        raise SqlQueryError(
            f"字段「{name}」不存在。可用字段：{', '.join(sorted(column_map.values()))[:800]}"
        )
    return hit


def _resolve_table(conn: Any, table_name: str) -> tuple[str, Optional[dict]]:
    """解析真实表名（大小写以数据库为准），并返回数据字典中的表定义。"""
    raw = (table_name or "").strip()
    if not raw:
        raise SqlQueryError("表名不能为空")
    _validate_sql_identifier(raw, "表名")

    dictionary = get_table(raw)
    candidate = dictionary["name"] if dictionary else raw
    rows = _sql_rows_params(
        conn,
        """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
          AND UPPER(TABLE_NAME) = UPPER(?)
          AND TABLE_TYPE = 'BASE TABLE'
        """,
        (_db_schema(), candidate),
    )
    if not rows:
        if dictionary:
            raise SqlQueryError(
                f"数据字典中存在表「{candidate}」，但当前数据库 {settings._SQL_DATABASE} "
                f"的 {settings._SQL_SCHEMA} 下没有该表。请确认连接的是正确的 U9 账套库。"
            )
        raise SqlQueryError(
            f"表「{raw}」不存在。可先用 u9_discover_tables 按业务关键字检索真实表名。"
        )
    return rows[0]["TABLE_NAME"], dictionary


def _default_columns(
    dictionary: Optional[dict],
    actual_columns: List[str],
    all_columns: bool,
) -> tuple[List[str], int]:
    """选择默认返回列。

    默认返回主键 + 前 40 个业务字段（跳过 CreatedOn/ModifiedOn/SysVersion 等审计列），
    避免大表一次返回几百列把响应撑爆；``all_columns=True`` 时返回全部。
    返回 (列名列表, 总列数)。
    """
    if all_columns:
        return list(actual_columns), len(actual_columns)

    actual_lower = {c.lower(): c for c in actual_columns}
    system_prefixes = (
        "created", "modified", "sysversion", "creator", "modifier",
        "updatetime", "updater", "timestamp", "rowversion",
    )

    ordered: List[str] = []
    if dictionary:
        primary = [
            c.get("name") for c in dictionary.get("columns") or []
            if c.get("primary_key") == "是" and c.get("name")
        ]
        for name in primary:
            hit = actual_lower.get(str(name).lower())
            if hit and hit not in ordered:
                ordered.append(hit)
        for column in dictionary.get("columns") or []:
            name = column.get("name")
            if not name:
                continue
            low = str(name).lower()
            if any(low.startswith(p) for p in system_prefixes):
                continue
            hit = actual_lower.get(low)
            if hit and hit not in ordered:
                ordered.append(hit)
            if len(ordered) >= 40:
                break

    if not ordered:
        ordered = [
            c for c in actual_columns
            if not any(c.lower().startswith(p) for p in system_prefixes)
        ][:40]

    return ordered or list(actual_columns)[:40], len(actual_columns)


def _build_where(
    filters: Optional[Sequence[Any]],
    column_map: dict[str, str],
) -> tuple[str, List[Any]]:
    """把结构化过滤条件编译成 WHERE 子句（列名白名单 + 参数占位符）。"""
    clauses: List[str] = []
    params: List[Any] = []

    for item in filters or []:
        if hasattr(item, "model_dump"):
            data = item.model_dump()
        elif isinstance(item, dict):
            data = item
        else:
            raise SqlQueryError("filters 的每一项都必须是 {column, operator, value} 结构")

        column = _resolve_column(str(data.get("column") or ""), column_map)
        raw_op = str(data.get("operator") or "=").strip().lower()
        op = {"==": "=", "<>": "!="}.get(raw_op, raw_op)
        if op not in _FILTER_OPS:
            raise SqlQueryError(
                f"不支持的运算符「{raw_op}」。可用：=, !=, >, >=, <, <=, like, in, "
                "between, is null, is not null, contains, startswith, endswith"
            )

        qcol = _quote_sql_identifier(column, "字段名")
        value = data.get("value")

        if op in ("is null", "is not null"):
            clauses.append(f"{qcol} IS {'NOT ' if op == 'is not null' else ''}NULL")
            continue
        if op in ("contains", "not contains", "startswith", "endswith"):
            text = "" if value is None else str(value)
            if op == "startswith":
                pattern = f"{text}%"
            elif op == "endswith":
                pattern = f"%{text}"
            else:
                pattern = f"%{text}%"
            clauses.append(f"{qcol} {'NOT ' if op.startswith('not ') else ''}LIKE ?")
            params.append(pattern)
            continue
        if op in ("in", "not in"):
            values = list(value) if isinstance(value, (list, tuple, set)) else [value]
            if not values:
                raise SqlQueryError(f"字段「{column}」使用 {op} 时 value 不能为空列表")
            placeholders = ", ".join("?" for _ in values)
            clauses.append(f"{qcol} {op.upper()} ({placeholders})")
            params.extend(values)
            continue
        if op == "between":
            values = list(value) if isinstance(value, (list, tuple)) else []
            if len(values) != 2:
                raise SqlQueryError(f"字段「{column}」使用 between 时 value 必须是两个元素的数组")
            clauses.append(f"{qcol} BETWEEN ? AND ?")
            params.extend(values)
            continue

        clauses.append(f"{qcol} {op.upper()}")
        params.append(value)

    return (" AND ".join(clauses), params)


def _build_order_by(
    order_by: str,
    column_map: dict[str, str],
    default_columns: Sequence[str],
) -> str:
    """编译 ORDER BY（列名白名单 + ASC/DESC 校验）。"""
    tokens: List[str] = []
    for raw in (order_by or "").split(","):
        token = raw.strip()
        if not token:
            continue
        m = _ORDER_TOKEN_RE.match(token)
        if not m:
            raise SqlQueryError(
                f"排序条件「{token}」非法。请使用「字段名 [ASC|DESC]」，多个字段用逗号分隔。"
            )
        column = _resolve_column(m.group("col"), column_map)
        direction = (m.group("dir") or "ASC").upper()
        tokens.append(f"{_quote_sql_identifier(column, '字段名')} {direction}")

    if not tokens:
        if default_columns:
            tokens = [f"{_quote_sql_identifier(default_columns[0], '字段名')} ASC"]
        else:
            # SQL Server 在 OFFSET/FETCH 时要求 ORDER BY
            tokens = ["(SELECT NULL)"]
    return ", ".join(tokens)


def query_table(
    table_name: str,
    columns: Optional[Sequence[str]] = None,
    filters: Optional[Sequence[Any]] = None,
    order_by: str = "",
    limit: int = 100,
    offset: int = 0,
    include_total: bool = False,
    all_columns: bool = False,
) -> dict:
    """按表名查询 U9 业务数据（只读，最多 1000 行）。"""
    _require_db()
    if limit < 1 or limit > 1000:
        raise SqlQueryError("limit 必须在 1~1000 之间")
    if offset < 0:
        raise SqlQueryError("offset 不能为负数")
    # 先校验标识符，非法表名在建立数据库连接之前就拒绝
    _validate_sql_identifier((table_name or "").strip(), "表名")

    conn = _sql_connect()
    try:
        try:
            conn.timeout = int(os.getenv("MCP_SQLSERVER_QUERY_TIMEOUT", "30"))
        except Exception:
            pass

        table, dictionary = _resolve_table(conn, table_name)
        actual_columns = _sql_columns(conn, _db_schema(), table)
        if not actual_columns:
            raise SqlQueryError(f"表「{table}」没有可读取的字段，或当前账号无权访问。")
        column_map = _column_map(actual_columns)

        if columns:
            selected = [_resolve_column(c, column_map) for c in columns]
        else:
            selected, _ = _default_columns(dictionary, actual_columns, all_columns)

        select_list = ", ".join(_quote_sql_identifier(c, "字段名") for c in selected)
        where_sql, params = _build_where(filters, column_map)
        order_sql = _build_order_by(order_by, column_map, selected)

        base = (
            f"FROM {_quote_sql_identifier(_db_schema(), 'Schema')}."
            f"{_quote_sql_identifier(table, '表名')}"
        )
        if where_sql:
            base += f" WHERE {where_sql}"

        sql = (
            f"SELECT {select_list} {base} ORDER BY {order_sql} "
            f"OFFSET {int(offset)} ROWS FETCH NEXT {int(limit) + 1} ROWS ONLY"
        )
        rows = _sql_rows_params(conn, sql, params)
        has_more = len(rows) > limit
        rows = rows[:limit]

        total = None
        if include_total:
            count_rows = _sql_rows_params(conn, f"SELECT COUNT(*) AS total {base}", params)
            total = count_rows[0]["total"] if count_rows else 0

        out: dict[str, Any] = {
            "table": table,
            "schema": _db_schema(),
            "database": settings._SQL_DATABASE,
            "source": "database",
            "total_columns": len(actual_columns),
            "columns": selected,
            "count": len(rows),
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "data": _json_safe_rows(rows),
        }
        if total is not None:
            out["total"] = total
        if dictionary:
            out["table_purpose"] = dictionary.get("purpose") or dictionary.get("desc") or ""
        if not columns and not all_columns and len(actual_columns) > len(selected):
            out["columns_truncated"] = True
            out["tip"] = (
                f"默认只返回 {len(selected)}/{len(actual_columns)} 个字段。"
                "需要其它字段请传 columns=[...]，或传 all_columns=true。"
            )
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _strip_literals_and_comments(sql: str) -> str:
    """去掉 SQL 字符串字面量、[标识符] 与注释，仅保留关键字骨架用于安全扫描。"""
    out: List[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        # 单引号字符串，'' 为转义
        if ch == "'":
            out.append(" ")
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        # 方括号标识符 [Table Name]
        if ch == "[":
            out.append(" ")
            i += 1
            while i < n:
                if sql[i] == "]":
                    i += 1
                    break
                i += 1
            continue
        # -- 行注释
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue
        # /* */ 块注释
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _guard_readonly_sql(sql: str) -> str:
    """只读 SQL 守卫：仅允许单条 SELECT / WITH，拒绝 DML/DDL/多语句/危险关键字。"""
    original = (sql or "").strip()
    if not original:
        raise SqlQueryError("SQL 不能为空")

    skeleton = _strip_literals_and_comments(original)

    # 多语句检测：只允许末尾一个分号
    trimmed = skeleton.rstrip()
    if trimmed.endswith(";"):
        trimmed = trimmed[:-1]
    if ";" in trimmed:
        raise SqlQueryError("只允许执行单条 SQL，不能包含多个语句（分号）。")

    # 必须以 SELECT 或 WITH 开头
    first_match = re.match(r"\s*([A-Za-z_]+)", trimmed)
    first_keyword = first_match.group(1) if first_match else ""
    if not first_keyword or first_keyword.lower() not in ("select", "with"):
        raise SqlQueryError(
            f"只允许只读查询：SQL 必须以 SELECT 或 WITH 开头"
            f"（当前语句以 {first_keyword.upper() or '空'} 开头）。"
        )

    # 禁止关键字（词边界，忽略大小写）
    lowered = trimmed.lower()
    for keyword in sorted(_FORBIDDEN_SQL_KEYWORDS):
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])", lowered):
            raise SqlQueryError(
                f"SQL 中包含禁止的关键字「{keyword.upper()}」。本工具只允许只读 SELECT 查询。"
            )

    # 去掉末尾分号后返回，避免 pyodbc 执行多语句
    safe = original.rstrip()
    if safe.endswith(";"):
        safe = safe[:-1].rstrip()
    return safe


def execute_readonly_sql(
    sql: str,
    params: Optional[Sequence[Any]] = None,
    max_rows: int = 500,
) -> dict:
    """执行单条只读 SQL（SELECT/WITH），最多返回 max_rows 行。"""
    _require_db()
    if max_rows < 1 or max_rows > 5000:
        raise SqlQueryError("max_rows 必须在 1~5000 之间")

    safe_sql = _guard_readonly_sql(sql)
    conn = _sql_connect()
    try:
        try:
            conn.timeout = int(os.getenv("MCP_SQLSERVER_QUERY_TIMEOUT", "30"))
        except Exception:
            pass

        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(safe_sql, list(params))
            else:
                cursor.execute(safe_sql)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            fetched = cursor.fetchmany(max_rows + 1)
            truncated = len(fetched) > max_rows
            rows = [dict(zip(columns, row)) for row in fetched[:max_rows]]
        finally:
            cursor.close()

        return {
            "source": "database",
            "database": settings._SQL_DATABASE,
            "schema": settings._SQL_SCHEMA,
            "count": len(rows),
            "max_rows": max_rows,
            "truncated": truncated,
            "columns": columns,
            "data": _json_safe_rows(rows),
            "tip": (
                f"结果超过 {max_rows} 行，已截断。请缩小查询范围或调大 max_rows。"
                if truncated else None
            ),
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


def database_status() -> dict:
    """返回数据库直连配置状态（不建立连接）。"""
    return {
        "configured": bool(settings._SQL_ENABLED),
        "host": settings._SQL_HOST or None,
        "port": settings._SQL_PORT or None,
        "database": settings._SQL_DATABASE or None,
        "schema": settings._SQL_SCHEMA or None,
        "readonly": True,
        "schema_source": schema_status(),
    }
