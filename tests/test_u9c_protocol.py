"""U9C OpenAPI protocol tests: auth, query, action bodies and model mapping."""

import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from u9_mcp.config import settings, u9c_catalog
from u9_mcp.services import client, u9c_client, u9c_mapping


def ok(data):
    return {"ResCode": 0, "Success": True, "ResMsg": "", "Exception": "", "Data": data}


def fail(message="业务失败", code=1):
    return {"ResCode": code, "Success": False, "ResMsg": message,
            "Exception": "", "Data": None}


@pytest.fixture
def api(monkeypatch):
    calls, responses = [], []

    async def handle(request):
        calls.append(request)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)

    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda *args, **kwargs: transport)
    monkeypatch.setattr(settings, "SERVER_URL", "https://u9.invalid/webapi")
    monkeypatch.setattr(settings, "TOKEN", "static-token")
    monkeypatch.setattr(settings, "CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "CLIENT_SECRET", "secret")
    monkeypatch.setattr(settings, "ENT_CODE", "ent")
    monkeypatch.setattr(settings, "ORG_CODE", "org")
    monkeypatch.setattr(settings, "USERNAME", "user")
    monkeypatch.setattr(settings, "LANGUAGE", "zh-CN")
    monkeypatch.setattr(settings, "LOGIN_TYPE", 1)
    monkeypatch.setattr(settings, "LOGIN_DATE", "")
    monkeypatch.setattr(u9c_client, "_TOKEN", "static-token")
    monkeypatch.setattr(u9c_client, "_TOKEN_LOCK", None)
    return calls, responses


@pytest.mark.asyncio
async def test_auth_login_uses_oauth2_get_and_caches_token(api, monkeypatch):
    calls, responses = api
    monkeypatch.setattr(settings, "TOKEN", "")
    monkeypatch.setattr(u9c_client, "_TOKEN", None)
    responses.extend([ok("token-1"), ok({"RecordList": []})])

    assert await u9c_client.login() == "token-1"
    await u9c_client.common_query("X.Entity", ["ID"])

    login_req, query_req = calls
    assert login_req.method == "GET"
    assert login_req.url.path == "/webapi/OAuth2/AuthLogin"
    assert login_req.url.params["clientid"] == "cid"
    assert login_req.url.params["clientsecret"] == "secret"
    assert login_req.url.params["entCode"] == "ent"
    assert login_req.url.params["orgCode"] == "org"
    assert login_req.url.params["userCode"] == "user"
    assert login_req.url.params["language"] == "zh-CN"
    assert query_req.headers["token"] == "token-1"


@pytest.mark.asyncio
async def test_static_token_skips_login(api):
    calls, responses = api
    responses.append(ok({"RecordList": []}))
    token = await u9c_client.login()
    await u9c_client.common_query("X.Entity", ["ID"])
    assert token == "static-token"
    assert [c.url.path for c in calls] == ["/webapi/CommonEntity/Query"]
    assert calls[0].headers["token"] == "static-token"


@pytest.mark.asyncio
async def test_missing_auth_configuration_is_explicit(api, monkeypatch):
    calls, _ = api
    monkeypatch.setattr(settings, "TOKEN", "")
    monkeypatch.setattr(settings, "CLIENT_ID", "")
    monkeypatch.setattr(u9c_client, "_TOKEN", None)
    with pytest.raises(u9c_client.U9CError) as exc:
        await u9c_client.login()
    assert "U9_API_CLIENT_ID" in str(exc.value)
    assert calls == []


@pytest.mark.asyncio
async def test_query_translates_fields_filters_and_orders(api):
    calls, responses = api
    responses.append(ok({"RecordList": [{"ID": 7, "DocNo": "PO7"}], "RecordCount": 1}))

    result = await u9c_client.common_query_form(
        "PUR_PurchaseOrder",
        "FID,FBillNo,FSupplierId.FNumber,FDate",
        "FDocumentStatus='已审核' and FDate>='2026-01-01'",
        "FDate desc",
        0,
        20,
    )

    req = calls[0]
    assert req.method == "POST"
    assert req.url.path == "/webapi/CommonEntity/Query"
    body = json.loads(req.content)
    assert body["EntityFullName"] == "UFIDA.U9.PM.PO.PurchaseOrder"
    assert body["ReturnFields"] == ["ID", "DocNo", "Supplier.Code", "BusinessDate"]
    assert body["Orders"] == "BusinessDate desc"
    assert body["PageIndex"] == 1 and body["PageSize"] == 20
    assert body["Filters"] == [
        {"Field": "DocStatus", "Operator": "eq", "Value": "已审核",
         "ValueIsField": False, "Logic": "and"},
        {"Field": "BusinessDate", "Operator": "ge", "Value": "2026-01-01",
         "ValueIsField": False, "Logic": "and"},
    ]
    assert result["rows"] == [{"ID": 7, "DocNo": "PO7"}]
    assert result["total"] == 1
    assert "已按 U9C OpenAPI 命名转换" in result["notice"]


@pytest.mark.asyncio
async def test_query_unknown_entity_is_explicit(api):
    calls, _ = api
    with pytest.raises(u9c_client.U9CError) as exc:
        await u9c_client.common_query_form("NOT_A_FORM", "ID")
    assert "无法把 form_id" in str(exc.value)
    assert calls == []


@pytest.mark.asyncio
async def test_query_missing_service_is_not_reported_as_existing(api):
    """本地映射指向的 Service 不在规范中时，错误信息不能谎称它存在。"""
    calls, _ = api
    with pytest.raises(u9c_client.U9CError) as exc:
        await u9c_client.common_query_form("SVM_InquiryBill", "FID")
    assert "不在 U9C OpenAPI 规范中" in str(exc.value)
    assert calls == []


def test_purchase_contract_maps_to_pc_service():
    assert u9c_catalog.resolve_service("PUR_Contract") == "PC"
    assert u9c_mapping.resolve_action("PUR_Contract", "audit") == ("PC", "Approved")


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,total,rows", [
    (ok({"RecordList": [{"ID": 1}], "RecordCount": 9}), 9, [{"ID": 1}]),
    (ok({"Rows": [{"ID": 2}], "TotalCount": 1}), 1, [{"ID": 2}]),
    (ok([{"ID": 3}]), 1, [{"ID": 3}]),
    (ok({"ID": 4}), 1, [{"ID": 4}]),
    (ok(None), 0, []),
])
async def test_query_result_shape_normalization(api, payload, total, rows):
    api[1].append(payload)
    out = u9c_client.extract_query_result(payload)
    assert out["rows"] == rows
    assert out["total"] == total


