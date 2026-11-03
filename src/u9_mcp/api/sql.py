"""api.sql —— U9 数据库/数据字典探查工具。"""


from . import mcp
from ..config.form_catalog import FORM_CATALOG
from ..config.settings import _SQL_DATABASE, _SQL_ENABLED, _SQL_SCHEMA
from ..models.sql import (
    MetadataCandidateInput,
    SqlDescribeInput,
    SqlExecuteInput,
    SqlSearchInput,
    SqlTableQueryInput,
)
from ..services.db_query import database_status, execute_readonly_sql, query_table
from ..utils.formatting import _fmt
from ..utils.sql import _sql_connect, _sql_rows_params, _validate_sql_identifier
from ..utils.u9_schema import (
    dictionary_columns,
    get_table,
    schema_status,
    search_columns,
    search_tables,
    table_schema,
)


def _dictionary_table_rows(keyword: str, limit: int) -> list[dict]:
    """把数据字典检索结果转成与 INFORMATION_SCHEMA 相近的行结构。"""
    return [
        {
            "TABLE_NAME": item["table"],
            "TABLE_TYPE": "U9_DICTIONARY",
            "TABLE_PURPOSE": item["purpose"],
            "COLUMN_COUNT": item["column_count"],
            "MATCH_SCORE": item["match_score"],
        }
        for item in search_tables(keyword, limit)
    ]


def _database_table_rows(pattern: str, limit: int) -> list[dict]:
    schema = _validate_sql_identifier(_SQL_SCHEMA or "dbo", "Schema")
    conn = _sql_connect()
    try:
        return _sql_rows_params(conn, """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = ?
              AND TABLE_TYPE = 'BASE TABLE'
              AND (TABLE_NAME LIKE ? OR TABLE_NAME LIKE ?)
            ORDER BY TABLE_NAME
            OFFSET 0 ROWS FETCH NEXT {int(limit)} ROWS ONLY
        """, (schema, f"%{pattern}%", f"%{pattern.upper()}%"))
    finally:
        conn.close()


def _database_column_rows(pattern: str, limit: int) -> list[dict]:
    schema = _validate_sql_identifier(_SQL_SCHEMA or "dbo", "Schema")
    conn = _sql_connect()
    try:
        return _sql_rows_params(conn, """
            SELECT
                c.TABLE_NAME,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                c.ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t
              ON c.TABLE_SCHEMA = t.TABLE_SCHEMA
             AND c.TABLE_NAME = t.TABLE_NAME
             AND t.TABLE_TYPE = 'BASE TABLE'
            WHERE c.TABLE_SCHEMA = ?
              AND (c.COLUMN_NAME LIKE ? OR c.COLUMN_NAME LIKE ?)
            ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
            OFFSET 0 ROWS FETCH NEXT {int(limit)} ROWS ONLY
        """, (schema, f"%{pattern}%", f"%{pattern.upper()}%"))
    finally:
        conn.close()


def _dictionary_column_rows(keyword: str, limit: int) -> list[dict]:
    return [
        {
            "TABLE_NAME": item["table"],
            "TABLE_PURPOSE": item["table_purpose"],
            "COLUMN_NAME": item["column"],
            "DATA_TYPE": item["type"],
            "CHARACTER_MAXIMUM_LENGTH": item["length"],
            "IS_NULLABLE": item["nullable"],
            "IS_PRIMARY_KEY": item["primary_key"],
            "COLUMN_PURPOSE": item["purpose"],
        }
        for item in search_columns(keyword, limit)
    ]


