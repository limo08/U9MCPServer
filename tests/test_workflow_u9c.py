"""审批工具按 U9C DocStatus 数字枚举工作的回归测试。"""

import json
from unittest.mock import AsyncMock

from u9_mcp.api import workflow
from u9_mcp.models.system import WorkflowQueryInput, WorkflowStatusInput


async def test_pending_approvals_uses_u9c_docstatus(monkeypatch):
    post = AsyncMock(return_value={"Data": []})
    monkeypatch.setattr(workflow, "_post", post)

    out = json.loads(await workflow.u9_query_pending_approvals(
        WorkflowQueryInput(form_id="PUR_PurchaseOrder", status="pending", limit=5)
    ))

    assert out["status_filter"] == "pending"
    _, payload = post.await_args.args
    form_id, params = payload
    assert form_id == "PUR_PurchaseOrder"
    assert params["FilterString"] == "DocStatus IN (0, 1)"
    assert params["FieldKeys"] == "ID,DocNo,BusinessDate,DocStatus"
    assert params["Limit"] == 5


async def test_workflow_status_reads_u9c_data(monkeypatch):
    monkeypatch.setattr(workflow, "_post", AsyncMock(return_value={
        "ResCode": 0,
        "Success": True,
        "Data": {"ID": 1, "DocNo": "PO001", "DocStatus": 2},
    }))

    out = json.loads(await workflow.u9_query_workflow_status(
        WorkflowStatusInput(form_id="PUR_PurchaseOrder", bill_id="1")
    ))

    assert out["document_status"] == 2
    assert out["status_name"] == "已审核"
    assert out["bill_no"] == "PO001"
