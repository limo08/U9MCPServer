"""使用统计相关 DTO。"""

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────
# 使用日志工具
# ─────────────────────────────────────────────

class UsageReportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    format: str = Field(default="text", description="报告格式: text | markdown | json")
