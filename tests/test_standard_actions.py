"""WebAPI 标准动作补齐回归测试。

覆盖：
- BatchSave 请求体（Model 为数组）
- 批量保存工具（逐张字段纠错、结果汇总）
- 反作废 / 通用 ExecuteOperation
- 表单元数据操作列表（u9_list_form_operations）
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from u9_mcp.api import bill as bill_api
from u9_mcp.api import system as system_api
from u9_mcp.config import settings
from u9_mcp.models.query import BatchSaveInput
from u9_mcp.models.system import ExecuteActionInput, ExecuteOperationInput, FormOperationListInput
from u9_mcp.services import bill_ops, client, metadata


def _ok_result():
    return {
        "Result": {
            "ResponseStatus": {"IsSuccess": True, "Errors": []},
            "SuccessEntitys": [{"Id": 1, "Number": "PO001"}],
        }
    }


@pytest.fixture
def no_validator(monkeypatch):
    async def _none(_form_id, force=False):
        return None

    monkeypatch.setattr(bill_api, "_get_metadata_validator", _none)
    monkeypatch.setattr(bill_api, "_post_raw", AsyncMock(return_value=_ok_result()))


# ─── BatchSave 请求体 ─────────────────────────────

async def test_post_raw_batch_save_splits_create_and_modify(monkeypatch):
    from u9_mcp.services import u9c_client

    calls = []

    async def fake_request(service, action, body=None, **kwargs):
        calls.append((service, action, body))
        return {"ResCode": 0, "Success": True, "ResMsg": "", "Data": [
            {"ID": 1, "Code": "PO001", "IsSucess": True}
        ]}

    monkeypatch.setattr(u9c_client, "request", fake_request)
    monkeypatch.setattr(client, "_session_id", None)
    monkeypatch.setattr(u9c_client, "_TOKEN", "test-token")

    result = await client._post_raw(
        "batch_save",
        "BD_Customer",
        [
            {"FID": 0, "FNumber": "C001", "FName": "客户一"},
            {"FID": 123, "FNumber": "C002", "FName": "客户二"},
        ],
    )

    assert result["Success"] is True
    assert [(service, action) for service, action, _ in calls] == [
        ("Customer", "Create"), ("Customer", "Modify"),
    ]
    assert calls[0][2] == [{"Code": "C001", "Name": "客户一"}]
    assert calls[1][2] == [{"ID": 123, "Code": "C002", "Name": "客户二"}]


# ─── u9_batch_save_bills ─────────────────────────────

async def test_batch_save_bills_sets_fid_and_counts(monkeypatch, no_validator):
    params = BatchSaveInput(
        form_id="PUR_PurchaseOrder",
        models=[{"FDate": "2026-01-01"}, {"FID": 123, "FDate": "2026-01-02"}],
        is_delete_entry=False,
    )
    out = json.loads(await bill_api.u9_batch_save_bills(params))

    assert out["success"] is True
    assert out["count"] == 2
    assert out["form_id"] == "PUR_PurchaseOrder"

    call = bill_api._post_raw.await_args
    assert call.args[0] == "batch_save"
    assert call.args[1] == "PUR_PurchaseOrder"
    models = call.args[2]
    assert models[0]["FID"] == 0
    assert models[1]["FID"] == 123
    assert call.kwargs["is_delete_entry"] is False


async def test_batch_save_bills_reports_unknown_fields_with_index(monkeypatch):
    class Validator:
        def validate_and_fix(self, model):
            if "FDate" in model:
                return model, [], [{"field": "FDate", "name": "FDate"}]
            fixed = dict(model)
            fixed["FDate"] = fixed.pop("Fdata")
            return fixed, [{"from": "Fdata", "to": "FDate", "to_zh": "单据日期"}], []

    async def _validator(_form_id, force=False):
        return Validator()

    monkeypatch.setattr(bill_api, "_get_metadata_validator", _validator)
    monkeypatch.setattr(bill_api, "_post_raw", AsyncMock(return_value=_ok_result()))

    params = BatchSaveInput(
        form_id="PUR_PurchaseOrder",
        models=[{"Fdata": "2026-01-01"}, {"FDate": "2026-01-02"}],
    )
    out = json.loads(await bill_api.u9_batch_save_bills(params))

    assert out["success"] is True
    assert out["auto_fixes"][0]["model_index"] == 0
    assert out["unknown_fields"][0]["model_index"] == 1
    sent = bill_api._post_raw.await_args.args[2]
    assert sent[0]["FDate"] == "2026-01-01"


# ─── 反作废 / 通用动作 ─────────────────────────────

def _patch_execute(monkeypatch):
    mock = AsyncMock(return_value=_ok_result())
    monkeypatch.setattr(client, "_post_raw", mock)
    return mock


async def test_unvoid_without_u9c_action_returns_error(monkeypatch):
    monkeypatch.setattr(bill_ops.metadata, "_query_metadata", AsyncMock(return_value=None))
    post = _patch_execute(monkeypatch)

    out = json.loads(await bill_api.u9_unvoid_bills(
        ExecuteActionInput(form_id="SAL_SaleOrder", bill_ids=["1", "2"])
    ))

    assert out["success"] is False
    assert "无法自动确定" in out["message"]
    post.assert_not_awaited()


async def test_unvoid_resolves_operation_from_metadata(monkeypatch):
    meta = {"Result": {"NeedReturnData": {"Operations": [
        {"OperationNumber": "BillUnInvalid", "OperationName": [{"Key": 2052, "Value": "反作废"}]},
        {"OperationNumber": "BillCancel", "OperationName": [{"Key": 2052, "Value": "作废"}]},
    ]}}}
    monkeypatch.setattr(bill_ops.metadata, "_query_metadata", AsyncMock(return_value=meta))
    post = _patch_execute(monkeypatch)

    out = json.loads(await bill_api.u9_unvoid_bills(
        ExecuteActionInput(form_id="PUR_PurchaseOrder", bill_nos=["PO001"])
    ))

    assert out["action"] == "BillUnInvalid"
    assert out["action_source"] == "metadata"
    assert out["matched_operation_name"] == "反作废"
    assert post.await_args.args[2] == {"Numbers": ["PO001"]}


async def test_execute_operation_requires_operation():
    with pytest.raises(Exception):
        ExecuteOperationInput(form_id="PUR_PurchaseOrder", bill_ids=["1"])


async def test_execute_operation_uses_explicit_op_number(monkeypatch):
    post = _patch_execute(monkeypatch)
    out = json.loads(await bill_api.u9_execute_operation(
        ExecuteOperationInput(form_id="PUR_PurchaseOrder", bill_ids=["9"], operation="BillClose")
    ))

    assert out["success"] is True
    assert out["action"] == "BillClose"
    assert out["action_source"] == "explicit"
    assert post.await_args.kwargs["op_number"] == "BillClose"


# ─── u9_list_form_operations ─────────────────────────

async def test_list_form_operations_extracts_multilingual(monkeypatch):
    meta = {"Result": {"NeedReturnData": {"Operations": [
        {"OperationNumber": "Submit", "OperationName": [
            {"Key": 1033, "Value": "Submit"}, {"Key": 2052, "Value": "提交"}]},
        {"OperationNumber": "Audit", "OperationName": [{"Key": 1033, "Value": "Audit"}]},
        {"OperationName": [{"Key": 2052, "Value": "无编码"}]},
    ]}}}
    query = AsyncMock(return_value=meta)
    monkeypatch.setattr(bill_ops.metadata, "_query_metadata", query)

    out = json.loads(await system_api.u9_list_form_operations(
        FormOperationListInput(form_id="PUR_PurchaseOrder")
    ))

    assert out["ok"] is True
    assert out["count"] == 2
    assert out["operations"][0] == {
        "number": "Submit",
        "name": "提交",
        "names": [{"locale": 1033, "name": "Submit"}, {"locale": 2052, "name": "提交"}],
    }
    assert out["operations"][1]["name"] == "Audit"
    query.assert_awaited_once_with("PUR_PurchaseOrder", force=False)


async def test_list_form_operations_handles_missing_metadata(monkeypatch):
    monkeypatch.setattr(
        bill_ops.metadata, "_query_metadata", AsyncMock(return_value=None)
    )
    out = json.loads(await system_api.u9_list_form_operations(
        FormOperationListInput(form_id="NOT_EXIST", refresh_metadata=True)
    ))

    assert out["ok"] is False
    assert "元数据" in out["error"]
    bill_ops.metadata._query_metadata.assert_awaited_once_with("NOT_EXIST", force=True)


async def test_save_bill_modifies_by_u9c_id(monkeypatch):
    """U9C 用户按 ID 修改时，不能被自动补出的 FID=0 覆盖。"""
    from u9_mcp.services import u9c_client

    calls = []

    async def fake_request(service, action, body=None, **kwargs):
        calls.append((service, action, body))
        return {"ResCode": 0, "Success": True, "ResMsg": "", "Data": [{"ID": 123, "DocNo": "PO001"}]}

    async def _none(_form_id, force=False):
        return None

    monkeypatch.setattr(bill_api, "_get_metadata_validator", _none)
    monkeypatch.setattr(u9c_client, "request", fake_request)

    out = json.loads(await bill_api.u9_save_bill(
        bill_api.SaveInput(form_id="BD_Customer", model={"ID": 123, "Code": "C002"})
    ))

    assert out["success"] is True
    assert [(service, action) for service, action, _ in calls] == [("Customer", "Modify")]
    assert calls[0][2] == [{"ID": 123, "Code": "C002"}]


def test_u9c_operation_summaries_are_authoritative():
    """U9C 摘要比英文 Action 名可靠：Release=挂起、Hold=解除挂起。"""
    meta = metadata._catalog_metadata("PUR_PurchaseOrder")
    ops = {
        o["OperationNumber"]: next(
            n["Value"] for n in o["OperationName"] if n["Key"] == 2052
        )
        for o in meta["Result"]["NeedReturnData"]["Operations"]
    }

    assert ops["Release"] == "挂起采购订单"
    assert ops["Hold"] == "解除挂起采购订单"
    assert ops["Cancel"] == "终止采购订单"
    assert meta["CacheVersion"] == metadata._CACHE_VERSION
