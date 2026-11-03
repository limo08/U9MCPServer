---
name: u9-mcp-dev
description: |
  Knowledge base for the U9 MCP Dev Squad. Covers how to integrate the U9 OpenAPI (ApiDoc) interfaces into the u9-mcp Python+MCPServer (mcp 2.x) project: WebAPI login/metadata caching, field-discovery SOP, 二开 (customized) bill pitfalls, and the ApiDoc coverage tracking template.
metadata:
  version: "1.0.0"
---

# 用友 MCP 开发团 · 知识库

本 Skill 是 `u9-mcp-dev` 专家团的共享知识底座，供主理人（龚联达）与四位团员（范探源 / 寇豆码 / 严过关 / 温书成）在协作时查阅。目标是**把用友开放平台 ApiDoc 的全部接口集成进 `D:\AI\projects\u9-mcp`**。

## 项目事实（已实证，勿凭记忆）

- **源码位置**：`D:\AI\projects\u9-mcp`，Python + MCPServer（mcp 2.x）。
- **工具规模**：当前 **107 个 `@mcp.tool`**，覆盖 17 个业务域；元数据读取 U9C 离线目录，SQL Server 仅只读查询。
- **构建后端**：`hatchling`（`python -m build`）。
- **运行环境**：U9C OpenAPI（`https://openapi.yyu9c.com/doc.html`）；配置 `U9_API_SERVER_URL` / `U9_API_CLIENT_ID` / `U9_API_CLIENT_SECRET` / `U9_API_ENT_CODE` / `U9_API_ORG_CODE` / `U9_API_USERNAME`，也可用 `U9_API_TOKEN` 跳过登录。
- **登录方式**：OAuth2 `GET /webapi/OAuth2/AuthLogin`，后续请求带 `token` 请求头。
- **响应结构**：`{"ResCode":0,"Success":true,"ResMsg":"","Data":...,"Exception":""}`。
- **查询/动作**：查询走 `POST /webapi/CommonEntity/Query`；写操作走 `POST /webapi/{Service}/{Action}`。
- **动作语义**：以 U9C OpenAPI `summary` 为准（如 `PurchaseOrder.Release`=挂起、`Hold`=解除挂起），不要按经验硬编码。

## U9C OpenAPI 结构

`https://openapi.yyu9c.com/doc.html` 的规范已随包发布到 `src/u9_mcp/data/u9c_openapi.json`：

- **628 paths / 157 Services (tags) / 838 schemas**。
- 每个 Service 暴露自己的动作（`/webapi/{Service}/{Action}`），没有跨 Service 统一的 `Save` / `Audit` / 通用查询 / 通用执行动作。
- 查询统一走 `CommonEntity/Query`，请求体为 `UFSoft.UBF.MVC.Common.ApiComParms`。
- 动作列表与中文摘要由 `u9c_catalog` 读取；不要假设所有 Service 的动作相同。

## 集成工作流（团队 SOP 映射）

| 阶段 | 负责团员 | 关键动作 | 输入 → 输出 |
|------|----------|----------|-------------|
| 探字段 / WebAPI 映射 | 范探源 | `u9_get_fields` 探 U9C Service/字段；`u9_list_form_operations` 查真实 Action | 任务 → 字段/操作映射表 |
| 实现 `@mcp.tool` | 寇豆码 | 复用提速工具，落地工具代码 | 映射表 → 工具签名 |
| 测试回归 | 严过关 | `bin/kmcp test` + 用例；区分权限拒绝 vs 正常数据 | 工具签名 → 回归报告 |
| 文档 / 发布 | 温书成 | 更新 `docs/`、`mcp_optimization_notes.md`、CHANGELOG；`bin/kmcp build` → `twine upload` → Pages | 变更 → 发布清单 |

## 提速工具（已落地 server.py，优先复用）

- `u9_validate_bill`：保存前校验，返回 `auto_fixes / missing_required / entry_issues / suggestions`，**不真正保存**。
- `u9_get_bill_template`：取已验证 model 骨架，支持 `SAL_Quotation` / `SAL_SaleOrder` / `PUR_PurchaseOrder`。
- `u9_refresh_metadata`：强制刷新元数据。
- 元数据已落盘缓存到 `~/.workbuddy/u9_metadata_cache/`。

**推荐工作流**：`get_bill_template → 填数 → validate_bill → save_bill`。

## 必读参考

- `references/webapi-login-cache.md` — U9C OAuth2 登录、查询/动作端点、元数据缓存。
- `references/field-discovery-sop.md` — `u9_get_fields` 探字段的标准操作流程与返回解析。
- `references/ercustom-pitfalls.md` — 本环境二开单据坑（SAL_SaleOrder 二开、TRNV_Receipt/PaymentSlip、FCUSTID 全大写、FBaseUnitId 等）。
- `references/apidoc-coverage-template.md` — ApiDoc 覆盖进度跟踪表模板，配合 `bin/kmcp coverage` 使用。
- `references/avoid-duplication.md` — **防止重复开发红线**：通用/专用工具清单 + 决策树 + `bin/kmcp tools` 查重用法。开工前必读。

## 助手命令（bin/kmcp）

团队配套 CLI `bin/kmcp`：

- `bin/kmcp test` — 跑 `evals/` + `tests/` 回归（连真实用友环境）。
- `bin/kmcp build` — `python -m build` 构建 wheel / sdist。
- `bin/kmcp list-tools` — 统计 `@mcp.tool` 数量。
- `bin/kmcp coverage` — 对照 `references/api-inventory-raw.json` 输出 ApiDoc 覆盖进度。
