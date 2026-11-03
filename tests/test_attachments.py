"""U9C AttachmentFile contract tests (in-memory HTTP transport)."""

import asyncio
import base64
import json
import os
import sys
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from u9_mcp import server
from u9_mcp.config import settings
from u9_mcp.services import u9c_client
from u9_mcp.utils import usage_log


def upload_input(**changes):
    values = dict(
        form_id="PUR_PurchaseOrder",
        bill_id="100723",
        bill_no="CGDD000198",
        file_name="合同.txt",
        send_byte="77u/MTIzNA==",
    )
    values.update(changes)
    return server.AttachmentUploadInput(**values)


def ok(data):
    return {"ResCode": 0, "Success": True, "ResMsg": "", "Exception": "", "Data": data}


def upload_result(handler="file-123", **changes):
    row = {
        "IsSuccess": True,
        "Handler": handler,
        "FileName": "合同.txt",
        "FileSize": 7,
        "Message": "",
    }
    row.update(changes)
    return ok([row])


def download_result(**changes):
    row = {
        "IsSuccess": True,
        "Handler": "file-123",
        "FileName": "合同.txt",
        "FileSize": 7,
        "FileUrl": "https://files.invalid/contract.txt",
    }
    row.update(changes)
    return ok(row)


@pytest.fixture
def api(monkeypatch):
    """Exercise real httpx serialization without opening a socket."""
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
    monkeypatch.setattr(settings, "TOKEN", "")
    monkeypatch.setattr(u9c_client, "_TOKEN", "test-token")
    monkeypatch.setattr(u9c_client, "_TOKEN_LOCK", None)
    login = AsyncMock(return_value="renewed-token")
    monkeypatch.setattr(u9c_client, "_auth_login", login)
    log = Mock()
    monkeypatch.setattr(usage_log, "log_tool_usage", log)
    return calls, responses, login, log


@pytest.mark.parametrize("changes", [
    {"form_id": " "}, {"bill_id": ""}, {"bill_no": " "}, {"file_name": ""},
    {"file_id": " "}, {"send_byte": "not base64!"}, {"send_byte": "data:text/plain;base64,YQ=="},
    {"send_byte": "合同"}, {"is_last": "false"}, {"is_last": False}, {"unknown": 1},
    {"entry_id": "100"}, {"entry_key": "FPOOrderEntry"},
    {"entry_key": "FPOOrderEntry", "entry_id": "-1"},
    {"send_byte": base64.b64encode(b"a" * (4 * 1024 * 1024 + 1)).decode()},
])
def test_upload_validation(changes):
    with pytest.raises(ValidationError):
        upload_input(**changes)


@pytest.mark.parametrize("changes", [
    {"file_id": " "}, {"handler": " "}, {"start_index": -1}, {"start_index": 1},
    {"start_index": True}, {"start_index": 0.5}, {"unexpected": 1},
])
def test_download_validation(changes):
    with pytest.raises(ValidationError):
        server.AttachmentDownloadInput(**{"file_id": "file-123", **changes})


def test_download_requires_handler_and_accepts_explicit_handler():
    with pytest.raises(ValidationError):
        server.AttachmentDownloadInput()
    item = server.AttachmentDownloadInput(handler="h-1")
    assert item.effective_handler == "h-1"


def test_empty_file_and_max_size_are_valid():
    assert upload_input(send_byte="").send_byte == ""
    data = base64.b64encode(b"a" * (4 * 1024 * 1024)).decode()
    assert upload_input(send_byte=data).send_byte == data
    assert upload_input().decoded_size == 7


