"""U9C 单据附件上传/下载。

U9C 的附件协议如下：

* 上传：``POST /webapi/AttachmentFile/AttachmentFileUpload``
  请求体 ``{EntityID, EntityType, FlowID, files:[{FileName, FileSize, FileContent}]}``，
  ``FileContent`` 是标准 Base64；没有 4 MiB 分块/FileId 续传协议。
* 下载：``POST /webapi/AttachmentFile/AttachmentFileDownload?handler=...``
  返回 ``FileResult``（Handler / FileName / FileSize / FileUrl），再按 FileUrl 取文件；
  也提供 ``AttachmentFileDownloadByDocID?docid=...`` 按单据列出附件。
"""

import base64
import binascii
import math
import os
import time
from typing import Any
import httpx

from . import u9c_client
from ..config import settings
from ..utils.errors import _parse_u9_errors
from ..utils.formatting import _fmt
from ..utils import usage_log


class AttachmentError(ValueError):
    pass


def _file_results(result: Any) -> list[dict]:
    if not isinstance(result, dict):
        raise AttachmentError("附件接口响应不是 JSON 对象")
    if not u9c_client.result_ok(result):
        raise AttachmentError(u9c_client.result_message(result) or "附件操作失败")
    data = result.get("Data")
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    raise AttachmentError("附件接口响应缺少 Data")


def _attachment_body(result: Any) -> dict:
    """兼容旧导出：返回附件结果中的第一条 FileResult。"""
    rows = _file_results(result)
    if not rows:
        raise AttachmentError("附件接口未返回文件结果")
    return rows[0]


def _post_attachment(ep_key: str, payload: Any = None, *, params: dict | None = None) -> Any:
    """调用 AttachmentFile 下的 U9C Action（保留旧函数名）。"""
    action = settings._EP.get(ep_key, ep_key).split("/", 1)[-1]
    return u9c_client.request(
        "AttachmentFile", action, payload, params=params,
        timeout=_timeout(),
    )


def _timeout() -> httpx.Timeout:
    raw = os.getenv("U9_ATTACHMENT_TIMEOUT")
    if raw is None or not raw.strip():
        seconds = 120.0
    else:
        try:
            seconds = float(raw)
        except ValueError:
            raise AttachmentError("U9_ATTACHMENT_TIMEOUT 必须为有限正数（秒）") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise AttachmentError("U9_ATTACHMENT_TIMEOUT 必须为有限正数（秒）")
    return httpx.Timeout(seconds, connect=30)


def _attachment_result(result: Any, op: str) -> tuple[dict, dict]:
    """把 U9C FileResult 归一化为工具输出。"""
    rows = _file_results(result)
    if not rows:
        raise AttachmentError("附件接口未返回文件结果")
    failed = [r for r in rows if r.get("IsSuccess", r.get("IsSucess", True)) is False]
    out: dict = {"op": op, "success": not failed, "response_status": result}
    primary = rows[0]
    for key in ("Handler", "FileName", "FileSize", "FileUrl", "Message"):
        if primary.get(key) not in (None, ""):
            out[key[:1].lower() + key[1:]] = primary[key]
    if failed:
        out["errors"] = _parse_u9_errors(result) or [
            {"message": str(r.get("Message") or "附件操作失败")} for r in failed
        ]
    return out, primary


def _attachment_exception(exc: Exception, op: str) -> str:
    if isinstance(exc, AttachmentError):
        message = str(exc) or "附件操作失败"
    elif isinstance(exc, httpx.HTTPStatusError):
        message = f"附件文件下载 HTTP {exc.response.status_code}"
    elif isinstance(exc, ValueError):
        message = f"附件接口调用或响应校验失败: {exc}"
    elif isinstance(exc, u9c_client.U9CError):
        message = str(exc) or "附件接口调用失败"
    else:
        message = f"附件接口调用或响应校验失败 ({type(exc).__name__}): {exc}"
    out = {"op": op, "success": False, "errors": [{"message": message}]}
    if op == "upload_attachment":
        out["outcome_unknown"] = True
        out["recovery_hint"] = (
            "无法确认附件是否已上传；请先在 U9 单据附件页核对，勿盲目重传。"
        )
    return _fmt(out)


async def download_content(file_url: str) -> str:
    """下载 FileUrl 指向的文件并返回 Base64（U9C FileResult 只给地址）。"""
    url = (file_url or "").strip()
    if not url:
        raise AttachmentError("附件结果没有 FileUrl，无法下载内容")
    if url.startswith("/"):
        url = settings.u9c_base_url().rstrip("/") + url
    async with httpx.AsyncClient(timeout=_timeout(), proxy=None,
                                 transport=httpx.AsyncHTTPTransport(http1=True),
                                 follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("ascii")
