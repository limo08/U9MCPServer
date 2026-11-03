"""api.workflow"""


from ._delegates import _post, _post_raw
from . import mcp
from ..config.form_catalog import FORM_CATALOG
from ..models.system import WorkflowActionInput, WorkflowQueryInput, WorkflowStatusInput
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt, _rows



@mcp.tool(
    name="u9_query_pending_approvals",
    annotations={"title": "查询待审批单据", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_pending_approvals(params: WorkflowQueryInput) -> str:
    """查询待审批的单据列表。

    查询当前处于审批中状态（已提交、待审核）的单据。

    Returns:
        str: JSON 格式的待审批单据列表
    """
    try:
        # U9C 单据状态：0=开立、1=审核中、2=已审核、3=关闭
        if params.status == "pending":
            status_filter = "DocStatus IN (0, 1)"  # 待审批：开立/审核中
        elif params.status == "approved":
            status_filter = "DocStatus = 2"        # 已审核
        elif params.status == "rejected":
            status_filter = "DocStatus = 0"        # 驳回后回到开立/草稿
        else:
            status_filter = ""

        # 如果指定了表单类型
        if params.form_id:
            form_ids = [params.form_id]
        else:
            # 默认查询常见需要审批的单据
            form_ids = [
                "PUR_PurchaseOrder",     # 采购订单
                "SAL_SaleOrder",         # 销售订单
                "STK_InStock",           # 采购入库单
            ]

        all_results = []
        for fid in form_ids:
            info = FORM_CATALOG.get(fid, {"name": fid})
            # 使用 U9C 通用字段，避免字段不存在的问题
            fields = "ID,DocNo,BusinessDate,DocStatus"

            payload = [fid, {
                "FormId": fid,
                "FieldKeys": fields,
                "FilterString": status_filter,
                "OrderString": "BusinessDate DESC",
                "Limit": params.limit
            }]

            try:
                result = await _post("query", payload)
                rows = _rows(result)
                if rows:
                    all_results.append({
                        "form_id": fid,
                        "form_name": info.get("name", fid),
                        "count": len(rows),
                        "data": rows
                    })
            except Exception:
                continue

        return _fmt({
            "status_filter": params.status,
            "total_forms": len(all_results),
            "results": all_results
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_workflow_status",
    annotations={"title": "查询单据审批状态", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_workflow_status(params: WorkflowStatusInput) -> str:
    """查询单据的审批流状态。

    返回单据当前的审批状态和单据详情。

    Returns:
        str: JSON 格式的审批状态信息
    """
    try:
        # 查询单据详情
        result = await _post("view", [params.form_id, {"Id": params.bill_id}])

        if not result:
            return _fmt({"error": "单据不存在"})

        # 提取状态信息（U9C 查询结果统一放在 Data）
        bill_data = result.get("Data") or result.get("Result") or result
        if isinstance(bill_data, list):
            bill_data = bill_data[0] if bill_data else {}
        if not isinstance(bill_data, dict):
            bill_data = {}

        # U9C DocStatus：0=开立、1=审核中、2=已审核、3=关闭
        status_map = {
            0: "开立", 1: "审核中", 2: "已审核", 3: "关闭",
            "0": "开立", "1": "审核中", "2": "已审核", "3": "关闭",
        }
        doc_status = bill_data.get("DocStatus", bill_data.get("FDocumentStatus", ""))

        return _fmt({
            "form_id": params.form_id,
            "bill_id": params.bill_id,
            "document_status": doc_status,
            "status_name": status_map.get(doc_status, "未知"),
            "bill_no": bill_data.get("DocNo", bill_data.get("FBillNo", "")),
            "bill_data": bill_data
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_workflow_approve",
    annotations={"title": "审批通过", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_workflow_approve(params: WorkflowActionInput) -> str:
    """审批通过或驳回单据。

    - approve: 审核通过（待审核 → 已审核）
    - reject:  驳回（已审核 → 反审核回到待审核状态）
    - 返回结构化结果，包含 success / next_action 字段

    Returns:
        str: JSON，含 success / action / bill_id 字段
    """
    try:
        if params.action == "approve":
            result = await _post_raw("audit", params.form_id, {"Ids": params.bill_id})
            action_name = "审批通过"
        elif params.action == "reject":
            result = await _post_raw("unaudit", params.form_id, {"Ids": params.bill_id})
            action_name = "审批驳回"
        else:
            return _fmt({"error": f"不支持的操作: {params.action}"})

        status_data = _result_status(result, "audit" if params.action == "approve" else "unaudit")
        status_data["action"] = action_name
        status_data["bill_id"] = params.bill_id
        if params.opinion:
            status_data["opinion"] = params.opinion
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op=params.action)
