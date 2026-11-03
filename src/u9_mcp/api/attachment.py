"""api.attachment —— U9C 附件上传/下载。"""

import base64

from . import mcp
from ..config import u9c_catalog
from ..models.attachment import AttachmentDownloadInput, AttachmentUploadInput
from ..services.attachment import (
    _attachment_exception,
    _attachment_result,
    _post_attachment,
    download_content,
)
from ..utils.formatting import _fmt


@mcp.tool(
    name="u9_upload_attachment",
    annotations={"title": "上传单据附件", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False},
)
async def u9_upload_attachment(params: AttachmentUploadInput) -> str:
    """上传单据附件（表头），直接传完整文件的 Base64，不读取服务器本地文件。

    U9C 接口：``AttachmentFile/AttachmentFileUpload``。
    U9C 没有 4 MiB 分块 / FileId 续传协议，因此一次上传一个完整文件，
    不支持分录级附件。上传完成不会自动提交或审核单据。
    """
    try:
        entity_type = params.entity_type or u9c_catalog.resolve_entity(params.form_id) or params.form_id
        payload = {
            "EntityID": str(params.bill_id),
            "EntityType": entity_type,
            "files": [{
                "FileName": params.file_name,
                "FileSize": params.decoded_size,
                "FileContent": params.send_byte,
            }],
        }
        if params.flow_id:
            payload["FlowID"] = params.flow_id
        result = await _post_attachment("attachment_upload", payload)
        out, row = _attachment_result(result, "upload_attachment")
        if out["success"]:
            handler = row.get("Handler")
            if not handler:
                raise ValueError("U9C 附件上传响应缺少 Handler")
            out.update(
                file_id=handler,
                handler=handler,
                file_name=row.get("FileName") or params.file_name,
                file_size=row.get("FileSize", params.decoded_size),
                is_last=True,
                attachment_ids=[handler],
                next_action=None,
            )
        return _fmt(out)
    except Exception as exc:
        return _attachment_exception(exc, "upload_attachment")


@mcp.tool(
    name="u9_download_attachment",
    annotations={"title": "下载单据附件", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def u9_download_attachment(params: AttachmentDownloadInput) -> str:
    """按 Handler 下载附件，返回 Base64 file_part，不写服务器本地文件。

    U9C 接口：``AttachmentFile/AttachmentFileDownload?handler=...``，返回 FileResult
    （Handler / FileName / FileSize / FileUrl），随后服务会按 FileUrl 取回文件内容。
    U9C 不支持分块，``start_index`` 必须为 0。
    """
    try:
        handler = params.effective_handler
        result = await _post_attachment(
            "attachment_download", None, params={"handler": handler},
        )
        out, row = _attachment_result(result, "download_attachment")
        if out["success"]:
            content = row.get("FileContent")
            if not content and row.get("FileUrl"):
                content = await download_content(row["FileUrl"])
            if not isinstance(content, str) or not content:
                raise ValueError("U9C 附件下载响应没有 FileContent/FileUrl")
            try:
                base64.b64decode(content, validate=True)
            except Exception:
                content = base64.b64encode(content.encode("utf-8")).decode("ascii")
            out.update(
                file_id=handler,
                handler=handler,
                file_name=row.get("FileName") or "",
                file_size=row.get("FileSize", 0),
                file_part=content,
                start_index=0,
                is_last=True,
                next_action=None,
            )
        return _fmt(out)
    except Exception as exc:
        return _attachment_exception(exc, "download_attachment")
