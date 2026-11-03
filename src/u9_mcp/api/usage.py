"""api.usage"""

import json

from . import mcp
from ..models.usage import UsageReportInput
from ..utils.usage_log import generate_usage_report, get_usage_stats



@mcp.tool(
    name="u9_usage_report",
    annotations={"title": "查看使用报告", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_usage_report(params: UsageReportInput) -> str:
    """查看 MCP 使用统计报告，包括工具调用频率、成功率、耗时分布等。

    此工具分析已记录的使用日志，帮助了解：
    - 哪些工具被高频使用
    - 哪些工具失败率较高
    - API 调用耗时分布
    - 使用时段分布

    Returns:
        str: 使用报告（支持 text/markdown/json 格式）
    """
    if params.format == "json":
        return json.dumps(get_usage_stats(), ensure_ascii=False, indent=2)
    elif params.format == "markdown":
        return generate_usage_report()  # 内部会生成适合的格式
    else:
        return generate_usage_report()


@mcp.tool(
    name="u9_usage_stats",
    annotations={"title": "查看使用统计", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_usage_stats() -> str:
    """获取当前会话的使用统计摘要。

    返回当前进程内聚合的统计数据：
    - 工具使用次数
    - 成功/失败次数
    - 累计耗时
    - 错误类型统计

    Returns:
        str: 统计数据的 JSON 格式
    """
    return json.dumps(get_usage_stats(), ensure_ascii=False, indent=2)