@mcp.tool(
    name="u9_discover_tables",
    annotations={"title": "搜索 U9 数据表", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True}
)
async def u9_discover_tables(params: SqlSearchInput) -> str:
    """搜索 U9 数据表（优先查 SQL Server 系统目录，未配置数据库时回退到 U9 数据字典）。

    适用场景：
    - 想知道"采购"相关的表有哪些
    - 快速定位业务表名，不记得确切名称时
    - 配合 u9_discover_columns 一起使用，先找表再看字段

    U9 常见模块前缀：
    - PM_：采购（PM_PurchaseOrder 采购订单、PM_POLine 采购订单行）
    - SM_：销售（SM_SO 销售订单、SM_Ship 销售出库单）
    - InvDoc_：库存（InvDoc_OnStoreCheck 采购入库单、InvDoc_MiscShip 其他出库单）
    - CBO_：基础资料（CBO_ItemMaster 物料、CBO_Customer 客户、CBO_Supplier 供应商）
    - AP_ / AR_：应付 / 应收
    - MO_：生产制造

    搜索范围：SQL Server 系统目录（information_schema.TABLES / sys.tables），
    以及本地 U9 数据字典（u9_schema.json，可用 U9_SCHEMA_FILE 指定路径）。

    Returns:
        str: 表名列表，含表名、类型、用途/字段数
    """
    if not params.pattern:
        return _fmt({
            "tip": "请提供搜索关键字，如 pattern='purchase'、pattern='采购订单' 或 pattern='PM_'",
            "schema": schema_status(),
        })

    dictionary_rows = _dictionary_table_rows(params.pattern, params.limit)
    database_rows: list[dict] = []
    database_error = None
    if _SQL_ENABLED:
        try:
            database_rows = _database_table_rows(params.pattern, params.limit)
        except Exception as exc:
            database_error = str(exc)

    if not database_rows and not dictionary_rows:
        payload = {
            "pattern": params.pattern,
            "schema": _SQL_SCHEMA,
            "database": _SQL_DATABASE,
            "count": 0,
            "tables": [],
            "schema_source": schema_status(),
        }
        if database_error:
            payload["error"] = database_error
        return _fmt(payload)

    rows = database_rows or dictionary_rows
    return _fmt({
        "pattern": params.pattern,
        "schema": _SQL_SCHEMA,
        "database": _SQL_DATABASE,
        "source": "database" if database_rows else "u9_schema",
        "count": len(rows),
        "tables": rows,
        "dictionary_tables": dictionary_rows,
        "database_tables": database_rows,
        "database_error": database_error,
        "schema_source": schema_status(),
    })


@mcp.tool(
    name="u9_discover_columns",
    annotations={"title": "搜索 U9 数据字段", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True}
)
async def u9_discover_columns(params: SqlSearchInput) -> str:
    """按关键字搜索 U9 列名（优先查 SQL Server，未配置数据库时回退到 U9 数据字典）。

    适用场景：
    - 想找一个"供应商编码"字段在哪些表里
    - 接口映射时，确认某个字段在数据库里的实际名称
    - 快速验证 U9 API 字段和数据库字段的对应关系

    U9 字段命名规则：主键通常是 ``ID``，单据编号是 ``DocNo``，
    业务日期是 ``BusinessDate``，状态是 ``Status`` 或 ``DocState``，
    基础资料编码/名称是 ``Code`` / ``Name``。

    Returns:
        str: 列名搜索结果，含表名、列名、数据类型、是否可空、中文用途
    """
    if not params.pattern:
        return _fmt({
            "tip": "请提供搜索关键字，如 pattern='supplier'、pattern='金额' 或 pattern='DocNo'",
            "schema": schema_status(),
        })

    dictionary_rows = _dictionary_column_rows(params.pattern, params.limit)
    database_rows: list[dict] = []
    database_error = None
    if _SQL_ENABLED:
        try:
            database_rows = _database_column_rows(params.pattern, params.limit)
        except Exception as exc:
            database_error = str(exc)

    if not database_rows and not dictionary_rows:
        payload = {
            "pattern": params.pattern,
            "schema": _SQL_SCHEMA,
            "database": _SQL_DATABASE,
            "count": 0,
            "columns": [],
            "schema_source": schema_status(),
        }
        if database_error:
            payload["error"] = database_error
        return _fmt(payload)

    rows = database_rows or dictionary_rows
    return _fmt({
        "pattern": params.pattern,
        "schema": _SQL_SCHEMA,
        "database": _SQL_DATABASE,
        "source": "database" if database_rows else "u9_schema",
        "count": len(rows),
        "columns": rows,
        "dictionary_columns": dictionary_rows,
        "database_columns": database_rows,
        "database_error": database_error,
        "schema_source": schema_status(),
    })


