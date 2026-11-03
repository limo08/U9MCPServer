# U9 MCP 上架清单（Publish Guide）

本文件汇总把 **u9-mcp**（MCP 服务器）及配套 **u9-query**（WorkBuddy 技能）发布到市场所需材料。
所有外部发布动作（上传 PyPI / 推 GitHub / 提交 ClawHub）都需手动执行或在确认后进行。

---

## 0. 现状盘点

| 项 | 值                                                                                |
|----|-----------------------------------------------------------------------------------|
| PyPI 包名 | `u9-mcp`                                                                          |
| GitHub | https://github.com/limo08/U9MCPServer                                             |
| 官网 | https://github.com/limo08/U9MCPServer/                                            |
| 工具数 | **107 个，覆盖 17 大业务域**                                                      |
| 启动入口 | `uvx u9-mcp` 或 `python -m u9_mcp.server`                                         |
| 底层协议 | **U9C OpenAPI**：`/webapi/{Service}/{Action}` + `token` 头                        |
| 认证方式 | U9C OAuth2（clientid/clientsecret + entCode/userCode/orgCode），或 `U9_API_TOKEN` |
| 配置文件 | `pyproject.toml`（hatchling，脚本 `u9-mcp = u9_mcp.server:main`）                 |

---

## 1. 发布前自检

- [ ] **版本号**：更新 `pyproject.toml` / `server.json` / `__init__` 版本，构建后上传。
- [ ] **README 完整**：安装 / 配置 / 环境变量 / 工具表 / 示例 / FAQ 已对齐 U9C OpenAPI。
- [ ] **LICENSE**：MIT（已有）。
- [ ] **CHANGELOG**：记录首次发布及 U9C OpenAPI 能力。
- [ ] **无硬编码密钥**：所有凭证走环境变量。
- [ ] **示例充分**：`examples/` 含查询、创建、审核、下推、附件等场景。
- [ ] **配套技能**：`skill/u9-query/` 已更新为 U9C 配置与工具名。
- [ ] **接入模板**：`examples/workbuddy-mcp-config.example.json` 已更新。
- [ ] **测试**：`python -m pytest tests/ -q` 全绿（无真实租户时集成测试自动跳过）。

---

## 2. 发布 MCP 服务器到 ClawHub

1. 访问 https://clawhub.ai/ ，用 GitHub 账号登录。
2. 点击“发布技能 / 发布 MCP”，提交类型选 **MCP Server**。
3. 填写 GitHub 仓库地址 `https://github.com/limo08/U9MCPServer`，或上传本地文件夹。
4. 填写信息：
   - 名称：`u9-mcp`
   - 描述：用友 U9C MCP 服务器，让 AI 用自然语言查询与操作 ERP（107 个工具，17 个业务域）。
   - 版本：与 PyPI 对齐。
   - 标签：`erp` `用友` `u9c` `mcp` `openapi`
   - 启动命令：`uvx u9-mcp`
   - 环境变量（只写名称）：`U9_API_SERVER_URL` / `U9_API_CLIENT_ID` /
     `U9_API_CLIENT_SECRET` / `U9_API_ENT_CODE` / `U9_API_ORG_CODE` /
     `U9_API_USERNAME`（或 `U9_API_TOKEN`）
5. 提交审核，通常 1–3 个工作日完成安全扫描与功能测试。

---

## 3. 发布配套 Skill（u9-query）

仓库内 `skill/u9-query/` 即技能包：

- **ClawHub**：发布技能 → 上传 `skill/u9-query` 或填仓库地址。
- **WorkBuddy 官方市场**：按应用内“技能管理 / 发布”入口提交。
- **GitHub 导入**：技能管理选“通过 URL 导入”，填仓库地址并指定 `skill/u9-query`。

> 技能负责“语义路由 + 使用约定”，MCP 负责真正的 U9C 连接，两者独立上架。

---

## 4. WorkBuddy 用户接入配置

用户级 `~/.workbuddy/mcp.json`：

```json
{
  "mcpServers": {
    "u9": {
      "command": "uvx",
      "args": ["u9-mcp"],
      "env": {
        "U9_API_SERVER_URL": "https://YOUR-U9C-HOST:8080",
        "U9_API_CLIENT_ID": "YOUR-CLIENT-ID",
        "U9_API_CLIENT_SECRET": "YOUR-CLIENT-SECRET",
        "U9_API_ENT_CODE": "YOUR-ENT-CODE",
        "U9_API_ORG_CODE": "YOUR-ORG-CODE",
        "U9_API_USERNAME": "YOUR-USER-CODE"
      }
    }
  }
}
```

- `U9_API_SERVER_URL` 是 U9C 根地址，**不要带 `/webapi`**。
- 生产环境建议 `pip install u9-mcp` 后使用 `"command": "python", "args": ["-m", "u9_mcp.server"]`。
- 模板见 `examples/workbuddy-mcp-config.example.json`。

---

## 5. 注意事项

- **凭证安全**：市场描述与配置示例只写变量名，不写真实密码/token。
- **协议**：仅使用 U9C OpenAPI；旧的动态表单接口与 Cookie 会话均已不再使用。
- **权限**：U9C 用户需有对应模块与数据权限；权限不足会原样返回业务错误。
- **数据库只读**：SQL Server 探查工具只读，写入走 OpenAPI，避免绕过 U9 业务规则。
- **不支持对象**：U9C OpenAPI 无对应 Service 的对象会明确报错，文档已列出。

---

## 6. 后续可选项

- 在官网增加 U9C 一键接入说明与 mcp.json 片段。
- 在 ClawHub / 其他 MCP 市场同步登记。
- 每次改动 bump 版本、更新 CHANGELOG、README 与 `docs/AGENT-API.md`。
