"""U9C 附件上传/下载 DTO。"""

import base64
import binascii
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..config.settings import _ATTACHMENT_BASE64_LENGTH, _ATTACHMENT_CHUNK_BYTES


class AttachmentUploadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., min_length=1, description="单据 form_id 或 U9C 实体类型，例如 PUR_PurchaseOrder")
    bill_id: str = Field(..., min_length=1, description="已存在单据的 ID（U9C EntityID）")
    bill_no: str = Field(..., min_length=1, description="单据编号（保留用于兼容；U9C 上传以 bill_id 为准）")
    file_name: str = Field(..., min_length=1, description="含扩展名的文件名，不是本地文件路径")
    send_byte: str = Field(
        ..., max_length=_ATTACHMENT_BASE64_LENGTH,
        description="完整文件的标准 Base64 字符串（U9C 无分块协议，单次上传整个文件）",
    )
    is_last: bool = Field(default=True, strict=True, description="U9C 不支持分块；必须为 true")
    file_id: Optional[str] = Field(default=None, min_length=1, description="U9C 不支持续传；必须为空")
    entry_key: Optional[str] = Field(default=None, min_length=1, description="U9C 该接口不支持分录附件；必须为空")
    entry_id: Optional[str] = Field(default=None, min_length=1, description="U9C 该接口不支持分录附件；必须为空")
    alias_file_name: Optional[str] = Field(default=None, description="附件别名（U9C 无该字段，忽略）")
    entity_type: Optional[str] = Field(default=None, description="U9C EntityType；默认取实体全名或 form_id")
    flow_id: Optional[str] = Field(default=None, description="U9C 审批流 FlowID，可选")

    @field_validator("send_byte")
    @classmethod
    def validate_base64(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("send_byte 必须是标准 Base64 字符串") from None
        if len(decoded) > _ATTACHMENT_CHUNK_BYTES:
            raise ValueError("U9C 附件单次最多 4 MiB")
        return value

    @model_validator(mode="after")
    def validate_u9c_contract(self):
        if not self.is_last or self.file_id:
            raise ValueError("U9C 附件接口没有分块/续传协议：请一次上传完整文件，is_last=true 且不要传 file_id")
        if self.entry_key or self.entry_id:
            raise ValueError("U9C AttachmentFileUpload 不支持分录级附件，请只传表头附件")
        return self

    @property
    def decoded_size(self) -> int:
        return len(base64.b64decode(self.send_byte, validate=True))


class AttachmentDownloadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    file_id: Optional[str] = Field(default=None, min_length=1, description="附件 Handler（U9C FileResult.Handler）")
    handler: Optional[str] = Field(default=None, min_length=1, description="附件 Handler 的显式写法")
    start_index: int = Field(default=0, ge=0, strict=True, description="U9C 不支持断点续传；必须为 0")

    @model_validator(mode="after")
    def validate_handler(self):
        if not (self.handler or self.file_id):
            raise ValueError("必须提供 handler（或兼容字段 file_id）")
        if self.start_index:
            raise ValueError("U9C 附件下载不支持 start_index 断点续传，请传 0")
        return self

    @property
    def effective_handler(self) -> str:
        return self.handler or self.file_id or ""
