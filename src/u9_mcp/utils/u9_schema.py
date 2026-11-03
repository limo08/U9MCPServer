"""U9 数据字典（u9_schema.json）加载与检索。

数据字典由 U9 数据字典 Excel 解析而来，包含 7000+ 张表的用途、字段中文名、
类型、长度、主键等信息。SQL Server 探查工具在未配置数据库连接（或数据库中
查不到表）时，会回退到本模块，保证仍能按真实 U9 表名/字段名回答。

数据字典路径按以下顺序查找（可用 ``U9_SCHEMA_FILE`` 显式指定）：
1. ``$U9_SCHEMA_FILE``
2. ``<项目根>/data/u9_schema.json``
3. ``~/.u9_mcp/u9_schema.json``
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Iterator

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "tried": False,
    "path": None,
    "tables": None,
    "index": None,
    "error": None,
}


# 中文业务词 → U9 表名/英文关键词别名。U9 数据字典的 purpose 多为英文表名
# （如「项目管理PurchaseOrder表」），只按中文子串检索会漏掉，因此先做业务词扩展。
_CORE_TABLES = frozenset({
    "CBO_ItemMaster", "CBO_Customer", "CBO_Supplier", "CBO_Department",
    "CBO_Person", "CBO_InventoryInfo", "Base_UOM", "Base_Currency",
    "PM_PurchaseOrder", "PR_PR", "SM_SO", "SM_Ship", "SM_Quotation",
    "SM_RMA", "SM_PreShip", "InvDoc_OnStoreCheck", "InvDoc_MiscShip",
    "InvDoc_MiscRcvTrans", "InvDoc_TransferForm", "InvDoc_InventorySheet",
    "CBO_ItemQty", "AP_APBillHead", "AR_ARBillHead", "AP_PayBillHead",
    "AR_RecBillHead", "MO_MO", "MO_MOPickList", "MO_CompleteRpt",
    "QC_QCDoc", "PPR_RequestForQuotation", "PPB_QuoteDoc",
})

_CN_ALIASES: dict[str, tuple[str, ...]] = {
    "采购订单": ("PurchaseOrder", "PM_POLine"),
    "采购申请": ("PR_PR", "PRLine", "Requisition"),
    "采购入库": ("OnStoreCheck",),
    "采购退货": ("MRB",),
    "采购合同": ("PurchaseContract",),
    "采购价目": ("PurPriceList", "PurPriceLine"),
    "采购调价": ("PurPriceAdjustment", "PurPriceAdjust"),
    "采购询价": ("RequestForQuotation", "RFQ"),
    "供应商报价": ("QuoteDoc", "QuoteDocLine"),
    "比价": ("CPLine", "PPR_CP"),
    "销售订单": ("SM_SO", "SM_SOLine"),
    "销售出库": ("SM_Ship", "SM_ShipLine"),
    "销售退货": ("SM_RMA", "SM_RMALine"),
    "销售报价": ("SM_Quotation", "QuotationLine"),
    "发货通知": ("PreShip",),
    "退货通知": ("RMA",),
    "可用量": ("ItemQty", "OnHandQty"),
    "即时库存": ("ItemQty", "OnHandQty"),
    "库存": ("ItemQty", "InventoryInfo", "InventorySheet"),
    "盘点": ("InventorySheet",),
    "调拨": ("Transfer",),
    "组装": ("Assembly",),
    "拆卸": ("Assembly",),
    "生产订单": ("MO_MO", "MOOutput"),
    "生产领料": ("MOPickList",),
    "完工入库": ("CompleteRpt",),
    "委外": ("Subcontract",),
    "应付": ("APBill", "PayBill"),
    "应收": ("ARBill", "RecBill"),
    "收款": ("RecBill",),
    "付款": ("PayBill",),
    "费用申请": ("ExpenseRequest",),
    "费用报销": ("Reimburse",),
    "来料检验": ("QCDoc", "QCDocLine"),
    "质检": ("QCDoc",),
    "物料": ("ItemMaster",),
    "客户": ("Customer",),
    "供应商": ("Supplier",),
    "部门": ("Department",),
    "员工": ("Person", "Employee"),
    "人员": ("Person",),
    "仓库": ("InventoryInfo",),
    "计量单位": ("Base_UOM", "UOM"),
    "单位": ("Base_UOM", "UOM"),
    "币别": ("Base_Currency", "Currency"),
    "币种": ("Base_Currency", "Currency"),
    "合同": ("Contract",),
    "价目": ("PriceList", "PurPrice"),
    "询价": ("RequestForQuotation", "RFQ"),
    "报价": ("Quotation", "QuoteDoc", "Quote"),
}


def _expand_terms(keyword: str) -> list[str]:
    """把中文业务词扩展成数据字典里实际出现的英文/表名关键词。"""
    terms = [keyword]
    lowered = keyword.lower()
    for cn, aliases in _CN_ALIASES.items():
        if cn in keyword or keyword in cn:
            terms.extend(aliases)
    # 去重保序（忽略大小写）
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        key = term.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def _candidate_paths() -> Iterator[Path]:
    env_path = os.getenv("U9_SCHEMA_FILE", "").strip()
    if env_path:
        yield Path(env_path).expanduser()

    project_root = Path(__file__).resolve().parents[3]
    yield project_root / "data" / "u9_schema.json"
    yield project_root.parent / "U9-MCP-Server" / "data" / "u9_schema.json"
    yield Path.cwd() / "data" / "u9_schema.json"
    yield Path.home() / ".u9_mcp" / "u9_schema.json"


def _load() -> bool:
    """惰性加载数据字典；成功返回 True，找不到/解析失败返回 False。"""
    if _STATE["tables"] is not None:
        return True
    with _LOCK:
        if _STATE["tables"] is not None:
            return True
        if _STATE["tried"] and _STATE["error"]:
            return False
        _STATE["tried"] = True
        for path in _candidate_paths():
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception as exc:  # 损坏的大文件不应让工具直接崩掉
                _STATE["error"] = f"{path}: {exc}"
                continue

            tables = data.get("tables") or []
            index = {
                (table.get("name") or "").upper(): table
                for table in tables
                if table.get("name")
            }
            _STATE.update(
                path=str(path),
                tables=tables,
                index=index,
                error=None,
            )
            return True
        return False


def schema_status() -> dict[str, Any]:
    """返回数据字典加载状态，供工具输出携带来源信息。"""
    loaded = _load()
    return {
        "loaded": loaded,
        "path": _STATE["path"],
        "table_count": len(_STATE["tables"] or []),
        "error": _STATE["error"],
    }


def get_table(name: str) -> dict[str, Any] | None:
    """按表名（不区分大小写）获取原始表定义。"""
    if not name or not _load():
        return None
    return (_STATE["index"] or {}).get(name.strip().upper())


def table_exists(name: str) -> bool:
    return get_table(name) is not None


def _column_summary(column: dict[str, Any], position: int) -> dict[str, Any]:
    return {
        "name": column.get("name"),
        "type": column.get("type"),
        "length": column.get("length"),
        "nullable": column.get("nullable"),
        "primary_key": column.get("primary_key"),
        "purpose": column.get("purpose"),
        "position": position,
    }


def table_schema(name: str) -> dict[str, Any] | None:
    """返回单表结构（用途、说明、简称、字段列表）。"""
    table = get_table(name)
    if not table:
        return None
    return {
        "table": table.get("name"),
        "purpose": table.get("purpose") or "",
        "desc": table.get("desc") or "",
        "short": table.get("short") or "",
        "columns": [
            _column_summary(column, idx)
            for idx, column in enumerate(table.get("columns") or [], start=1)
        ],
    }


def search_tables(keyword: str, limit: int = 20) -> list[dict[str, Any]]:
    """按表名/简称/表用途/字段名/字段用途检索 U9 表。"""
    keyword = (keyword or "").strip()
    if not keyword or not _load():
        return []
    terms = _expand_terms(keyword)
    hits: list[dict[str, Any]] = []

    for table in _STATE["tables"] or []:
        name = table.get("name") or ""
        purpose = table.get("purpose") or ""
        desc = table.get("desc") or ""
        short = table.get("short") or ""
        columns = table.get("columns") or []

        best = 0
        name_lower = name.lower()
        for term in terms:
            lowered = term.lower()
            raw = 0
            if lowered in name_lower:
                raw += 5
            if lowered in short.lower():
                raw += 3
            if term in purpose or term in desc:
                raw += 4
            for column in columns:
                column_name = column.get("name") or ""
                column_purpose = column.get("purpose") or ""
                if lowered in column_name.lower():
                    raw += 2
                    break
                if term in column_purpose:
                    raw += 1
                    break
            if not raw:
                continue

            score = raw
            if name_lower.endswith(lowered):
                score += 4
            if name_lower == lowered:
                score += 8
            if name in _CORE_TABLES:
                score += 8
            # 同分时优先短表名（主数据表通常比扩展/关联表短）
            score += max(0, 8 - len(name) // 8)
            # 主表/主数据优先，多语言、历史、单据类型、地址等附属表降权
            if name_lower.endswith(("head", "master")):
                score += 2
            for suffix, penalty in (
                ("_trl", -8), ("his", -5), ("_extredefine", -5),
                ("doctype", -4), ("attachment", -4), ("_log", -4),
                ("address", -3), ("contact", -3), ("feedetail", -3),
                ("line", -1), ("_l", -1),
            ):
                if name_lower.endswith(suffix):
                    score += penalty
            best = max(best, score)

        if best:
            hits.append({
                "table": name,
                "purpose": purpose or desc,
                "short": short,
                "column_count": len(columns),
                "match_score": best,
            })

    hits.sort(key=lambda item: (-item["match_score"], item["table"]))
    return hits[:limit]


def search_columns(keyword: str, limit: int = 50) -> list[dict[str, Any]]:
    """按字段名/字段中文用途检索 U9 字段。"""
    keyword = (keyword or "").strip()
    if not keyword or not _load():
        return []
    lowered = keyword.lower()
    hits: list[dict[str, Any]] = []

    for table in _STATE["tables"] or []:
        table_name = table.get("name") or ""
        table_purpose = table.get("purpose") or ""
        for column in table.get("columns") or []:
            column_name = column.get("name") or ""
            column_purpose = column.get("purpose") or ""
            if lowered in column_name.lower() or keyword in column_purpose:
                hits.append({
                    "table": table_name,
                    "table_purpose": table_purpose,
                    "column": column_name,
                    "type": column.get("type"),
                    "length": column.get("length"),
                    "nullable": column.get("nullable"),
                    "primary_key": column.get("primary_key"),
                    "purpose": column_purpose,
                })
                if len(hits) >= limit:
                    return hits
    return hits


def dictionary_columns(table_name: str) -> list[dict[str, Any]]:
    """以数据库探查工具的统一列名返回字段（与 INFORMATION_SCHEMA 对齐）。"""
    schema = table_schema(table_name)
    if not schema:
        return []
    rows: list[dict[str, Any]] = []
    for column in schema["columns"]:
        rows.append({
            "COLUMN_NAME": column["name"],
            "DATA_TYPE": column["type"],
            "CHARACTER_MAXIMUM_LENGTH": column["length"],
            "NUMERIC_PRECISION": None,
            "NUMERIC_SCALE": None,
            "IS_NULLABLE": column["nullable"],
            "COLUMN_DEFAULT": None,
            "ORDINAL_POSITION": column["position"],
            "IS_PRIMARY_KEY": column["primary_key"],
            "REFERENCED_TABLE_NAME": None,
            "REFERENCED_COLUMN_NAME": None,
            "COLUMN_PURPOSE": column["purpose"],
        })
    return rows