@pytest.mark.asyncio
async def test_header_upload_wire_contract(api):
    calls, responses, login, log = api
    responses.append(upload_result())
    out = json.loads(await server.u9_upload_attachment(upload_input()))

    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert calls[0].url.path == "/webapi/AttachmentFile/AttachmentFileUpload"
    assert calls[0].headers["token"] == "test-token"
    assert calls[0].headers["content-type"] == "application/json"
    assert json.loads(calls[0].content) == {
        "EntityID": "100723",
        "EntityType": "UFIDA.U9.PM.PO.PurchaseOrder",
        "files": [{
            "FileName": "合同.txt",
            "FileSize": 7,
            "FileContent": "77u/MTIzNA==",
        }],
    }
    assert out["success"] is True
    assert out["file_id"] == "file-123" and out["handler"] == "file-123"
    assert out["attachment_ids"] == ["file-123"]
    assert out["is_last"] is True and out["next_action"] is None
    login.assert_not_awaited()
    log.assert_not_called()


@pytest.mark.asyncio
async def test_upload_accepts_entity_type_override_and_flow(api):
    calls, responses, _, _ = api
    responses.append(upload_result())
    out = json.loads(await server.u9_upload_attachment(upload_input(
        entity_type="UFIDA.U9.PM.PO.PurchaseOrder", flow_id="flow-1",
    )))
    body = json.loads(calls[0].content)
    assert body["EntityType"] == "UFIDA.U9.PM.PO.PurchaseOrder"
    assert body["FlowID"] == "flow-1"
    assert out["success"]


@pytest.mark.asyncio
async def test_download_fetches_file_url_and_returns_base64(api):
    calls, responses, _, _ = api
    responses.extend([download_result(), httpx.Response(200, content=b"1234")])
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(file_id="file-123")))

    assert len(calls) == 2
    assert calls[0].method == "POST"
    assert calls[0].url.path == "/webapi/AttachmentFile/AttachmentFileDownload"
    assert calls[0].url.params["handler"] == "file-123"
    assert calls[1].method == "GET"
    assert str(calls[1].url) == "https://files.invalid/contract.txt"
    assert out["success"] and out["file_part"] == "MTIzNA=="
    assert out["handler"] == "file-123" and out["start_index"] == 0
    assert out["is_last"] is True and out["next_action"] is None


@pytest.mark.asyncio
async def test_download_inline_content_needs_no_second_request(api):
    calls, responses, _, _ = api
    responses.append(download_result(FileUrl=None, FileContent="77u/MTIzNA=="))
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(handler="h-inline")))
    assert len(calls) == 1
    assert out["success"] and out["file_part"] == "77u/MTIzNA=="


@pytest.mark.asyncio
async def test_relative_file_url_uses_configured_server(api):
    calls, responses, _, _ = api
    responses.extend([
        download_result(FileUrl="/download/a.txt"),
        httpx.Response(200, content=b"abc"),
    ])
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(file_id="h1")))
    assert calls[1].url.path == "/download/a.txt"
    assert out["file_part"] == "YWJj"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    {"ResCode": 0, "Success": True, "Data": None},
    {"ResCode": 0, "Success": True, "Data": []},
    download_result(FileUrl=None, FileContent=None),
    httpx.Response(500, text="upstream failed"),
])
async def test_malformed_download_is_an_error(api, response):
    api[1].append(response)
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(file_id="x")))
    assert out["success"] is False and out["errors"]
    assert "next_action" not in out


@pytest.mark.asyncio
async def test_download_file_url_failure_is_reported(api):
    calls, responses, _, _ = api
    responses.extend([download_result(), httpx.Response(503, text="storage down")])
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(file_id="x")))
    assert out["success"] is False and len(calls) == 2
    assert "HTTP 503" in out["errors"][0]["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    {"ResCode": 1, "Success": False, "ResMsg": "附件权限不足", "Data": None},
    {"ResCode": 0, "Success": True, "Data": None},
    ok([{"IsSuccess": True, "FileName": "合同.txt"}]),
    httpx.Response(200, text="response_error: upstream error"),
    httpx.Response(503, text="hidden payload"),
])
async def test_failed_upload_reports_unknown_without_retry(api, response):
    calls, responses, login, log = api
    responses.append(response)
    out = json.loads(await server.u9_upload_attachment(upload_input()))
    assert out["success"] is False and out["outcome_unknown"] is True
    assert "next_action" not in out and len(calls) == 1
    login.assert_not_awaited()
    log.assert_not_called()


