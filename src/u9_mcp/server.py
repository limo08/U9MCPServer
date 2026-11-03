"""用友U9 MCP Server 入口（兼容门面）。

实际实现分层：
  api/      —— MCP 对外接口（工具/提示/资源）
  config/   —— 运行配置与常量
  models/   —— 请求/响应 DTO
  services/ —— 业务逻辑与 WebAPI 客户端
  utils/    —— 通用工具（日志/错误/格式化/SQL）

本模块继续重新导出所有历史名称，保持 ``from u9_mcp.server import ...`` 兼容。
"""

import httpx

from .api import mcp
from .api.attachment import u9_upload_attachment as u9_upload_attachment
from .api.attachment import u9_download_attachment as u9_download_attachment

from .api.bill import u9_save_bill as u9_save_bill
from .api.bill import u9_batch_save_bills as u9_batch_save_bills
from .api.bill import u9_validate_bill as u9_validate_bill
from .api.bill import u9_get_bill_template as u9_get_bill_template
from .api.bill import u9_refresh_metadata as u9_refresh_metadata
from .api.bill import u9_submit_bills as u9_submit_bills
from .api.bill import u9_audit_bills as u9_audit_bills
from .api.bill import u9_unaudit_bills as u9_unaudit_bills
from .api.bill import u9_delete_bills as u9_delete_bills
from .api.bill import u9_cancel_bills as u9_cancel_bills
from .api.bill import u9_void_bills as u9_void_bills
from .api.bill import u9_unvoid_bills as u9_unvoid_bills
from .api.bill import u9_execute_operation as u9_execute_operation
from .api.bill import u9_close_bill as u9_close_bill
from .api.bill import u9_unclose_bill as u9_unclose_bill
from .api.bill import u9_forbid_bills as u9_forbid_bills
from .api.bill import u9_enable_bills as u9_enable_bills
from .api.bill import u9_push_bill as u9_push_bill
from .api.bill import u9_create_and_audit as u9_create_and_audit
from .api.bill import u9_push_and_audit as u9_push_and_audit
from .api.bill import u9_create_lx_billing as u9_create_lx_billing

from .api.cost import u9_query_material_cost as u9_query_material_cost
from .api.cost import u9_query_material_target_cost as u9_query_material_target_cost
from .api.cost import u9_query_cost_calculation as u9_query_cost_calculation
from .api.cost import u9_query_cost_centers as u9_query_cost_centers
from .api.cost import u9_query_cost_items as u9_query_cost_items
from .api.cost import u9_query_product_standard_cost as u9_query_product_standard_cost
from .api.cost import u9_query_cost_adjustments as u9_query_cost_adjustments
from .api.cost import u9_save_cost_adjustment as u9_save_cost_adjustment
from .api.cost import u9_query_instant_cost_compare as u9_query_instant_cost_compare
from .api.cost import u9_query_cost_trend as u9_query_cost_trend
from .api.cost import u9_query_finished_product_cost as u9_query_finished_product_cost
from .api.cost import u9_query_material_cost_usage as u9_query_material_cost_usage

from .api.finance import u9_query_expense_reimburse as u9_query_expense_reimburse
from .api.finance import u9_query_loan_balance as u9_query_loan_balance
from .api.finance import u9_query_fixed_asset as u9_query_fixed_asset
from .api.finance import u9_query_asset_card as u9_query_asset_card
from .api.finance import u9_query_asset_depreciation as u9_query_asset_depreciation
from .api.finance import u9_save_asset as u9_save_asset
from .api.finance import u9_query_asset_transfer as u9_query_asset_transfer
from .api.finance import u9_query_asset_scrape as u9_query_asset_scrape

from .api.logs import u9_query_audit_log as u9_query_audit_log
from .api.logs import u9_query_operation_logs as u9_query_operation_logs
from .api.logs import u9_query_change_log as u9_query_change_log
from .api.logs import u9_query_approval_flow as u9_query_approval_flow
from .api.logs import u9_query_permission_changes as u9_query_permission_changes
from .api.logs import u9_query_data_backup as u9_query_data_backup

