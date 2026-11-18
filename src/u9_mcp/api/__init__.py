"""MCP 对外接口层：创建 MCPServer 实例并注册所有工具/提示/资源。"""

from mcp.server.mcpserver import MCPServer

from ..config.service_catalog import resolve_service_tools

mcp = MCPServer("u9_mcp")

# 导入工具模块以触发 @mcp.tool / @mcp.prompt / @mcp.resource 注册
from . import attachment  # noqa: E402,F401
from . import bill  # noqa: E402,F401
from . import cost  # noqa: E402,F401
from . import finance  # noqa: E402,F401
from . import logs  # noqa: E402,F401
from . import production  # noqa: E402,F401
from . import prompts  # noqa: E402,F401
from . import query  # noqa: E402,F401
from . import report  # noqa: E402,F401
from . import sql  # noqa: E402,F401
from . import supply_chain  # noqa: E402,F401
from . import system  # noqa: E402,F401
from . import usage  # noqa: E402,F401
from . import workflow  # noqa: E402,F401


# ─────────────────────────────────────────────
# 按业务域拆分：服务过滤
# ─────────────────────────────────────────────
def registered_tool_names() -> list[str]:
    """返回当前进程已注册的全部工具名（过滤前/后均可用）。"""
    return [tool.name for tool in mcp._tool_manager.list_tools()]


def apply_service_filter(service: str | None = None) -> list[str]:
    """按服务目录过滤当前进程的工具。

    ``service`` 支持 ``all``、单个服务 ID 或逗号分隔的多个服务 ID。
    返回过滤后的工具名列表。该操作会修改全局 ``mcp``，一个进程只应调用一次；
    测试/多服务场景请使用独立进程。
    """
    allowed = resolve_service_tools(service)
    current = registered_tool_names()
    if allowed is None:
        return current

    unknown = sorted(allowed - set(current))
    if unknown:
        raise RuntimeError(
            "服务目录中的工具未注册：" + ", ".join(unknown)
        )

    for name in current:
        if name not in allowed:
            mcp.remove_tool(name)
    return registered_tool_names()


def selected_tool_names(service: str | None = None) -> list[str]:
    """不修改进程，返回该服务选择对应的工具名。"""
    allowed = resolve_service_tools(service)
    if allowed is None:
        return registered_tool_names()
    return [name for name in registered_tool_names() if name in allowed]