@mcp.tool(
    name="u9_describe_table",
    annotations={"title": "查看 U9 表结构", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True}
)
async def u9_describe_table(params: SqlDescribeInput) -> str:
    """查看指定 U9 表的完整结构（列名、类型、可空、主键、中文用途）。

    适用场景：
    - 知道表名，想了解完整字段列表
    - 写 SQL 或做数据建模前，查看表结构
    - 确认 U9 API 返回的字段在数据库里的实际类型

    U9 常见表：
    - PM_PurchaseOrder / PM_POLine：采购订单头 / 行
    - SM_SO / SM_SOLine：销售订单头 / 行
    - SM_Ship / SM_ShipLine：销售出库单头 / 行
    - InvDoc_OnStoreCheck / InvDoc_OnStoreCheckL：采购入库单头 / 行
    - CBO_ItemMaster：物料主数据
    - CBO_Customer / CBO_Supplier：客户 / 供应商
    - AP_APBillHead / AR_ARBillHead：应付单 / 应收单

    未配置 SQL Server 时自动回退到 U9 数据字典（u9_schema.json）。

    Returns:
        str: 表结构详情
    """
    database_rows: list[dict] = []
    database_error = None
    if _SQL_ENABLED:
        try:
            schema = _validate_sql_identifier(_SQL_SCHEMA or "dbo", "Schema")
            table_name = _validate_sql_identifier(params.table_name, "表名")
            conn = _sql_connect()
            try:
                database_rows = _sql_rows_params(conn, """
                    SELECT
                        c.COLUMN_NAME,
                        c.DATA_TYPE,
                        c.CHARACTER_MAXIMUM_LENGTH,
                        c.NUMERIC_PRECISION,
                        c.NUMERIC_SCALE,
                        c.IS_NULLABLE,
                        c.COLUMN_DEFAULT,
                        c.ORDINAL_POSITION,
                        pk.COLUMN_NAME AS IS_PRIMARY_KEY,
                        fk.REFERENCED_TABLE_NAME,
                        fk.REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS c
                    LEFT JOIN (
                        SELECT cu.TABLE_SCHEMA, cu.TABLE_NAME, cu.COLUMN_NAME
                        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                        JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE cu
                          ON tc.CONSTRAINT_NAME = cu.CONSTRAINT_NAME
                        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                          AND cu.TABLE_SCHEMA = ?
                    ) pk ON pk.TABLE_SCHEMA = c.TABLE_SCHEMA
                       AND pk.TABLE_NAME = c.TABLE_NAME
                       AND pk.COLUMN_NAME = c.COLUMN_NAME
                    LEFT JOIN (
                        SELECT
                            kcu.TABLE_SCHEMA, kcu.TABLE_NAME, kcu.COLUMN_NAME,
                            kcu2.TABLE_NAME AS REFERENCED_TABLE_NAME,
                            kcu2.COLUMN_NAME AS REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                          ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2
                          ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME
                        WHERE kcu.TABLE_SCHEMA = ?
                    ) fk ON fk.TABLE_SCHEMA = c.TABLE_SCHEMA
                       AND fk.TABLE_NAME = c.TABLE_NAME
                       AND fk.COLUMN_NAME = c.COLUMN_NAME
                    WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
                    ORDER BY c.ORDINAL_POSITION
                """, (schema, schema, schema, table_name))
            finally:
                conn.close()
        except Exception as exc:
            database_error = str(exc)

    dictionary = table_schema(params.table_name)

    if database_rows:
        return _fmt({
            "table": params.table_name,
            "schema": _SQL_SCHEMA,
            "database": _SQL_DATABASE,
            "source": "database",
            "count": len(database_rows),
            "purpose": dictionary.get("purpose") if dictionary else None,
            "columns": database_rows,
        })

    if dictionary:
        return _fmt({
            "table": dictionary["table"],
            "schema": "u9_schema",
            "database": _SQL_DATABASE or None,
            "source": "u9_schema",
            "purpose": dictionary["purpose"],
            "desc": dictionary["desc"],
            "short": dictionary["short"],
            "count": len(dictionary["columns"]),
            "columns": dictionary_columns(params.table_name),
            "database_error": database_error,
        })

    payload = {"error": f"表 '{params.table_name}' 不存在或无权访问。"}
    if database_error:
        payload["database_error"] = database_error
    payload["schema_source"] = schema_status()
    payload["hint"] = "可先用 u9_discover_tables 按业务关键字检索真实 U9 表名。"
    return _fmt(payload)