from .api.production import u9_query_production_orders as u9_query_production_orders
from .api.production import u9_query_production_pick_materials as u9_query_production_pick_materials
from .api.production import u9_query_production_stock_in as u9_query_production_stock_in
from .api.production import u9_view_production_order as u9_view_production_order
from .api.production import u9_save_production_order as u9_save_production_order
from .api.production import u9_submit_production_orders as u9_submit_production_orders
from .api.production import u9_audit_production_orders as u9_audit_production_orders
from .api.production import u9_push_production_pick as u9_push_production_pick
from .api.production import u9_push_production_stock_in as u9_push_production_stock_in
from .api.production import u9_query_mrp_result as u9_query_mrp_result
from .api.production import u9_query_production_plan as u9_query_production_plan
from .api.production import u9_query_production_report as u9_query_production_report

from .api.prompts import prompt_query_purchase_orders as prompt_query_purchase_orders
from .api.prompts import prompt_query_inventory as prompt_query_inventory
from .api.prompts import prompt_create_purchase_order as prompt_create_purchase_order
from .api.prompts import resource_form_catalog as resource_form_catalog
from .api.prompts import resource_help as resource_help

from .api.query import u9_query_bills as u9_query_bills
from .api.query import u9_view_bill as u9_view_bill
from .api.query import u9_query_purchase_orders as u9_query_purchase_orders
from .api.query import u9_query_purchase_order_progress as u9_query_purchase_order_progress
from .api.query import u9_query_sale_orders as u9_query_sale_orders
from .api.query import u9_query_sale_quotations as u9_query_sale_quotations
from .api.query import u9_query_stock_bills as u9_query_stock_bills
from .api.query import u9_query_inventory as u9_query_inventory
from .api.query import u9_query_outsource_orders as u9_query_outsource_orders
from .api.query import u9_query_receipts as u9_query_receipts
from .api.query import u9_query_materials as u9_query_materials
from .api.query import u9_query_partners as u9_query_partners

from .api.report import u9_query_report as u9_query_report

from .api.sql import u9_discover_tables as u9_discover_tables
from .api.sql import u9_discover_columns as u9_discover_columns
from .api.sql import u9_describe_table as u9_describe_table
from .api.sql import u9_discover_metadata_candidates as u9_discover_metadata_candidates
from .api.sql import u9_query_table as u9_query_table
from .api.sql import u9_execute_sql as u9_execute_sql

from .api.supply_chain import u9_query_sales_outstock as u9_query_sales_outstock
from .api.supply_chain import u9_query_delivery_notice as u9_query_delivery_notice
from .api.supply_chain import u9_query_stock_in as u9_query_stock_in
from .api.supply_chain import u9_query_purchase_requisitions as u9_query_purchase_requisitions
from .api.supply_chain import u9_query_quality_inspections as u9_query_quality_inspections
from .api.supply_chain import u9_query_stock_transfer_apply as u9_query_stock_transfer_apply
from .api.supply_chain import u9_query_purchase_inquiry as u9_query_purchase_inquiry
from .api.supply_chain import u9_query_supplier_quotes as u9_query_supplier_quotes
from .api.supply_chain import u9_query_misc_movement_detail as u9_query_misc_movement_detail
from .api.supply_chain import u9_query_transfer_pending_detail as u9_query_transfer_pending_detail
from .api.supply_chain import u9_query_transfer_apply as u9_query_transfer_apply
from .api.supply_chain import u9_query_transfer_direct as u9_query_transfer_direct
from .api.supply_chain import u9_push_stock_transfer as u9_push_stock_transfer

from .api.system import u9_query_user as u9_query_user
from .api.system import u9_query_role as u9_query_role
from .api.system import u9_query_permission as u9_query_permission
from .api.system import u9_query_sequence as u9_query_sequence
from .api.system import u9_query_number_rule as u9_query_number_rule
from .api.system import u9_query_system_config as u9_query_system_config
from .api.system import u9_list_forms as u9_list_forms
from .api.system import u9_get_fields as u9_get_fields
from .api.system import u9_list_form_operations as u9_list_form_operations

from .api.usage import u9_usage_report as u9_usage_report
from .api.usage import u9_usage_stats as u9_usage_stats

from .api.workflow import u9_query_pending_approvals as u9_query_pending_approvals
from .api.workflow import u9_query_workflow_status as u9_query_workflow_status
from .api.workflow import u9_workflow_approve as u9_workflow_approve

from .config.bill_templates import BILL_TEMPLATES as BILL_TEMPLATES

from .config.form_catalog import FORM_CATALOG as FORM_CATALOG