@pytest.mark.asyncio
async def test_standard_action_body_uses_opt_doc_rdata(api):
    calls, responses = api
    responses.append(ok([{"IsSucess": True}]))
    result = await u9c_client.standard_action(
        "PurchaseOrder", "Submit", ids=["1", 2], codes=["PO1"])
    assert result["Success"]
    assert calls[0].url.path == "/webapi/PurchaseOrder/Submit"
    assert json.loads(calls[0].content) == [
        {"ID": 1, "Code": "PO1"},
        {"ID": 2},
    ]


def test_standard_action_requires_id_or_code():
    with pytest.raises(u9c_client.U9CError):
        u9c_client.opt_doc_rdata([], [])


@pytest.mark.asyncio
async def test_http_error_and_401_retry(api):
    calls, responses = api
    responses.append(httpx.Response(500, text="upstream"))
    with pytest.raises(u9c_client.U9CError) as exc:
        await u9c_client.request("X", "Y", {})
    assert "HTTP 500" in str(exc.value)

    responses.append(httpx.Response(200, json=fail("token 已过期", code=401)))
    responses.append(ok("new-token"))
    responses.append(ok({"RecordList": []}))
    payload = await u9c_client.request("X", "Y", {})
    assert payload["Success"]
    assert calls[-1].headers["token"] == "new-token"


def test_result_helpers():
    assert u9c_client.result_ok(ok(None))
    assert not u9c_client.result_ok(fail("x"))
    assert u9c_client.result_message(fail("x")) == "x"
    assert u9c_client.result_message(ok([{"IsSucess": False, "ErrorMsg": "明细错误"}])) == "明细错误"


def test_convert_model_maps_legacy_fields_and_lines():
    converted = u9c_mapping.convert_model("PUR_PurchaseOrder", {
        "FID": 0,
        "FBillNo": "PO-1",
        "FDate": "2026-01-01",
        "FSupplierId": {"FNumber": "S1", "FName": "供应商一"},
        "FPOOrderEntry": [{
            "FMaterialId": {"FNumber": "M1"},
            "FQty": 3,
            "FDeliveryDate": "2026-01-05",
        }],
    })
    assert "ID" not in converted
    assert converted["DocNo"] == "PO-1"
    assert converted["BusinessDate"] == "2026-01-01"
    assert converted["Supplier"] == {"Code": "S1", "Name": "供应商一"}
    assert converted["POLineDTOList"] == [{
        "ItemInfo": {"Code": "M1"},
        "ReqQtyTU": 3,
        "DeliveryDate": "2026-01-05",
    }]