@mcp.tool(
    name="u9_discover_metadata_candidates",
    annotations={"title": "U9 元数据候选发现", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True}
)
async def u9_discover_metadata_candidates(params: MetadataCandidateInput) -> str:
    """发现 U9 数据库中与指定 form_id 对应的真实表。

    映射来源：FORM_CATALOG 的 db_tables（已按 u9_schema.json 校正），
    并同时检查 SQL Server 实际表与数据字典收录情况。

    form_id → 表名对应规律（U9）：
    - PUR_PurchaseOrder → PM_PurchaseOrder / PM_POLine（采购订单）
    - PUR_Requisition   → PR_PR / PR_PRLine（采购申请单）
    - SAL_SaleOrder     → SM_SO / SM_SOLine（销售订单）
    - STK_InStock       → InvDoc_OnStoreCheck / InvDoc_OnStoreCheckL（采购入库）
    - STK_Inventory     → CBO_ItemQty（即时库存）
    - BD_Material       → CBO_ItemMaster（物料）
    - BD_Supplier       → CBO_Supplier（供应商）
    - BD_Customer       → CBO_Customer（客户）

    适用场景：
    - 想知道某个 form_id 对应数据库里哪张表
    - 想探索某类单据的所有关联表（如采购全流程：订单→收料→入库）
    - 理解 U9 form_id 和数据库表名的映射关系

    Returns:
        str: form_id 与表名的候选映射列表
    """
    # 从 FORM_CATALOG 中自动提取 form_id → (主表, 明细/行表) 的映射
    candidates: list[tuple[str, str, str]] = []
    for fid, info in FORM_CATALOG.items():
        tables = info.get("db_tables", ())
        if tables:
            main_table = tables[0]
            name = info.get("name", fid)
            candidates.append((fid, main_table, name))

    # 按 form_id 过滤（如指定了）
    if params.form_id:
        filtered: list[tuple[str, str, str]] = [
            (fid, tbl, name) for fid, tbl, name in candidates
            if params.form_id.lower() in fid.lower()
        ]
    else:
        filtered = candidates
    filtered = filtered[:params.limit]

    # 数据库存在性（未配置 SQL Server 时为 None，表示未知）
    database_error = None
    conn = None
    if _SQL_ENABLED:
        try:
            conn = _sql_connect()
        except Exception as exc:
            database_error = str(exc)
            conn = None

    try:
        results = []
        for form_id, table_name, description in filtered:
            info = FORM_CATALOG.get(form_id, {})
            all_tables = info.get("db_tables", ())

            details = []
            exists_list = []
            for table in all_tables:
                dictionary = get_table(table)
                dictionary_exists = dictionary is not None

                database_exists = None
                if conn is not None:
                    try:
                        rows = _sql_rows_params(conn, """
                            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
                            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                              AND TABLE_TYPE = 'BASE TABLE'
                        """, (_validate_sql_identifier(_SQL_SCHEMA or "dbo", "Schema"), table))
                        database_exists = bool(rows)
                    except Exception as exc:
                        database_error = str(exc)

                exists = database_exists if database_exists is not None else dictionary_exists
                if exists:
                    exists_list.append(table)
                details.append({
                    "table": table,
                    "purpose": dictionary.get("purpose") if dictionary else None,
                    "column_count": len(dictionary.get("columns") or []) if dictionary else None,
                    "dictionary_exists": dictionary_exists,
                    "database_exists": database_exists,
                })

            results.append({
                "form_id": form_id,
                "table_name": table_name,
                "description": description,
                "exists": table_name in exists_list,
                "db_tables": all_tables,
                "table_details": details,
                "exists_tables": exists_list,
                "has_all_tables": bool(all_tables) and len(exists_list) == len(all_tables),
                "suggestion": (
                    f"调用 u9_describe_table(table_name='{table_name}') 查看表结构"
                    if table_name in exists_list
                    else "该表未在 SQL Server 或 U9 数据字典中命中，"
                         "可用 u9_discover_tables 按业务关键字重新检索"
                ),
            })

        return _fmt({
            "form_id_filter": params.form_id or "(全部)",
            "schema": _SQL_SCHEMA,
            "database": _SQL_DATABASE,
            "source": "database+u9_schema" if _SQL_ENABLED else "u9_schema",
            "count": len(results),
            "tip": "exists_tables=已命中的表；has_all_tables=true 表示主表和明细表均命中",
            "database_error": database_error,
            "schema_source": schema_status(),
            "results": results,
        })
    finally:
        if conn is not None:
            conn.close()