from .config.settings import _env as _env
from .config.settings import _USAGE_LOG_FILE as _USAGE_LOG_FILE
from .config.settings import SERVER_URL as SERVER_URL
from .config.settings import ACCT_ID as ACCT_ID
from .config.settings import USERNAME as USERNAME
from .config.settings import PASSWORD as PASSWORD
from .config.settings import CLIENT_ID as CLIENT_ID
from .config.settings import CLIENT_SECRET as CLIENT_SECRET
from .config.settings import ENT_CODE as ENT_CODE
from .config.settings import ORG_CODE as ORG_CODE
from .config.settings import TOKEN as TOKEN
from .config.settings import U9C_AUTH_CONFIGURED as U9C_AUTH_CONFIGURED
from .config.settings import LCID as LCID
from .config.settings import _SQL_HOST as _SQL_HOST
from .config.settings import _SQL_PORT as _SQL_PORT
from .config.settings import _SQL_USER as _SQL_USER
from .config.settings import _SQL_PASSWORD as _SQL_PASSWORD
from .config.settings import _SQL_DATABASE as _SQL_DATABASE
from .config.settings import _SQL_SCHEMA as _SQL_SCHEMA
from .config.settings import _SQL_ENABLED as _SQL_ENABLED
from .config.settings import _EP as _EP
from .config.settings import _ATTACHMENT_CHUNK_BYTES as _ATTACHMENT_CHUNK_BYTES
from .config.settings import _ATTACHMENT_BASE64_LENGTH as _ATTACHMENT_BASE64_LENGTH

from .models.attachment import AttachmentUploadInput as AttachmentUploadInput
from .models.attachment import AttachmentDownloadInput as AttachmentDownloadInput

from .models.metadata import FieldDef as FieldDef

from .models.query import QueryInput as QueryInput
from .models.query import ViewInput as ViewInput
from .models.query import SaveInput as SaveInput
from .models.query import BatchSaveInput as BatchSaveInput
from .models.query import BillIdsInput as BillIdsInput
from .models.query import PurchaseOrderProgressInput as PurchaseOrderProgressInput
from .models.query import MaterialQueryInput as MaterialQueryInput
from .models.query import PartnerQueryInput as PartnerQueryInput
from .models.query import InventoryQueryInput as InventoryQueryInput
from .models.query import ReceiptQueryInput as ReceiptQueryInput
from .models.query import OutsourceOrderQueryInput as OutsourceOrderQueryInput
from .models.query import PushDownInput as PushDownInput
from .models.query import CreateAndAuditInput as CreateAndAuditInput
from .models.query import PushAndAuditInput as PushAndAuditInput
from .models.query import CreateLxBillingInput as CreateLxBillingInput
from .models.query import MaterialCostQueryInput as MaterialCostQueryInput
from .models.query import ProductionOrderBillIdsInput as ProductionOrderBillIdsInput
from .models.query import ProductionOrderSaveInput as ProductionOrderSaveInput
from .models.query import ProductionPickPushInput as ProductionPickPushInput
from .models.query import ProductionStockInPushInput as ProductionStockInPushInput
from .models.query import MRPResultQueryInput as MRPResultQueryInput
from .models.query import ProductionPlanQueryInput as ProductionPlanQueryInput
from .models.query import ProductionReportQueryInput as ProductionReportQueryInput
from .models.query import ReportQueryInput as ReportQueryInput

from .models.sql import SqlSearchInput as SqlSearchInput
from .models.sql import SqlDescribeInput as SqlDescribeInput
from .models.sql import MetadataCandidateInput as MetadataCandidateInput
from .models.sql import SqlFilter as SqlFilter
from .models.sql import SqlTableQueryInput as SqlTableQueryInput
from .models.sql import SqlExecuteInput as SqlExecuteInput

from .models.system import ExecuteActionInput as ExecuteActionInput
from .models.system import ExecuteOperationInput as ExecuteOperationInput
from .models.system import FormOperationListInput as FormOperationListInput
from .models.system import UserQueryInput as UserQueryInput
from .models.system import RoleQueryInput as RoleQueryInput
from .models.system import PermissionQueryInput as PermissionQueryInput
from .models.system import SequenceQueryInput as SequenceQueryInput
from .models.system import NumberRuleQueryInput as NumberRuleQueryInput
from .models.system import SystemConfigInput as SystemConfigInput
from .models.system import FormSearchInput as FormSearchInput
from .models.system import FieldQueryInput as FieldQueryInput
from .models.system import WorkflowQueryInput as WorkflowQueryInput
from .models.system import WorkflowActionInput as WorkflowActionInput
from .models.system import WorkflowStatusInput as WorkflowStatusInput
from .models.system import AuditLogInput as AuditLogInput
from .models.system import ChangeLogInput as ChangeLogInput
from .models.system import ApprovalFlowInput as ApprovalFlowInput
from .models.system import PermissionChangeInput as PermissionChangeInput
from .models.system import DataBackupInput as DataBackupInput
from .models.system import OperationLogInput as OperationLogInput