def test_convert_model_keeps_explicit_id_and_rejects_unknown_fields():
    converted = u9c_mapping.convert_model("BD_Customer", {"FID": 12, "FNumber": "C1"})
    assert converted["ID"] == 12
    with pytest.raises(u9c_mapping.MappingError) as exc:
        u9c_mapping.convert_model("BD_Customer", {"FNotAField": 1})
    assert "无法映射" in str(exc.value)


def test_form_to_service_and_entity_resolution():
    assert u9c_catalog.resolve_service("PUR_PurchaseOrder") == "PurchaseOrder"
    assert u9c_catalog.resolve_service("SAL_SaleOrder") == "SO"
    assert u9c_catalog.resolve_entity("SAL_SaleOrder") == "UFIDA.U9.SM.SO.SO"
    assert u9c_catalog.resolve_service("BD_User") == "UserInfo"
    assert u9c_catalog.resolve_service("NOT_A_FORM") is None


def test_hold_release_follow_u9c_action_summaries():
    # U9C PurchaseOrder: Release=挂起, Hold=解除挂起（与英文直觉相反）。
    assert u9c_mapping.resolve_action("PUR_PurchaseOrder", "forbid") == ("PurchaseOrder", "Release")
    assert u9c_mapping.resolve_action("PUR_PurchaseOrder", "enable") == ("PurchaseOrder", "Hold")
    assert u9c_mapping.resolve_action("PUR_PurchaseOrder", "submit") == ("PurchaseOrder", "Submit")
    assert u9c_mapping.resolve_action("PUR_PurchaseOrder", "unclose") == ("PurchaseOrder", "Open")
    assert u9c_mapping.resolve_action("SAL_SaleOrder", "cancel_assign") == ("SO", "CancelReleaseSO")


def test_unsupported_actions_are_explicit():
    with pytest.raises(u9c_mapping.MappingError) as exc:
        u9c_mapping.resolve_action("PUR_PurchaseOrder", "cancel_assign")
    assert "不支持动作" in str(exc.value)
    with pytest.raises(u9c_mapping.MappingError) as exc:
        u9c_mapping.resolve_action("PUR_PurchaseOrder", "save", model={"FID": 1})
    assert "未提供 Modify" in str(exc.value)
    with pytest.raises(u9c_mapping.MappingError):
        u9c_mapping.resolve_action("NOT_A_FORM", "submit")


@pytest.mark.asyncio
async def test_report_uses_u9c_pdf_endpoint(api):
    calls, responses = api
    responses.append(ok({"FileName": "balance.pdf", "FileContentBase64": "JVBERi0="}))
    out = await client._post("report", ("GL_RPT_AccountBalance", {}))
    assert out["Success"]
    assert calls[0].url.path == "/webapi/Report/GetReportPdfFile"
    assert json.loads(calls[0].content) == {"ReportCaseID": "GL_RPT_AccountBalance"}
    assert out["Data"]["FileContentBase64"] == "JVBERi0="


@pytest.mark.asyncio
async def test_metadata_uses_offline_u9c_catalog(api):
    calls, _ = api
    out = await client._post("metadata", ("PurchaseOrder",))
    assert out["service"] == "PurchaseOrder"
    assert out["entity"] == "UFIDA.U9.PM.PO.PurchaseOrder"
    assert calls == []


@pytest.mark.asyncio
async def test_unknown_generic_endpoint_is_rejected(api):
    calls, _ = api
    with pytest.raises(u9c_client.U9CError) as exc:
        await client._post("save_legacy", {})
    assert "没有通用端点" in str(exc.value)
    assert calls == []


def test_production_legacy_fields_translate_to_u9c_paths():
    assert u9c_mapping.return_fields(
        "PRD_MO",
        "FBillNo,FDate,FMaterialId.FNumber,FQty,FPlanStartDate,FPlanFinishDate",
    ) == ["DocNo", "ItemMaster.Code", "ProductQty", "StartDate", "CompleteDate"]
    assert u9c_mapping.return_fields(
        "PRD_PickMtrl",
        "FMoBillNo,FMaterialId.FNumber,FPickQty,FStockId.FName",
    ) == ["MOs.Code", "Item.Code", "IssueQty", "IssueWh.Name"]
