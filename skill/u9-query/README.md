# u9-query —— 用友 U9C 查询与操作助手（WorkBuddy Skill）

> 把“查 U9C / 操作 U9C ERP”的自然语言需求，路由到已连接的 **u9-mcp** MCP 服务器。

## 它做什么

- 识别用户对用友 U9C ERP 的查询/操作意图（销售/采购订单、库存、物料、客户/供应商、单据审核下推等）。
- 引导 WorkBuddy 调用 `u9-mcp` 暴露的 107 个工具，用中文结构化返回结果。
- **不**直接连接 U9C——连接由 u9-mcp 通过 U9C OpenAPI 完成，本技能只做“语义路由 + 使用约定”。

## 前置依赖

必须先让 **u9-mcp** 在 WorkBuddy 中作为 MCP 服务器连接。配置方式见仓库根目录：

- `README.md` —— 安装、配置、`U9_API_*` 环境变量说明
- `docs/AGENT-API.md` —— Agent 调用约定
- `PUBLISH.md` —— 上架清单
- `examples/workbuddy-mcp-config.example.json` —— mcp.json 模板

最小配置（用户级 `~/.workbuddy/mcp.json`）：

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

也可以只配置 `U9_API_SERVER_URL` + `U9_API_TOKEN`。

## 触发词示例

- “查一下本月已审核的销售订单”
- “物料 MAT001 的即时库存是多少”
- “帮我新建一张采购订单……”
- “审核这几张采购入库单：12345, 12346”

## 目录结构

```
skill/u9-query/
├── SKILL.md   # 技能主体（frontmatter + 指令/工具表/约定）
└── README.md  # 本文件
```

## 发布

参见 `PUBLISH.md`：可发布到 ClawHub、WorkBuddy 官方市场，或通过 GitHub 仓库地址导入。

## License

MIT © Limo
