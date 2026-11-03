# 手工测试脚本

本目录存放**需要真实用友环境**或需要人工观察输出的测试脚本。它们不是 pytest 用例，
`tests/conftest.py` 已通过 `collect_ignore_glob` 将其排除在自动收集之外。

运行前请配置 `U9_API_*` 环境变量（见 `tests/TEST_GUIDE.md`），或让脚本从 MCP 客户端配置读取。

| 脚本 | 用途 | 是否调用真实用友 |
| --- | --- | --- |
| `test_login.py` | 验证 `_login()` 登录与会话获取 | 是 |
| `mcp_protocol_test.py` | 通过 stdio JSON-RPC 验证 MCP 协议与工具调用 | 是 |
| `mcp_test.py` | 模拟 AI 用户走完整业务场景（部分用 mock） | 部分 |
| `scenario_test.py` | Harness Engineering 约束层/反馈层场景验证 | 部分 |

```bash
python tests/manual/test_login.py
python tests/manual/mcp_protocol_test.py
python tests/manual/mcp_test.py
python tests/manual/scenario_test.py
```

`test_login.py` 默认读取 `~/.workbuddy/mcp.json`，可用环境变量覆盖：

```bash
export U9_MCP_CONFIG=/path/to/mcp.json
export U9_MCP_SERVER=u9   # mcpServers 下的服务名
```