from .models.usage import UsageReportInput as UsageReportInput

from .services.attachment import _attachment_body as _attachment_body
from .services.attachment import _post_attachment as _post_attachment
from .services.attachment import _attachment_result as _attachment_result
from .services.attachment import _attachment_exception as _attachment_exception

from .services.bill_ops import _simplify_view_result as _simplify_view_result
from .services.bill_ops import _resolve_execute_operation as _resolve_execute_operation
from .services.bill_ops import _operation_resolve_error as _operation_resolve_error
from .services.bill_ops import _run_execute_action as _run_execute_action
from .services.bill_ops import _step_failed_status as _step_failed_status

from .services.client import _session_id as _session_id
from .services.client import _url as _url
from .services.client import _login as _login
from .services.client import _post as _post
from .services.client import _post_raw as _post_raw
from .services.client import _session_lock as _session_lock
from .services.client import _get_session_lock as _get_session_lock
from .services.client import _query_payload as _query_payload
from .services.client import _post_query as _post_query

from .services.metadata import _METADATA_CACHE as _METADATA_CACHE
from .services.metadata import MetadataValidator as MetadataValidator
from .services.metadata import _metadata_cache_dir as _metadata_cache_dir
from .services.metadata import _metadata_cache_path as _metadata_cache_path
from .services.metadata import _query_metadata as _query_metadata
from .services.metadata import _get_metadata_validator as _get_metadata_validator

from .services.no_fid import NO_FID_FORMS as NO_FID_FORMS
from .services.no_fid import _LEARNED_NO_FID_FORMS as _LEARNED_NO_FID_FORMS
from .services.no_fid import _NO_FID_ERR_PATTERNS as _NO_FID_ERR_PATTERNS
from .services.no_fid import _form_lacks_fid as _form_lacks_fid
from .services.no_fid import _strip_fid as _strip_fid
from .services.no_fid import _is_no_fid_error as _is_no_fid_error
from .services.no_fid import _looks_like_error as _looks_like_error

from .services.system import _system_query_payload as _system_query_payload
from .services.system import _post_system as _post_system

from .utils.errors import KNOWN_ERROR_PATTERNS as KNOWN_ERROR_PATTERNS
from .utils.errors import _is_session_expired as _is_session_expired
from .utils.errors import KNOWN_ERROR_NEXT_ACTIONS as KNOWN_ERROR_NEXT_ACTIONS
from .utils.errors import DOC_LIFECYCLE as DOC_LIFECYCLE
from .utils.errors import _match_known_pattern as _match_known_pattern
from .utils.errors import FIELD_LABELS as FIELD_LABELS
from .utils.errors import _FIELD_LABELS_RE as _FIELD_LABELS_RE
from .utils.errors import _zh_field as _zh_field
from .utils.errors import _humanize_error_message as _humanize_error_message
from .utils.errors import _parse_u9_errors as _parse_u9_errors
from .utils.errors import _reconcile_batch as _reconcile_batch
from .utils.errors import _result_status as _result_status
from .utils.errors import add_known_pattern as add_known_pattern
from .utils.errors import _err as _err

from .utils.formatting import _normalize_ids as _normalize_ids
from .utils.formatting import _rows as _rows
from .utils.formatting import _escape_sql_like as _escape_sql_like
from .utils.formatting import _safe_json as _safe_json
from .utils.formatting import _fmt as _fmt

from .utils.sql import _sql_connect as _sql_connect
from .utils.sql import _sql_rows as _sql_rows

from .utils.usage_log import _ERROR_STATS as _ERROR_STATS
from .utils.usage_log import _TOOL_STATS as _TOOL_STATS
from .utils.usage_log import _get_log_dir as _get_log_dir
from .utils.usage_log import _sanitize_params as _sanitize_params
from .utils.usage_log import log_tool_usage as log_tool_usage
from .utils.usage_log import get_usage_stats as get_usage_stats
from .utils.usage_log import with_usage_log as with_usage_log
from .utils.usage_log import ToolLogger as ToolLogger
from .utils.usage_log import generate_usage_report as generate_usage_report




