"""按业务域划分的 MCP 服务目录。

一个服务 = 一个可独立部署的业务域。服务目录是工具过滤、部署脚本、
README 和回归测试的唯一事实来源；新增/移动工具时只改这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ALL_SERVICE = "all"


@dataclass(frozen=True)
class ServiceDefinition:
    """一个可独立部署的业务域服务。"""

    id: str
    title: str
    description: str
    port: int
    tools: tuple[str, ...]

    @property
    def tool_count(self) -> int:
        return len(self.tools)


SERVICES: dict[str, ServiceDefinition] = {
    "u9-bill": ServiceDefinition(
        id="u9-bill",
        title="通用单据",
        description="单据保存、提交、审核、作废、关闭、下推等通用单据操作",
        port=8011,
        tools=(
            "u9_save_bill",
            "u9_batch_save_bills",
            "u9_validate_bill",
            "u9_query_bills",
            "u9_view_bill",
            "u9_submit_bills",
            "u9_audit_bills",
            "u9_unaudit_bills",
            "u9_delete_bills",
            "u9_cancel_bills",
            "u9_void_bills",
            "u9_unvoid_bills",
            "u9_close_bill",
            "u9_unclose_bill",
            "u9_forbid_bills",
            "u9_enable_bills",
            "u9_push_bill",
            "u9_create_lx_billing",
        ),
    ),
    "u9-audit-workflow": ServiceDefinition(
        id="u9-audit-workflow",
        title="审计与审批",
        description="审计日志、变更日志、审批流程查询与审批操作",
        port=8012,
        tools=(
            "u9_create_and_audit",
            "u9_push_and_audit",
            "u9_query_operation_logs",
            "u9_query_audit_log",
            "u9_query_change_log",
            "u9_query_permission_changes",
            "u9_query_pending_approvals",
            "u9_query_workflow_status",
            "u9_query_approval_flow",
            "u9_workflow_approve",
        ),
    ),
    "u9-production": ServiceDefinition(
        id="u9-production",
        title="生产制造",
        description="生产订单、生产领料、生产入库、生产计划与 MRP",
        port=8013,
        tools=(
            "u9_query_production_orders",
            "u9_view_production_order",
            "u9_query_production_pick_materials",
            "u9_query_production_stock_in",
            "u9_save_production_order",
            "u9_submit_production_orders",
            "u9_audit_production_orders",
            "u9_push_production_pick",
            "u9_push_production_stock_in",
            "u9_query_mrp_result",
            "u9_query_production_plan",
            "u9_query_production_report",
        ),
    ),
    "u9-cost": ServiceDefinition(
        id="u9-cost",
        title="成本核算",
        description="材料成本、成本计算、成本分析与成本调整",
        port=8014,
        tools=(
            "u9_query_material_cost",
            "u9_query_material_target_cost",
            "u9_query_material_cost_usage",
            "u9_query_cost_calculation",
            "u9_query_cost_centers",
            "u9_query_cost_items",
            "u9_query_product_standard_cost",
            "u9_query_cost_adjustments",
            "u9_query_instant_cost_compare",
            "u9_query_cost_trend",
            "u9_query_finished_product_cost",
            "u9_save_cost_adjustment",
        ),
    ),
    "u9-asset": ServiceDefinition(
        id="u9-asset",
        title="固定资产",
        description="资产卡片、折旧、调拨与报废查询",
        port=8015,
        tools=(
            "u9_query_fixed_asset",
            "u9_query_asset_card",
            "u9_query_asset_depreciation",
            "u9_query_asset_transfer",
            "u9_query_asset_scrape",
            "u9_save_asset",
        ),
    ),
    "u9-inventory": ServiceDefinition(
        id="u9-inventory",
        title="库存",
        description="即时库存、出入库单据、库存调拨与杂项收发",
        port=8016,
        tools=(
            "u9_query_inventory",
            "u9_query_stock_bills",
            "u9_query_stock_in",
            "u9_query_stock_transfer_apply",
            "u9_query_transfer_apply",
            "u9_query_transfer_direct",
            "u9_query_transfer_pending_detail",
            "u9_query_misc_movement_detail",
            "u9_push_stock_transfer",
        ),
    ),
    "u9-purchase": ServiceDefinition(
        id="u9-purchase",
        title="采购",
        description="采购订单、请购、询价、供应商报价与订单进度",
        port=8017,
        tools=(
            "u9_query_purchase_orders",
            "u9_query_purchase_requisitions",
            "u9_query_purchase_inquiry",
            "u9_query_purchase_order_progress",
            "u9_query_supplier_quotes",
        ),
    ),
    "u9-sales": ServiceDefinition(
        id="u9-sales",
        title="销售",
        description="销售订单、报价、销售出库与发货通知",
        port=8018,
        tools=(
            "u9_query_sale_orders",
            "u9_query_sale_quotations",
            "u9_query_sales_outstock",
            "u9_query_delivery_notice",
        ),
    ),
    "u9-outsource-receipt": ServiceDefinition(
        id="u9-outsource-receipt",
        title="委外/收款",
        description="委外加工订单与收款单查询",
        port=8019,
        tools=(
            "u9_query_outsource_orders",
            "u9_query_receipts",
        ),
    ),
    "u9-master-data": ServiceDefinition(
        id="u9-master-data",
        title="基础数据",
        description="物料、客商、用户、角色、权限、序列、编码规则与系统配置",
        port=8020,
        tools=(
            "u9_query_materials",
            "u9_query_partners",
            "u9_query_user",
            "u9_query_role",
            "u9_query_permission",
            "u9_query_sequence",
            "u9_query_number_rule",
            "u9_query_system_config",
        ),
    ),
    "u9-system": ServiceDefinition(
        id="u9-system",
        title="系统/其他",
        description="质检、费用报销、借款、数据备份与通用操作",
        port=8021,
        tools=(
            "u9_query_quality_inspections",
            "u9_query_expense_reimburse",
            "u9_query_loan_balance",
            "u9_query_data_backup",
            "u9_execute_operation",
        ),
    ),
    "u9-metadata": ServiceDefinition(
        id="u9-metadata",
        title="元数据/开发",
        description="表单/字段元数据、数据库结构探查与只读 SQL",
        port=8022,
        tools=(
            "u9_list_forms",
            "u9_get_fields",
            "u9_list_form_operations",
            "u9_get_bill_template",
            "u9_refresh_metadata",
            "u9_discover_tables",
            "u9_discover_columns",
            "u9_describe_table",
            "u9_discover_metadata_candidates",
            "u9_query_table",
            "u9_execute_sql",
        ),
    ),
    "u9-reporting": ServiceDefinition(
        id="u9-reporting",
        title="统计/报表/附件",
        description="使用统计、财务报表与单据附件",
        port=8023,
        tools=(
            "u9_usage_stats",
            "u9_usage_report",
            "u9_query_report",
            "u9_upload_attachment",
            "u9_download_attachment",
        ),
    ),
}


SERVICE_IDS: tuple[str, ...] = tuple(SERVICES)


def service_tool_names(service_id: str) -> tuple[str, ...]:
    """返回某个服务包含的工具名。"""
    try:
        return SERVICES[service_id].tools
    except KeyError as exc:
        raise ValueError(f"未知服务：{service_id}") from exc


def all_service_tool_names() -> tuple[str, ...]:
    """返回所有服务工具名（保持目录顺序）。"""
    return tuple(tool for service in SERVICES.values() for tool in service.tools)


def normalize_service_selection(value: str | None) -> tuple[str, ...]:
    """解析服务选择。

    - ``None`` / 空串 / ``all`` / ``*`` → ``("all",)``
    - ``u9-bill,u9-purchase`` → 对应服务 ID 元组
    - 未知服务 ID → ``ValueError``
    """
    raw = (value or "").strip()
    if not raw or raw.lower() in {"all", "*"}:
        return (ALL_SERVICE,)

    selected: list[str] = []
    for part in raw.replace(" ", ",").split(","):
        service_id = part.strip()
        if not service_id:
            continue
        if service_id.lower() in {"all", "*"}:
            return (ALL_SERVICE,)
        if service_id not in SERVICES:
            available = ", ".join(SERVICE_IDS)
            raise ValueError(f"未知服务：{service_id}；可选：{available}")
        if service_id not in selected:
            selected.append(service_id)

    if not selected:
        return (ALL_SERVICE,)
    return tuple(selected)


def resolve_service_tools(value: str | None) -> set[str] | None:
    """返回服务选择对应的工具集合；``None`` 表示不限制（all）。"""
    selected = normalize_service_selection(value)
    if selected == (ALL_SERVICE,):
        return None
    return {tool for service_id in selected for tool in service_tool_names(service_id)}



# 角色组合：只用于部署时选择服务，不改变各服务自身的工具目录。
ROLE_BUNDLES: dict[str, dict[str, object]] = {
    "supply-chain": {
        "title": "供应链专员",
        "port": 8030,
        "services": (
            "u9-bill",
            "u9-purchase",
            "u9-sales",
            "u9-inventory",
            "u9-outsource-receipt",
            "u9-master-data",
        ),
    },
    "production-cost": {
        "title": "生产/成本会计",
        "port": 8031,
        "services": (
            "u9-production",
            "u9-cost",
            "u9-asset",
            "u9-master-data",
        ),
    },
    "finance-audit": {
        "title": "财务/审计",
        "port": 8032,
        "services": (
            "u9-cost",
            "u9-asset",
            "u9-audit-workflow",
            "u9-master-data",
        ),
    },
    "management": {
        "title": "管理层/综合",
        "port": 8033,
        "services": (
            "u9-bill",
            "u9-audit-workflow",
            "u9-master-data",
            "u9-reporting",
        ),
    },
    "dev": {
        "title": "开发/实施",
        "port": 8034,
        "services": (
            "u9-metadata",
            "u9-system",
            "u9-master-data",
        ),
    },
}


def role_bundle_tools(role_id: str) -> tuple[str, ...]:
    """返回角色组合包含的工具名（按服务目录顺序去重）。"""
    try:
        services = ROLE_BUNDLES[role_id]["services"]
    except KeyError as exc:
        raise ValueError(f"未知角色组合：{role_id}") from exc
    names: list[str] = []
    for service_id in services:  # type: ignore[union-attr]
        for tool in service_tool_names(str(service_id)):
            if tool not in names:
                names.append(tool)
    return tuple(names)


def role_bundle_service_ids(role_id: str) -> tuple[str, ...]:
    """返回角色组合的服务 ID。"""
    try:
        return tuple(str(s) for s in ROLE_BUNDLES[role_id]["services"])  # type: ignore[union-attr]
    except KeyError as exc:
        raise ValueError(f"未知角色组合：{role_id}") from exc


def format_role_table() -> str:
    """CLI 使用的角色组合表。"""
    lines = [
        f"{'角色 ID':<18} {'角色':<14} {'工具数':>5}  端口  建议服务组合",
        "-" * 110,
    ]
    for role_id, item in ROLE_BUNDLES.items():
        tools = role_bundle_tools(role_id)
        services = ",".join(role_bundle_service_ids(role_id))
        lines.append(
            f"{role_id:<18} {str(item['title']):<14} {len(tools):>5}  "
            f"{item['port']:<5} {services}"
        )
    return "\n".join(lines)


def service_table(registered_tools: Iterable[str] | None = None) -> list[dict[str, object]]:
    """生成服务概览，供 CLI / 文档 / 测试使用。"""
    registered = set(registered_tools) if registered_tools is not None else None
    rows: list[dict[str, object]] = []
    for service in SERVICES.values():
        tools = service.tools
        rows.append(
            {
                "id": service.id,
                "title": service.title,
                "description": service.description,
                "port": service.port,
                "tool_count": len(tools),
                "missing": sorted(set(tools) - registered) if registered is not None else [],
            }
        )
    return rows


def format_service_table() -> str:
    """CLI 使用的纯文本服务表。"""
    lines = [
        f"{'服务 ID':<24} {'业务域':<12} {'工具数':>5}  端口  说明",
        "-" * 92,
    ]
    for row in service_table():
        lines.append(
            f"{row['id']:<24} {row['title']:<12} {row['tool_count']:>5}  "
            f"{row['port']:<5} {row['description']}"
        )
    lines.append("-" * 92)
    lines.append(f"{'合计':<24} {'':<12} {len(all_service_tool_names()):>5}")
    return "\n".join(lines)
