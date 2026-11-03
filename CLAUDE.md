# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in development mode
pip install -e .

# Run the MCP server directly
u9_mcp

# Run with uvx (no install needed)
uvx u9-mcp

# Build distribution package
pip install hatchling
python -m hatchling build

# Install with all deps
pip install "mcp[cli]>=2.0.0" httpx pydantic
```

Run tests:
```bash
# Unit + mock tests (no U9 server required)
python -m pytest tests/ -v

# Integration tests (requires U9C server + OAuth2 env vars)
U9_API_SERVER_URL=https://your-u9c-host:8080 \
U9_API_CLIENT_ID=... U9_API_CLIENT_SECRET=... \
U9_API_ENT_CODE=... U9_API_ORG_CODE=... U9_API_USERNAME=... \
python -m pytest tests/test_integration.py -v

# End-to-end workflow tests (requires real U9 env, same vars as above)
# Auto-skipped when U9_API_* env vars are absent — never commit credentials in source.
python -m pytest tests/e2e -v -m e2e
```

Run the evaluation layer (`evals/` — agent 行为评估与回归对比，详见 `evals/README.md`）:
```bash
# 离线自检整条评估管线（mock agent + mock 账套状态，无需用友、不写数据）
python -m evals.run_eval --dry-run

# 真实评估（连测试账套；需先把 evals/config.yaml 的 test_account.confirmed 设为 true）
python -m evals.run_eval
```

## Architecture

This is a layered MCP Server that bridges AI clients to U9C ERP via the U9C OpenAPI
(`/webapi/{Service}/{Action}` + OAuth2 `token` header):

- `src/u9_mcp/api/` — 对外 MCP 接口（工具/提示/资源，`@mcp.tool`）
- `src/u9_mcp/config/` — 环境变量、WebAPI 端点、表单目录等配置
- `src/u9_mcp/models/` — Pydantic 输入 DTO 与实体类
- `src/u9_mcp/services/` — 业务逻辑（WebAPI 客户端、元数据、附件、单据操作）
- `src/u9_mcp/utils/` — 通用工具（日志、错误解析、格式化、SQL 探查）
- `src/u9_mcp/server.py` — 兼容门面与启动入口

### Request Flow

1. AI client calls a tool → MCPServer dispatches to the decorated async function
2. Function calls `_post(ep_key, payload)` or `_post_raw(...)` with a legacy-compatible payload
3. `_post` routes to `services/u9c_client.py`, which resolves Service/Entity and OAuth2 token
4. On 401/token-expired response, auto re-logins and retries once
5. Results are normalized to the legacy tool shape (`Result`/`Data`) where needed
6. All tools return JSON strings (success or error message from `_err()`)

### Key Internals

- **`settings._EP`** — fixed U9C endpoints (`OAuth2/AuthLogin`, `CommonEntity/Query`, `AttachmentFile/*`, `Report/GetReportPdfFile`)
- **`u9c_client._TOKEN`** — cached OAuth2 token (old `_session_id` is kept as a compatibility alias)
- **`config/u9c_catalog.py`** — offline index of bundled `data/u9c_openapi.json`: form_id → Service/Entity, fields, entries, actions
- **`services/u9c_mapping.py`** — translates legacy F* fields/filters/models/action names to U9C
- **`FORM_CATALOG` / `u9c_catalog`** — power `u9_list_forms` / `u9_get_fields` without calling U9
- **Pydantic input models** — each tool has a dedicated model (`QueryInput`, `SaveInput`, `BillIdsInput`, etc.) with `extra="forbid"` for strict validation

### Tool Categories

| Category | Tools |
|----------|-------|
| Metadata | `u9_list_forms`, `u9_get_fields` |
| Read-only queries | `u9_query_bills`, `u9_view_bill`, `u9_query_purchase_orders`, `u9_query_sale_orders`, `u9_query_stock_bills`, `u9_query_inventory`, `u9_query_materials`, `u9_query_partners` |
| Write operations | `u9_save_bill`, `u9_submit_bills`, `u9_audit_bills`, `u9_unaudit_bills`, `u9_delete_bills`, `u9_push_bill` |
| Workflow | `u9_query_pending_approvals`, `u9_query_workflow_status`, `u9_workflow_approve`, `u9_query_expense_reimburse` |
| SQL Server introspection | `u9_discover_tables`, `u9_discover_columns`, `u9_describe_table`, `u9_discover_metadata_candidates` |

### Environment Variables (required at runtime)

| Variable | Description |
|----------|-------------|
| `U9_API_SERVER_URL` | U9C base URL, e.g. `https://u9.example.com:8080` (no `/webapi`) |
| `U9_API_CLIENT_ID` | U9C OAuth2 client id |
| `U9_API_CLIENT_SECRET` | U9C OAuth2 client secret |
| `U9_API_ENT_CODE` | Enterprise/account set code (`entCode`) |
| `U9_API_ORG_CODE` | Organization code (`orgCode`) |
| `U9_API_USERNAME` | User code (`userCode`) |
| `U9_API_TOKEN` | Optional pre-issued token (alternative to OAuth2) |
| `MCP_SQLSERVER_HOST` | SQL Server host (optional, for DB introspection) |
| `MCP_SQLSERVER_PORT` | SQL Server port (default 1433) |
| `MCP_SQLSERVER_DATABASE` | Database name |
| `MCP_SQLSERVER_USER` | SQL Server user (read-only recommended) |
| `MCP_SQLSERVER_PASSWORD` | SQL Server password |

### 自动记忆约定

### 代码注释格式（💡 REMEMBER）
代码中发现值得记忆的内容时，用以下格式标记：
```python
# 💡 REMEMBER: <简短描述>
# 💡 REMEMBER: <简短描述> — <根因/结论>
```
示例：
```python
# 💡 REMEMBER: httpx 0.28+ 默认 HTTP/2，用友不支持，必须显式传 http1=True，否则全 502
# 💡 REMEMBER: demo 环境 FLinkQty 不存在 — 用 FReceiveQty+FStockInQty 代替
```

### 提取脚本
```bash
python scripts/extract_remember.py   # 扫描并打印所有记忆条目
python scripts/extract_remember.py --update  # 追加到记忆文件
```

### 会话结束检查
每次长会话结束时，AI 应主动问：
> "这次有哪些发现需要记忆？"

## GitHub Pages (`docs/`)

The website at `https://limo08.github.io/U9MCPServer/` is a single static HTML file (`docs/index.html`). The deploy workflow (`.github/workflows/deploy-pages.yml`) triggers on push to `main` branch.

### Examples (`examples/`)

Business scenario examples showing how to use each tool. See `examples/README.md` for the full list. Useful as reference when helping users with U9 MCP queries.

### Workflow Hints (`examples/workflow-hints.md`)

> **核心参考文件，AI 执行具体任务时按需检索。**

关键内容：
- **单据生命周期状态机**：Save(草稿) → Submit(待审核) → Audit(已审核)
- **高层复合工具**：`u9_create_and_audit`、`u9_push_and_audit` 一站式操作
- **写操作完整流程**：Save → Submit → Audit（含 next_action 字段说明）
- **操作返回结构化字段**：success/next_action/errors/tip
- **常见错误处理**：关联数量已达上限、字段不存在、权限不足等

### 测试指南 (`tests/TEST_GUIDE.md`)

生产模块测试参考，包含：
- 生产订单、计划管理、资产管理、成本管理、调拨管理、质量管理、审计合规
- 各模块的 form_id 和可用字段
- 已知问题列表（Demo 环境未启用的模块）

---

## Harness 约束层

`tests/test_harness.py` 定义了操作链约束和反馈循环机制：

### 结构化操作结果

每次写操作返回：
```json
{
  "success": true,
  "bill_no": "PO001",
  "fid": "12345",
  "next_action": "submit",
  "errors": [{"message": "...", "reason": "...", "suggestion": "..."}]
}
```

**判断完成**：检查 `next_action == null` 且 `success == true`。

### 错误模式库 (`KNOWN_ERROR_PATTERNS`)

位于 `src/u9_mcp/utils/errors.py`，自动匹配常见错误：

| 错误关键词 | 原因 | 建议操作 |
|-----------|------|---------|
| 502/Bad Gateway | 用友不支持 HTTP/2 | 确保 httpx 传 `http1=True` |
| 会话/session | Session 过期 | 调用 `_login()` 重新登录 |
| 关联数量 | 累计已达上限 | 检查 FReceiveQty+FStockInQty |
| 字段不存在 | 字段在当前账套未启用 | 用 `u9_get_fields` 确认 |
| 已被其他用户修改 | 乐观锁冲突 | 重新 `view_bill` 拉最新数据 |

错误命中后会携带 `matched.next_action_tool` 建议下一步工具。

### 单据状态机 (`DOC_LIFECYCLE`)

定义写操作后的状态流转：
- `save` → 草稿，下一步建议 `submit`
- `submit` → 待审核，下一步建议 `audit`
- `audit` → 已审核，操作完成
- `push` → 目标单草稿，下一步建议 `submit+audit`

---

## 测试问题排查流程

1. **运行测试查看错误**
   ```bash
   python -m pytest tests/ -v
   ```

2. **检查测试指南** (`tests/TEST_GUIDE.md`)
   - 查看已知问题列表（Demo 环境未启用的模块）
   - 确认 form_id 和字段是否正确

3. **查阅官方 API 文档**
   - 使用 MCP 浏览器访问 https://openapi.open.u9.com/ApiDoc
   - 搜索对应业务领域的单据类型
   - 查看请求参数、响应格式、代码示例

4. **常见 Demo 环境限制**
   - FLinkQty 不存在 → 用 FReceiveQty+FStockInQty 代替
   - 某些模块未启用 → form_id 存在但字段不存在
   - 权限限制 → 联系管理员开通

---

## 使用日志系统

详细文档见 `docs/usage_logging.md`。

### MCP 工具

| 工具 | 说明 |
|------|------|
| `u9_usage_report` | 查看详细使用报告（text/markdown/json） |
| `u9_usage_stats` | 获取当前会话统计摘要（JSON） |

### 命令行工具

```bash
# 生成使用报告
python scripts/usage_report.py

# 输出 Markdown 格式
python scripts/usage_report.py --format markdown -o report.md

# 分析指定日志文件
python scripts/usage_report.py --file /path/to/log.jsonl
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_USAGE_LOG` | `usage_log.jsonl` | 日志文件名 |
| `MCP_USAGE_LOG_DIR` | `.` | 日志目录 |

### 日志分析改进

基于日志可以分析：
- **高频工具** → 优先优化核心流程
- **高频错误** → 归类到 `KNOWN_ERROR_PATTERNS`
- **耗时分布** → 定位慢查询
- **未覆盖场景** → 发现新 API 需求


