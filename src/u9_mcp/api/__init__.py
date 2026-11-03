"""MCP 对外接口层：创建 MCPServer 实例并注册所有工具/提示/资源。"""

from mcp.server.mcpserver import MCPServer

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
