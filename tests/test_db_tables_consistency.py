"""FORM_CATALOG 中 db_tables 与 U9 数据字典的一致性回归测试。

背景：
    FORM_CATALOG 的 db_tables 会直接喂给 AI 用于生成 SQL。历史上这里曾使用
    U9 的 ``T_*`` 表名（如 T_PUR_POORDER），与 U9 数据字典中的真实表名
    （PM_PurchaseOrder / PM_POLine）完全对不上，导致用户侧「对象名无效」。

本测试做两层校验：
1. 纯机械校验：不允许再出现 U9 风格的 ``T_*`` / ``V_*`` 表名；
2. 数据字典校验：每个映射表都必须能在 u9_schema.json 中查到（找不到字典时跳过）。

自定义单据（TRNV_*）的表名由 BOS 动态生成，不在标准 U9 数据字典中，显式放行。
"""

import pytest

from u9_mcp.server import FORM_CATALOG
from u9_mcp.utils.u9_schema import schema_status, table_exists

# 自定义单据：表名由 BOS 动态生成，不收录在标准 U9 数据字典中
CUSTOM_FORM_PREFIXES = ("TRNV_",)

# 必须锁死的核心映射，防止被改回 自定义 表名
EXPECTED_U9_TABLES = {
    "BD_Material": ("CBO_ItemMaster",),
    "BD_Customer": ("CBO_Customer",),
    "BD_Supplier": ("CBO_Supplier",),
    "PUR_PurchaseOrder": ("PM_PurchaseOrder", "PM_POLine"),
    "PUR_Requisition": ("PR_PR", "PR_PRLine"),
    "SAL_SaleOrder": ("SM_SO", "SM_SOLine"),
    "STK_InStock": ("InvDoc_OnStoreCheck", "InvDoc_OnStoreCheckL"),
    "STK_Inventory": ("CBO_ItemQty",),
    "AP_Payable": ("AP_APBillHead", "AP_APBillLine"),
    "AR_Receivable": ("AR_ARBillHead", "AR_ARBillLine"),
}


def _paired_entries():
    """产出所有「主表 + 明细/行表」成对定义的业务对象。"""
    for form_id, meta in FORM_CATALOG.items():
        tables = meta.get("db_tables") or ()
        if len(tables) >= 2:
            yield form_id, tables


def test_db_tables_pairs_exist():
    """至少要有成对定义的对象，否则说明本测试的取数逻辑已失效。"""
    pairs = list(_paired_entries())
    assert len(pairs) > 20, f"成对 db_tables 只找到 {len(pairs)} 条，取数逻辑可能已失效"


@pytest.mark.parametrize("form_id,tables", list(_paired_entries()))
def test_no_legacy_erp_table_names(form_id, tables):
    """不允许再把旧版 T_* / V_* 表名写进 U9 表映射。"""
    if form_id.startswith(CUSTOM_FORM_PREFIXES):
        pytest.skip(f"{form_id} 为自定义单据，表名由 BOS 动态生成")

    for table in tables:
        assert not table.upper().startswith(("T_", "V_")), (
            f"{form_id} 仍在使用旧版风格表名 {table}；"
            "请从 u9_schema.json 中查真实 U9 表名（如 PM_PurchaseOrder / PM_POLine）"
        )


@pytest.mark.parametrize("form_id,expected", list(EXPECTED_U9_TABLES.items()))
def test_core_form_mapping(form_id, expected):
    """核心表单的主表/明细表必须与 U9 数据字典一致。"""
    assert FORM_CATALOG[form_id]["db_tables"] == expected


def test_all_mapped_tables_exist_in_u9_schema():
    """所有标准 U9 表映射都必须能在数据字典中查到。"""
    status = schema_status()
    if not status["loaded"]:
        pytest.skip(
            "未找到 u9_schema.json（可用 U9_SCHEMA_FILE 指定），跳过字典校验："
            f"{status.get('error') or status.get('path')}"
        )

    missing = []
    for form_id, meta in FORM_CATALOG.items():
        if form_id.startswith(CUSTOM_FORM_PREFIXES):
            continue
        for table in meta.get("db_tables") or ():
            if not table_exists(table):
                missing.append(f"{form_id} -> {table}")

    assert not missing, "以下 db_tables 在 u9_schema.json 中不存在：\n" + "\n".join(missing)