@mcp.tool(
    name="u9_query_table",
    annotations={"title": "直接查询 U9 数据表", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True}
)
async def u9_query_table(params: SqlTableQueryInput) -> str:
    """直接读取 U9 账套库中的业务数据（只读，走 SQL Server，不走 WebAPI）。

    适用场景：
    - 按条件快速查表：``table_name='PM_PurchaseOrder'``，按 ``DocNo`` / ``Supplier`` 过滤
    - 报表/统计前的原始数据核对，或 WebAPI 查询字段不够用时补充
    - 排查「单据到底有没有落库」这类问题

    与 ``u9_query_bills`` 的区别：
    - ``u9_query_bills`` 走 WebAPI，受 U9 权限/数据权限与查询视图限制
    - 本工具直连数据库，按真实物理表读取，字段更全；但**只读**，不会绕过
      U9 业务规则去写库

    安全约束：
    - 表名、字段名必须真实存在（同时按 ``u9_schema.json`` 与
      ``INFORMATION_SCHEMA`` 校验），不接受任意 SQL 片段
    - 所有过滤值都参数化绑定；``limit`` 最大 1000，建议先用 ``u9_describe_table``
      或 ``u9_discover_columns`` 确认字段名

    示例：
    - 查采购订单：``table_name='PM_PurchaseOrder'``,
      ``filters=[{"column":"DocNo","operator":"contains","value":"PO2026"}]``
    - 按日期区间：``filters=[{"column":"BusinessDate","operator":"between",
      "value":["2026-01-01","2026-01-31"]}]``

    Returns:
        str: 查询结果（columns / data / count / has_more / total 等）
    """
    try:
        result = query_table(
            table_name=params.table_name,
            columns=params.columns,
            filters=params.filters,
            order_by=params.order_by,
            limit=params.limit,
            offset=params.offset,
            include_total=params.include_total,
            all_columns=params.all_columns,
        )
        return _fmt(result)
    except Exception as exc:
        return _fmt({
            "error": str(exc),
            "table": params.table_name,
            "source": "database",
            "database_status": database_status(),
            "hint": (
                "确认已配置 MCP_SQLSERVER_* 且账号可读该表；"
                "表名/字段名可先用 u9_discover_tables / u9_discover_columns / "
                "u9_describe_table 查询。"
            ),
        })


@mcp.tool(
    name="u9_execute_sql",
    annotations={"title": "执行只读 SQL", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True}
)
async def u9_execute_sql(params: SqlExecuteInput) -> str:
    """执行单条只读 SQL（SELECT / WITH），用于跨表 JOIN、聚合等复杂查询。

    ⚠️ 只读守卫：只允许**单条** ``SELECT`` 或 ``WITH`` 查询。以下内容会被拒绝：
    ``INSERT`` / ``UPDATE`` / ``DELETE`` / ``MERGE``、``DROP`` / ``ALTER`` /
    ``CREATE`` / ``TRUNCATE``、``EXEC`` / 存储过程、``SELECT ... INTO``、
    ``BACKUP`` / ``RESTORE``、``DBCC``、``OPENROWSET``、多语句（分号）等。

    U9 真实表名示例：``PM_PurchaseOrder``（采购订单头）、``PM_POLine``（采购订单行）、
    ``SM_SO`` / ``SM_SOLine``（销售订单）、``CBO_ItemMaster``（物料）、
    ``InvDoc_OnStoreCheck`` / ``InvDoc_OnStoreCheckL``（采购入库）。

    建议使用参数化，避免手工拼接字符串：

    ```sql
    SELECT TOP 20 h.DocNo, h.BusinessDate, h.TotalMoney
    FROM PM_PurchaseOrder h
    WHERE h.BusinessDate >= ? AND h.Status = ?
    ORDER BY h.BusinessDate DESC
    ```

    对应 ``params=["2026-01-01", 1]``。

    注意：
    - 绕过 WebAPI 直连数据库，返回的是物理表原始数据，不是 U9 查询视图；
    - 账号权限由 DBA 控制，建议只授予 ``db_datareader``；
    - 结果最多返回 ``max_rows`` 行，超出部分截断。

    Returns:
        str: 查询结果（columns / data / count / truncated）
    """
    try:
        result = execute_readonly_sql(
            sql=params.sql,
            params=params.params,
            max_rows=params.max_rows,
        )
        return _fmt(result)
    except Exception as exc:
        return _fmt({
            "error": str(exc),
            "source": "database",
            "readonly": True,
            "database_status": database_status(),
            "hint": (
                "仅支持单条 SELECT/WITH；如已配置数据库仍失败，请检查账号权限与表名。"
                "可先用 u9_discover_tables / u9_describe_table 确认表结构。"
            ),
        })