# ─────────────────────────────────────────────
# 入口函数
# ─────────────────────────────────────────────
def _is_placeholder_url(url: str) -> bool:
    """判断是否为示例/占位地址。"""
    return not url or "your-server" in url.lower()


def _u9_config_missing() -> list[str]:
    """返回 U9C 接口访问方式缺失的配置项。

    U9C 支持两种认证：
    1. 静态 token：``U9_API_TOKEN``；
    2. OAuth2：``U9_API_CLIENT_ID`` / ``U9_API_CLIENT_SECRET`` /
       ``U9_API_ENT_CODE`` / ``U9_API_ORG_CODE`` / ``U9_API_USERNAME``。
    两者都还需要 ``U9_API_SERVER_URL``。
    """
    missing: list[str] = []
    if not SERVER_URL or _is_placeholder_url(str(SERVER_URL)):
        missing.append("U9_API_SERVER_URL")
    if not TOKEN:
        oauth = {
            "U9_API_CLIENT_ID": CLIENT_ID,
            "U9_API_CLIENT_SECRET": CLIENT_SECRET,
            "U9_API_ENT_CODE": ENT_CODE,
            "U9_API_ORG_CODE": ORG_CODE,
            "U9_API_USERNAME": USERNAME,
        }
        missing.extend(name for name, value in oauth.items() if not value)
    return missing


def _db_config() -> dict[str, str]:
    """读取 SQL Server 直连配置。"""
    from .config import settings

    return {
        "MCP_SQLSERVER_HOST": settings._SQL_HOST,
        "MCP_SQLSERVER_PORT": settings._SQL_PORT,
        "MCP_SQLSERVER_DATABASE": settings._SQL_DATABASE,
        "MCP_SQLSERVER_USER": settings._SQL_USER,
        "MCP_SQLSERVER_PASSWORD": settings._SQL_PASSWORD,
    }


def _db_config_missing() -> list[str]:
    """返回 SQL Server 直连方式缺失的配置项。"""
    cfg = _db_config()
    required = (
        "MCP_SQLSERVER_HOST",
        "MCP_SQLSERVER_DATABASE",
        "MCP_SQLSERVER_USER",
        "MCP_SQLSERVER_PASSWORD",
    )
    return [name for name in required if not cfg[name]]


def _check_u9() -> int:
    """登录一次 U9 接口，返回检查结果码。"""
    import asyncio

    print(f"[INFO] U9C 接口: {SERVER_URL}")
    mode = "静态 TOKEN" if TOKEN else "OAuth2 AuthLogin"
    print(f"[INFO] 账套: {ENT_CODE}  组织: {ORG_CODE}  用户: {USERNAME or '-'}  认证: {mode}")
    print("[INFO] 正在尝试认证 U9C...")
    try:
        token = asyncio.run(_login())
    except httpx.HTTPError as e:
        print(f"[FAIL] 网络错误: {e}")
        print("       请检查 U9_API_SERVER_URL 是否可访问（U9C 通常以 /webapi/ 为接口根路径）。")
        return 2
    except RuntimeError as e:
        print(f"[FAIL] {e}")
        print("       请检查 U9_API_TOKEN，或 U9_API_CLIENT_ID / U9_API_CLIENT_SECRET / "
              "U9_API_ENT_CODE / U9_API_ORG_CODE / U9_API_USERNAME 是否正确。")
        return 3
    except Exception as e:
        print(f"[FAIL] 未知错误: {type(e).__name__}: {e}")
        return 4

    print(f"[OK] U9C 认证成功，token: {token[:12]}...")
    return 0


def _check_database() -> int:
    """连接一次 SQL Server 并执行 SELECT 1，返回检查结果码。"""
    from .utils.sql import _sql_connect

    cfg = _db_config()
    print(f"[INFO] 数据库: {cfg['MCP_SQLSERVER_HOST']}:{cfg['MCP_SQLSERVER_PORT']}/"
          f"{cfg['MCP_SQLSERVER_DATABASE']}  用户: {cfg['MCP_SQLSERVER_USER']}")
    print("[INFO] 正在尝试连接 SQL Server...")

    conn = None
    try:
        conn = _sql_connect()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        finally:
            cursor.close()
    except Exception as e:
        print(f"[FAIL] 数据库连接失败: {type(e).__name__}: {e}")
        print("       请检查 MCP_SQLSERVER_HOST / PORT / DATABASE / USER / PASSWORD "
              "以及 SQL Server ODBC 驱动是否安装。")
        return 5
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    print("[OK] 数据库连接成功。")
    return 0