@pytest.mark.asyncio
async def test_download_business_error_uses_top_level_message(api):
    api[1].append({"ResCode": 1, "Success": False, "ResMsg": "文件不存在", "Data": None})
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(file_id="missing")))
    assert out["success"] is False
    assert out["errors"][0]["message"] == "文件不存在"
    assert "file_part" not in out and len(api[0]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "invalid"])
async def test_invalid_attachment_timeout_stops_before_network(api, monkeypatch, value):
    monkeypatch.setenv("U9_ATTACHMENT_TIMEOUT", value)
    result = json.loads(await server.u9_upload_attachment(upload_input()))
    assert result["success"] is False and not api[0]
    api[2].assert_not_awaited()


@pytest.mark.asyncio
async def test_attachment_timeout_is_configurable_without_extending_connect_timeout(api, monkeypatch):
    monkeypatch.setenv("U9_ATTACHMENT_TIMEOUT", "180")
    api[1].append(upload_result())
    result = json.loads(await server.u9_upload_attachment(upload_input()))
    assert result["success"]
    timeouts = api[0][0].extensions["timeout"]
    assert timeouts["read"] == 180 and timeouts["write"] == 180
    assert timeouts["connect"] == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [
    httpx.ReadTimeout("hidden payload"),
    httpx.ConnectError("hidden payload"),
])
async def test_upload_network_failures_are_not_replayed_or_logged(api, exception):
    calls, responses, login, log = api
    responses.append(exception)
    result = await server.u9_upload_attachment(upload_input())
    out = json.loads(result)
    assert out["success"] is False and out["outcome_unknown"]
    assert "勿盲目重传" in out["recovery_hint"] and len(calls) == 1
    assert "hidden payload" not in result + repr(log.call_args)
    login.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_401_reauthenticates_and_retries_once(api):
    calls, responses, login, _ = api
    responses.extend([httpx.Response(401), upload_result()])
    out = json.loads(await server.u9_upload_attachment(upload_input()))
    assert out["success"] and len(calls) == 2
    assert calls[0].content == calls[1].content
    assert calls[0].headers["token"] == "test-token"
    assert calls[1].headers["token"] == "renewed-token"
    login.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_401_stops(api):
    calls, responses, login, _ = api
    responses.extend([httpx.Response(401), httpx.Response(401)])
    out = json.loads(await server.u9_upload_attachment(upload_input()))
    assert out["success"] is False and len(calls) == 2
    login.assert_awaited_once()


@pytest.mark.asyncio
async def test_token_words_in_successful_filename_do_not_replay(api):
    api[1].append(download_result(FileContent="YQ==", FileName="token expired 会话.txt"))
    out = json.loads(await server.u9_download_attachment(
        server.AttachmentDownloadInput(file_id="x")))
    assert out["success"] and len(api[0]) == 1
    api[2].assert_not_awaited()


@pytest.mark.asyncio
async def test_cold_token_login_is_shared(api, monkeypatch):
    monkeypatch.setattr(u9c_client, "_TOKEN", None)
    api[1].extend([
        download_result(FileContent="YQ=="),
        download_result(FileContent="Yg=="),
    ])
    await asyncio.gather(*[
        server.u9_download_attachment(server.AttachmentDownloadInput(file_id="x"))
        for _ in range(2)
    ])
    api[2].assert_awaited_once()
    assert len(api[0]) == 2


@pytest.mark.asyncio
async def test_mcp_discovery_exposes_safe_annotations_and_validates_input(api):
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    assert tools["u9_upload_attachment"].annotations.read_only_hint is False
    assert tools["u9_upload_attachment"].annotations.idempotent_hint is False
    assert tools["u9_download_attachment"].annotations.read_only_hint is True
    assert tools["u9_download_attachment"].annotations.idempotent_hint is True
    api[1].append(upload_result())
    result = await server.mcp.call_tool(
        "u9_upload_attachment", {"params": upload_input().model_dump()})
    assert result and len(api[0]) == 1
