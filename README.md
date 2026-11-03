<!-- mcp-name: https://github.com/limo08/U9MCPServer -->

# U9 MCP Server —— 让 AI 直接操作用友U9 ERP

> ⚠️ 本项目为**第三方开源**，非用友官方出品，与用友软件（U9）无任何隶属或授权关系。

[![PyPI version](https://img.shields.io/pypi/v/u9-mcp?style=flat-square&color=2563eb)](https://pypi.org/project/u9-mcp/)
[![Downloads](https://img.shields.io/pypi/dm/u9-mcp?style=flat-square&color=10b981)](https://pypi.org/project/u9-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/u9-mcp?style=flat-square)](https://pypi.org/project/u9-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![MCP Badge](https://lobehub.com/badge/mcp-full/wahailong-u9mcp?theme=light)](https://lobehub.com/mcp/wahailong-u9mcp)

**U9 MCP Server** 是用友U9 ERP 的 [MCP（Model Context Protocol）](https://modelcontextprotocol.io/) 服务端，让 Claude、Cursor、Windsurf、Cline 等 AI 助手能够通过自然语言直接操作用友 ERP 系统。

GitHub 仓库：https://github.com/limo08/U9MCPServer

## 为什么需要用友 MCP？

如何让AI走进企业/住进企业/并在企业内健康成长，一直是AI圈探讨并研究的方向。有了 **用友 MCP Server**，你可以：

- 直接对 AI 说："**查询本月已审核的采购订单**"
- 直接对 AI 说："**帮我新建一张销售订单**"
- 直接对 AI 说："**审核这几张入库单**"
- 在微信、WhatsApp、Telegram 中通过 OpenClaw 操作用友

AI 会自动调用用友 API 完成操作，无需手动登录 ERP 界面。

## 对实施与开发的价值

**实施阶段**
- **快速验证配置**：用自然语言直接查数据，无需登录 ERP 界面逐层点菜单
- **数据核查**：批量查询单据状态、库存数量，快速定位问题
- **客户演示**：现场说"查一下你们的采购订单"，AI 实时返回结果，演示效果直观

**日常使用**
- 业务人员自助查询，减少依赖实施人员的频率
- 批量提交、审核单据，替代重复的手工操作
- 通过微信 / WhatsApp 直接操作用友，无需打开 ERP 客户端

**开发阶段**
- 用 `u9_list_forms`、`u9_get_fields` 快速探索表单结构，替代翻文档
- 自然语言调试接口，比手写 API 请求效率更高
- 可作为内部工具基础进行二次开发，快速扩展自定义工具

## 支持的 AI 客户端

| 客户端                                           | 支持方式                                                                                   |
|--------------------------------------------------|--------------------------------------------------------------------------------------------|
| [Claude Desktop](https://claude.ai/download)     | 原生 MCP                                                                                   |
| [Cursor](https://cursor.sh/)                     | 原生 MCP                                                                                   |
| [Windsurf](https://codeium.com/windsurf)         | 原生 MCP                                                                                   |
| [Cline](https://github.com/cline/cline)          | 原生 MCP                                                                                   |
| [Continue](https://continue.dev/)                | 原生 MCP                                                                                   |
| [Claude Code CLI](https://claude.ai/claude-code) | 原生 MCP                                                                                   |
| [OpenClaw](https://openclaw.ai/)                 | 微信/WhatsApp/Telegram 中使用；将本页地址发给 OpenClaw，它会自动完成安装并引导填写用友配置 |
| [WorkBuddy](https://www.workbuddy.cn/)           | 原生 MCP                                                                                   |
| 其他 MCP 兼容客户端                              | 原生 MCP                                                                                   |

## 功能特性

- **107 个工具**：覆盖生产、成本、资产、审计、采购、销售、库存、单据附件、财务、委外加工、财务报表等 17 大业务域
- **元数据动态查询**：`get_bill_template` / `validate_bill` / `refresh_metadata`，元数据本地缓存
- **6 个 U9 库表/数据工具**：搜索表、搜索字段、查看表结构、form_id 元数据候选发现，以及只读直查表数据（`u9_query_table`）和执行单条只读 SQL（`u9_execute_sql`）；已按 `u9_schema.json` 校正 U9 真实表名，未配置 SQL Server 时结构探查自动回退到数据字典
- **自然语言操作**：用中文直接描述需求，AI 自动转换为 API 调用
- **异步高性能**：基于 async/await，支持并发请求
- **U9C OpenAPI 协议**：统一走 `/webapi/{Service}/{Action}`，请求头 `token`，响应 `ResCode/Success/ResMsg/Data`
- **自动续期**：token 过期自动重新 OAuth2 登录并重试一次；连接失败不盲目重写业务单据
- **安全认证**：U9C OAuth2（clientid/clientsecret + entCode/userCode/orgCode），或直接注入已有 token
- **类型安全**：基于 Pydantic 数据验证，参数自动补全
- **易于扩展**：基于 MCP Python SDK 2.x 的 MCPServer，轻松添加自定义工具
- **使用示例**：提供 [9 个常见业务场景示例](./examples/)，覆盖查询、新建、审核、下推等操作

## 快速安装

```bash
pip install u9-mcp
```

或使用 uvx 直接运行（推荐，无需手动安装）：

```bash
uvx u9-mcp
```

## 远程部署（HTTP / SSE 模式）

默认以 `stdio` 模式运行（本地 MCP 客户端通过子进程调用）。若要把服务部署到服务器、或用网关/托管平台（如 Smithery）**远程调用、免客户端安装**，可改用 HTTP 类传输：

```bash
# SSE 模式
uvx u9-mcp --transport sse --host 0.0.0.0 --port 8000

# Streamable HTTP 模式
uvx u9-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

- SSE 端点：`http://<host>:<port>/sse`
- Streamable HTTP 端点：`http://<host>:<port>/mcp`

> 远程模式下**仍需 U9C 凭证**（通过 `U9_API_*` 环境变量注入）。HTTP 只是传输通道，并不替代 U9C 认证——客户端连上来后，工具调用照样要通过 U9C OAuth2 获取 `token`。

也可用环境变量代替命令行参数：`U9_MCP_TRANSPORT`（stdio/sse/streamable-http）、`U9_MCP_HOST`、`U9_MCP_PORT`。

## Docker 部署

不想在服务器上折腾 Python 环境的，直接用容器。

**方式一：拉现成镜像（最快）**

```bash
docker run --rm -p 8000:8000 --env-file .env ghcr.io/limo/u9mcp:latest
```

镜像随每次发版自动构建推送，`latest` 跟最新 tag 走，也可以锁定具体版本号如 `:0.0.9`。

**方式二：docker compose（推荐长期运行）**

```bash
cp .env.example .env      # 填 U9C OAuth2 6 个变量（或 U9_API_TOKEN）
docker compose up -d
docker compose logs -f
```

**方式三：本地自己构建**

```bash
docker build -t u9-mcp .
# 国内网络慢可换 pip 源：
docker build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ -t u9-mcp .
```

起来之后 MCP 客户端连 `http://<宿主机IP>:8000/mcp`（Streamable HTTP）。

几个容易踩的点：

- 容器默认以 `streamable-http` 模式监听 `0.0.0.0:8000`。**别改回 127.0.0.1** —— 那样只有容器内部能连，宿主机映射了端口也访问不到。
- 想让容器当本地 MCP 客户端的子进程用（stdio 模式）：
  ```bash
  docker run -i --rm --env-file .env -e U9_MCP_TRANSPORT=stdio ghcr.io/limo/u9mcp:latest
  ```
- 配置对不对，先自检一把（不起服务；U9 接口登录 或 SQL Server 直连，至少配置一种）：
  ```bash
  docker run --rm --env-file .env ghcr.io/limo/u9mcp:latest --check
  ```
- 容器里跑的是用友 API 那部分。SQL Server 直连探查工具还需要额外装微软 ODBC 驱动（`msodbcsql18`），镜像里只预装了 `unixodbc` 基础库。

## 服务器一键启动（Linux）

把项目放到服务器后：

```bash
cp .env.example .env      # 填好 U9C OAuth2（或 MCP_SQLSERVER_*）配置
chmod +x start.sh
./start.sh                # 后台启动，默认 streamable-http，监听 0.0.0.0:8000
```

启动后 MCP 端点：`http://<服务器IP>:8000/mcp`（SSE 模式为 `http://<服务器IP>:8000/sse`）。

> **别把两个地址搞混**：
> - `U9_API_SERVER_URL=https://server_ip:port` 是 **本服务访问 U9C 的上游接口地址**（不要带 `/webapi`）；
> - `http://<服务器IP>:8000/mcp` 是 **MCP 服务自己的监听地址**，供 Claude/Cursor 等客户端连接。
>
> 两者用途不同，端口也可以不同。`./start.sh` 的 `status` 会同时显示这两个地址。

| 命令 | 作用 |
|------|------|
| `./start.sh` | 后台启动（等价 `start`） |
| `./start.sh run` | 前台启动，适合 systemd / supervisor / docker |
| `./start.sh stop` | 停止服务 |
| `./start.sh restart` | 重启服务 |
| `./start.sh status` | 查看 PID、传输方式和端点 |
| `./start.sh logs` | 查看最近 200 行日志（`tail -f logs/u9-mcp.log` 可跟踪） |
| `./start.sh check` | 检查 U9 接口 / SQL Server 配置，不启动服务 |
| `./start.sh install` | 手动创建 `.venv` 并安装依赖 |

常用参数：

```bash
./start.sh --port 9000
./start.sh run --transport sse --host 0.0.0.0 --port 8000
./start.sh --transport stdio          # 给本地 MCP 客户端当子进程用
```

- 首次启动若检测到依赖缺失，会自动创建 `.venv` 并 `pip install -e .`（可用 `--no-install` 关闭）。
- 配置优先级：命令行参数 > 系统环境变量 > 项目根目录 `.env`。
- PID / 运行状态 / 日志默认写入 `.u9-mcp.pid`、`.u9-mcp.state`、`logs/u9-mcp.log`，均已在 `.gitignore` 中忽略。
- 日志位置不写死，可通过 `.env` 的 `U9_MCP_LOG_FILE` 指定；相对路径基于项目根目录，也可用绝对路径（如 `/var/log/u9-mcp/server.log`）。PID/状态文件同理支持 `U9_MCP_PID_FILE`、`U9_MCP_STATE_FILE`。

**systemd 托管示例**：

```ini
[Unit]
Description=U9 MCP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/u9-mcp
EnvironmentFile=/opt/u9-mcp/.env
ExecStart=/opt/u9-mcp/start.sh run
Restart=always
RestartSec=3
User=u9mcp

[Install]
WantedBy=multi-user.target
```

> systemd 场景用 `run`（前台），不要用默认的后台模式，否则 `Type=simple` 会误判服务退出。

## 配置教程

### 第一步：U9C 后台准备

1. 在 U9C 开放平台申请 OAuth2 应用，取得 `clientid` / `clientsecret`
2. 准备企业账套编码 `entCode`、组织编码 `orgCode`、用户编码 `userCode`（建议专用集成账号，**不要用 Administrator**）
3. 为该账号分配所需模块与数据权限；U9C OpenAPI 以该用户身份执行，权限与 U9 界面一致

### 第二步：配置 MCP 客户端

在你的 MCP 客户端配置文件中添加以下内容：

```json
{
  "mcpServers": {
    "u9": {
      "command": "uvx",
      "args": ["u9-mcp"],
      "env": {
        "U9_API_SERVER_URL": "https://your-u9c-host:8080",
        "U9_API_CLIENT_ID": "your-client-id",
        "U9_API_CLIENT_SECRET": "your-client-secret",
        "U9_API_ENT_CODE": "your-ent-code",
        "U9_API_ORG_CODE": "your-org-code",
        "U9_API_USERNAME": "your-user-code"
      }
    }
  }
}
```

如果已有 U9C 签发的 token，也可以只设置 `U9_API_SERVER_URL` + `U9_API_TOKEN`。静态 token 失效后不会自动续期；同时配置 OAuth2 凭证时会自动降级重登。

**配置文件位置：**

| 客户端 | 配置文件路径 |
|--------|-------------|
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Cursor | Settings → MCP → Add Server |
| Claude Code CLI | `~/.claude/settings.json` |
| OpenClaw | 使用 `openclaw mcp set` 命令配置，自动热加载无需重启 |

### 第三步：重启客户端

配置完成后重启你的 MCP 客户端即可开始使用。

> **OpenClaw 用户**：使用 `openclaw mcp set` 配置后会自动热加载，**无需重启网关**。

## 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `U9_API_SERVER_URL` | U9C 服务器根地址（不要带 `/webapi`） | `https://u9.example.com:8080` |
| `U9_API_CLIENT_ID` | OAuth2 client id | `your-client-id` |
| `U9_API_CLIENT_SECRET` | OAuth2 client secret | `your-client-secret` |
| `U9_API_ENT_CODE` | 企业账套编码（entCode） | `001` |
| `U9_API_ORG_CODE` | 组织编码（orgCode） | `01` |
| `U9_API_USERNAME` | 用户编码（userCode） | `demo` |
| `U9_API_TOKEN` | 可选：直接注入已签发 token | `eyJ...` |
| `U9_API_LANGUAGE` | 可选：语言，默认 `zh-CN` | `zh-CN` |
| `U9_API_LOGIN_TYPE` | 可选：OAuth2 登录类型，默认 `1` | `1` |
| `U9_API_LOGIN_DATE` | 可选：登录上下文日期 | `2026-11-02` |
| `U9_API_ENTITY_MAP` | 可选：form_id → U9C 实体全名覆盖映射（JSON） | `{"PUR_PurchaseOrder":"UFIDA.U9.PM.PO.PurchaseOrder"}` |
| `U9_ATTACHMENT_TIMEOUT` | 附件传输读写等待时间（秒，可选，默认 120；连接超时仍为 30） | `120` |
| `MCP_SQLSERVER_HOST` | SQL Server 主机（可选，用于数据库探查） | `localhost` |
| `MCP_SQLSERVER_PORT` | SQL Server 端口（默认 1433） | `1433` |
| `MCP_SQLSERVER_DATABASE` | 数据库名 | `AIS20260309171043` |
| `MCP_SQLSERVER_USER` | SQL Server 用户（建议只读账号） | `sa` |
| `MCP_SQLSERVER_PASSWORD` | SQL Server 密码 | `xxxx` |
| `U9_SCHEMA_FILE` | U9 数据字典 JSON 路径（可选；未配置 SQL Server 时用于表结构探查回退） | `./data/u9_schema.json` |
| `U9_MCP_LOG_FILE` | `start.sh` 运行日志路径（可选；相对路径基于项目根目录，支持绝对路径） | `/var/log/u9-mcp/server.log` |
| `U9_MCP_PID_FILE` | `start.sh` PID 文件路径（可选） | `/run/u9-mcp.pid` |
| `U9_MCP_STATE_FILE` | `start.sh` 运行状态文件路径（可选） | `/run/u9-mcp.state` |
| `MCP_USAGE_LOG` | 工具调用统计日志路径（可选，默认 `usage_log.jsonl`） | `/var/log/u9-mcp/usage.jsonl` |

> 用友接口变量统一使用 `U9_API_*` 前缀（如 `U9_API_SERVER_URL`）；MCP 运行参数使用 `U9_MCP_*`（如 `U9_MCP_PORT`）。
> 只配置一套即可：**U9C OpenAPI**（`U9_API_SERVER_URL` + OAuth2 五项，或 `U9_API_TOKEN`）或 **SQL Server 直连**（`MCP_SQLSERVER_*`）。

## 可用工具列表

共 **107 个工具**，按业务域分组（每组列出代表性工具，完整清单见 `src/u9_mcp/api/`）：

| 业务域 | 数量 | 代表性工具 |
|--------|------|-----------|
| 通用单据 | 18 | `u9_save_bill` · `u9_batch_save_bills` · `u9_submit_bills` · `u9_audit_bills` · `u9_validate_bill` · `u9_push_bill` · `u9_void_bills` · `u9_unvoid_bills` · `u9_execute_operation` |
| 生产制造 | 12 | `u9_query_production_orders` · `u9_save_production_order` · `u9_query_mrp_result` · `u9_push_production_pick` |
| 成本核算 | 12 | `u9_query_material_cost` · `u9_query_cost_calculation` · `u9_save_cost_adjustment` · `u9_query_finished_product_cost` |
| 固定资产 | 6 | `u9_query_fixed_asset` · `u9_save_asset` · `u9_query_asset_depreciation` |
| 库存 | 9 | `u9_query_inventory` · `u9_query_stock_bills` · `u9_push_stock_transfer` · `u9_query_transfer_direct` |
| 委外加工 | 1 | `u9_query_outsource_orders`（委外订单 SUB_SubReqOrder：在制量/逾期/回货交期） |
| 审计合规 | 6 | `u9_query_operation_logs` · `u9_query_audit_log` · `u9_query_change_log` · `u9_query_permission_changes` · `u9_create_and_audit` · `u9_push_and_audit` |
| 采购 | 5 | `u9_query_purchase_orders` · `u9_query_purchase_requisitions` · `u9_query_purchase_inquiry` · `u9_query_purchase_order_progress` · `u9_query_supplier_quotes` |
| 销售 | 4 | `u9_query_sale_orders` · `u9_query_sale_quotations` · `u9_query_sales_outstock` · `u9_query_delivery_notice` |
| 工作流/审批 | 4 | `u9_query_pending_approvals` · `u9_workflow_approve` · `u9_query_approval_flow` |
| 基础资料/权限 | 5 | `u9_query_materials` · `u9_query_partners` · `u9_query_user` · `u9_query_role` · `u9_query_permission` |
| 元数据/探查 | 11 | `u9_get_fields` · `u9_list_form_operations` · `u9_discover_tables` · `u9_query_table` · `u9_execute_sql` · `u9_get_bill_template` |
| 系统/其他 | 8 | `u9_query_system_config` · `u9_query_quality_inspections` · `u9_query_expense_reimburse` · `u9_query_number_rule` · `u9_query_loan_balance` · `u9_query_data_backup` |
| 统计 | 2 | `u9_usage_stats` · `u9_usage_report` |
| 财务报表 | 1 | `u9_query_report`（`Report/GetReportPdfFile`，按 ReportCaseID 或订阅报表名生成 PDF） |
| 单据附件 | 2 | `u9_upload_attachment` · `u9_download_attachment`（`AttachmentFile*`，表头附件，Base64） |
| 财务收款 | 1 | `u9_query_receipts`（收款单 AR_Receivable：实收金额/结算方式/核销金额） |

> 元数据/探查含 4 个库表结构工具（`u9_discover_tables` / `u9_discover_columns` / `u9_describe_table` / `u9_discover_metadata_candidates`）和 2 个只读数据查询工具（`u9_query_table` / `u9_execute_sql`）。配置 `MCP_SQLSERVER_*` 可查真实数据库；未配置时结构探查回退到 `U9_SCHEMA_FILE` 指向的 `u9_schema.json`。
>
> U9C OpenAPI 只开放了部分业务对象。成本核算、审计/上机日志、角色权限、编码规则、系统配置、数据备份等工具在标准 U9C 环境中没有对应 Service，会返回明确的不支持说明；只读统计请用 `u9_query_table` / `u9_execute_sql`，或通过 `U9_API_ENTITY_MAP` 映射账套自定义实体。

### 元数据查询

| 工具名称 | 功能说明 |
|----------|---------|
| `u9_list_forms` | 搜索可用表单（不知道 form_id 时使用） |
| `u9_get_fields` | 获取表单字段列表 |

### 数据查询（只读操作）

| 工具名称 | 功能说明 |
|----------|---------|
| `u9_query_bills` | 通用单据查询，支持任意 form_id |
| `u9_view_bill` | 查看单据完整详情 |
| `u9_query_purchase_orders` | 查询采购订单 |
| `u9_query_sale_orders` | 查询销售订单 |
| `u9_query_sale_quotations` | 查询销售报价单（SAL_Quotation） |
| `u9_query_stock_bills` | 查询出入库单据 |
| `u9_query_inventory` | 查询即时库存 |
| `u9_query_receipts` | 查询收款单（AR_Receivable）：实收金额、结算方式（现金/转账/承兑汇票）、核销金额，营收/回款/应收余额核心数据源 |
| `u9_query_outsource_orders` | 查询委外加工订单（SUB_SubReqOrder）：在制量、逾期分析、回货交期预测，WIP 数据核心来源 |
| `u9_query_materials` | 查询物料档案 |
| `u9_query_partners` | 查询客户/供应商档案 |
| `u9_query_report` | U9C 报表文件：`Report/GetReportPdfFile`，传 `ReportCaseID` 或 `SubscirbeReportName`，返回 `FileName` + `FileContentBase64`（PDF） |

### 单据操作（写操作）

| 工具名称 | 功能说明 |
|----------|---------|
| `u9_save_bill` | 新建或修改单据 |
| `u9_submit_bills` | 提交单据 |
| `u9_audit_bills` | 审核单据 |
| `u9_unaudit_bills` | 反审核单据 |
| `u9_delete_bills` | 删除单据 |

### 单据附件（U9C AttachmentFile）

| 工具名称 | 功能说明 |
|----------|---------|
| `u9_upload_attachment` | `AttachmentFile/AttachmentFileUpload`：一次上传完整文件（Base64），绑定已存在的表头单据，返回 `Handler`（兼容别名 `file_id`） |
| `u9_download_attachment` | `AttachmentFile/AttachmentFileDownload?handler=...`：返回 `FileResult`，若只有 `FileUrl` 则自动取回内容并返回 Base64 |

U9C 没有分块/FileId 续传协议，也不支持该接口的分录级附件，因此 `is_last` 必须为 `true`、`file_id` / `entry_key` / `entry_id` 必须为空，单文件最大 4 MiB。附件工具不读写 MCP 服务器本地文件，上传完成不会自动提交或审核单据。详见 [单据附件示例](./examples/bill-attachments.md)。

## 使用示例

配置完成后，在 Claude 或其他 AI 客户端中直接用自然语言操作：

```
# 查询类
查询最近 20 条已审核的采购订单
查一下物料编码 MAT001 的即时库存
查询客户编码 C001 的所有销售订单
显示本月所有未提交的销售订单

# 操作类
帮我新建一张采购订单，供应商 S001，物料 MAT001，数量 100，单价 10.5
审核这几张采购入库单：12345, 12346, 12347
反审核销售订单 SO2024001
```

## U9 库表探查与只读查询工具（可选）

配置 `MCP_SQLSERVER_*` 可查真实 SQL Server；未配置时自动回退到 U9 数据字典（`U9_SCHEMA_FILE`），帮助理解 U9 数据库结构：

| 工具名称 | 功能说明 |
|---------|---------|
| `u9_discover_tables` | 按关键字搜索数据库表名 |
| `u9_discover_columns` | 按关键字搜索字段名（含所在表） |
| `u9_describe_table` | 查看表完整结构（字段、类型、主键、外键） |
| `u9_discover_metadata_candidates` | 根据 form_id 发现对应的数据库表名 |
| `u9_query_table` | 按表名只读查询业务数据（过滤/排序/分页/总数；字段名白名单 + 参数化） |
| `u9_execute_sql` | 执行单条只读 SQL（SELECT/WITH），内置 DML/DDL/多语句拦截 |

**典型用法**：先问 AI "采购订单在数据库里对应哪张表"，再用 `u9_describe_table` 看字段结构，最后用 `u9_query_table` 按条件读取数据。数据库直连工具均为只读，写入仍应走 WebAPI 以保证业务规则生效。

## 支持的单据类型（form_id）

| form_id | 说明 |
|---------|------|
| `PUR_PurchaseOrder` | 采购订单 |
| `SAL_SaleOrder` | 销售订单 |
| `STK_InStock` | 采购入库单 |
| `SAL_OUTSTOCK` | 销售出库单 |
| `STK_MisDelivery` | 其他出库单 |
| `STK_Miscellaneous` | 其他入库单 |
| `STK_TransferDirect` | 直接调拨单 |
| `BD_Material` | 物料档案 |
| `BD_Customer` | 客户档案 |
| `BD_Supplier` | 供应商档案 |
| `STK_Inventory` | 即时库存 |

## 常见问题

**Q: 提示认证失败怎么办？**
检查 `U9_API_CLIENT_ID` / `U9_API_CLIENT_SECRET` / `U9_API_ENT_CODE` / `U9_API_ORG_CODE` / `U9_API_USERNAME` 是否正确，以及该用户是否有对应 U9C 模块与数据权限。也可先用 `U9_API_TOKEN` 直接验证 token 是否有效。

**Q: 连接超时怎么解决？**
检查 `U9_API_SERVER_URL` 是否为 U9C 根地址且服务器可访问（不要写 `/webapi`；接口根路径由 MCP 自动拼接）。

**Q: MCP 客户端测试连接失败，或访问 `/mcp` 返回 404？**

先确认 u9-mcp 真的监听在你配置的端口，且该端口没有被其他程序占用：

```bash
./start.sh status
ss -ltnp | grep :8000
```

如果 8000 被别的服务占用（很常见），`start.sh` 会直接报“端口已被占用”。换一个端口即可：

```bash
./start.sh --port 8800
```

然后把 MCP 客户端地址改成 `http://127.0.0.1:8800/mcp`。MCP 服务的监听地址与 `U9_API_SERVER_URL`（U9C 地址）不是同一个地址。

**Q: 客户端报 `Unknown scheme for proxy URL ... socks://`？**

MCP 客户端继承了系统的 `ALL_PROXY` / `all_proxy` 环境变量，而 HTTP 客户端不支持 `socks://` 代理。给客户端设置：

```bash
NO_PROXY=127.0.0.1,localhost
```

或移除 `ALL_PROXY` / `all_proxy` 中的 socks 代理后重启客户端。

**Q: 支持用友U9公有云吗？**
支持。公有云与私有化部署都使用 U9C OpenAPI 的 `/webapi` 协议；只需按部署环境填写 `U9_API_SERVER_URL` 与 OAuth2 凭证。

**Q: 升级后仍报 `No module named 'mcp.server.fastmcp'`？**

本项目已升级到 **mcp 2.x**，服务端入口由 `FastMCP` 改为 `mcp.server.mcpserver.MCPServer`。若仍看到该错误，说明运行环境缓存了旧版 `u9-mcp` / `mcp`。两种解决方式：

1. 清理 uv 缓存后重试：`uv cache clean`，再重新启动 `uvx u9-mcp`；
2. 或改用 pip 安装 + 模块方式启动（更稳，推荐用于生产）：

   ```bash
   pip install u9-mcp
   ```

   MCP 客户端配置改为：

   ```json
   {
     "mcpServers": {
       "u9": {
         "command": "python",
         "args": ["-m", "u9_mcp.server"],
         "env": { "U9_API_SERVER_URL": "...", "U9_API_CLIENT_ID": "...", "U9_API_CLIENT_SECRET": "...", "U9_API_ENT_CODE": "...", "U9_API_ORG_CODE": "...", "U9_API_USERNAME": "..." }
       }
     }
   }
   ```

**Q: 如何添加自定义工具？**
基于 MCPServer（mcp 2.x）框架，在 `src/u9_mcp/api/` 对应模块中添加 `@mcp.tool()` 装饰器方法即可扩展。


## 联系方式

- QQ：2774390734
- 邮箱：limo@utechai.com
- 微信：limo08

## License

MIT © Limo