def _run_check() -> int:
    """检查当前配置：U9 接口 或 SQL Server 直连，至少一种可用。

    返回码：0=至少一种访问方式可用；1=两种方式都未配置；
    2/3/4=U9 网络/认证/未知错误；5=数据库连接失败。
    """
    u9_missing = _u9_config_missing()
    db_missing = _db_config_missing()
    u9_ready = not u9_missing
    db_ready = not db_missing

    if not u9_ready and not db_ready:
        print("[FAIL] 未配置任何可用的访问方式：U9 接口 与 SQL Server 直连 至少需要配置一种。")
        print("       U9 接口缺少: " + ", ".join(u9_missing))
        print("       数据库缺少: " + ", ".join(db_missing))
        print("       仅用 U9C 接口: U9_API_SERVER_URL / U9_API_CLIENT_ID / "
              "U9_API_CLIENT_SECRET / U9_API_ENT_CODE / U9_API_ORG_CODE / U9_API_USERNAME"
              "（或 U9_API_TOKEN）")
        print("       仅用数据库:    MCP_SQLSERVER_HOST / MCP_SQLSERVER_DATABASE / "
              "MCP_SQLSERVER_USER / MCP_SQLSERVER_PASSWORD")
        print("       注：用友接口变量使用 U9_API_* 前缀；MCP 运行参数使用 U9_MCP_*。")
        return 1

    failures: list[int] = []
    configured = 0

    if u9_ready:
        configured += 1
        code = _check_u9()
        if code:
            failures.append(code)
    else:
        print("[INFO] U9 接口未完整配置，跳过登录检查。")
        print("       缺少: " + ", ".join(u9_missing))

    if db_ready:
        configured += 1
        code = _check_database()
        if code:
            failures.append(code)
    else:
        print("[INFO] SQL Server 直连未完整配置，跳过数据库检查。")
        print("       缺少: " + ", ".join(db_missing))

    if failures and len(failures) == configured:
        print("[FAIL] 已配置的访问方式均未通过检查。")
        return failures[0]
    if failures:
        print("[WARN] 部分访问方式未通过检查，但仍有一种访问方式可用。")
    else:
        print("[OK] 配置正确，可在 MCP 客户端中使用。")
    return 0



def main():
    """MCP Server 入口点

    用法:
      u9-mcp                              # 默认 stdio 模式（本地 MCP 客户端）
      u9-mcp --check                      # 检查配置：U9 登录 或 SQL Server 直连，至少一种可用
      u9-mcp --transport sse              # SSE 远程模式，监听 http://host:port/sse
      u9-mcp --transport streamable-http  # Streamable HTTP 远程模式，监听 http://host:port/mcp
    远程模式可用 --host / --port 指定监听地址（默认 127.0.0.1:8000）。
    也支持环境变量 U9_MCP_TRANSPORT / U9_MCP_HOST / U9_MCP_PORT。
    """
    import sys
    import argparse

    if len(sys.argv) > 1 and sys.argv[1] in ("--check", "check"):
        sys.exit(_run_check())

    parser = argparse.ArgumentParser(
        prog="u9-mcp",
        description="用友 U9C MCP Server (OpenAPI)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=_env("MCP_TRANSPORT", "stdio"),
        help="传输方式: stdio(默认, 本地) / sse / streamable-http(远程部署用)",
    )
    parser.add_argument(
        "--host",
        default=_env("MCP_HOST", "127.0.0.1"),
        help="sse / streamable-http 监听地址 (默认 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(_env("MCP_PORT", "8000")),
        help="sse / streamable-http 监听端口 (默认 8000)",
    )
    args = parser.parse_args()

    _run_server(transport=args.transport, host=args.host, port=args.port)



def _run_server(transport: str, host: str = "127.0.0.1", port: int = 8000) -> None:
    """启动 MCP Server（mcp 2.x 的 run() 直接接收 host/port）。"""
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    main()
