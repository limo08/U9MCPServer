---
name: u9-query
slug: u9-query
displayName: 用友U9C查询与操作助手
version: 1.1.0
description: 基于已连接的 u9-mcp（第三方开源 U9C MCP 服务器，非用友官方出品），用自然语言查询与操作用友 U9C ERP：销售/采购订单、即时库存、物料档案、客户/供应商、单据提交/审核/下推等。当用户提到“U9”“U9C”“查U9”“U9 销售订单/库存/物料”等 ERP 查询或操作需求时触发。
---

# 用友 U9C 查询与操作助手 (u9-query)

> 本技能**不自己连接 U9C**。它只是“导航员”：依赖名为 `u9` 的 MCP 服务器已连接，
> 并把用户的自然语言翻译成 u9-mcp 的工具调用。

## 一、前置条件

- 入口：WorkBuddy → 插件 → MCP 服务器 → 配置 MCP，确认 `u9` 已添加且工具列表正常加载。
- u9-mcp 使用 **U9C OpenAPI**（`/webapi/{Service}/{Action}` + `token` 头）。
- 必需环境变量（二选一）：
  - OAuth2：`U9_API_SERVER_URL`、`U9_API_CLIENT_ID`、`U9_API_CLIENT_SECRET`、
    `U9_API_ENT_CODE`、`U9_API_ORG_CODE`、`U9_API_USERNAME`
  - 静态 token：`U9_API_SERVER_URL`、`U9_API_TOKEN`
- 可选：
  - `U9_API_LANGUAGE`：默认 `zh-CN`
  - `MCP_SQLSERVER_*`：SQL Server 只读探查
  - `U9_SCHEMA_FILE`：离线数据字典
- `U9_API_SERVER_URL` 填 U9C 根地址，**不要带 `/webapi`**。
- 配置模板见 `examples/workbuddy-mcp-config.example.json`。

## 二、触发示例

- “查一下本月已审核的销售订单”
- “物料 MAT001 的即时库存是多少”
- “显示客户 C001 的所有销售订单”
- “帮我新建一张采购订单，供应商 S001，物料 MAT001，数量 100”
- “审核这几张采购入库单：12345, 12346, 12347”
- “采购订单在数据库里对应哪张表”

## 三、工具概览（107 个，17 个业务域）

| 业务域 | 代表性工具 |
|--------|-----------|
| 通用单据 | `u9_query_bills`、`u9_view_bill`、`u9_save_bill`、`u9_batch_save_bills`、`u9_submit_bills`、`u9_audit_bills`、`u9_void_bills`、`u9_execute_operation` |
| 采购 | `u9_query_purchase_orders`、`u9_query_purchase_requisitions`、`u9_query_purchase_inquiry`、`u9_query_purchase_order_progress` |
| 销售 | `u9_query_sale_orders`、`u9_query_sale_quotations`、`u9_query_sales_outstock`、`u9_query_delivery_notice` |
| 库存 | `u9_query_inventory`、`u9_query_stock_bills`、`u9_query_stock_in`、`u9_query_transfer_direct` |
| 生产制造 | `u9_query_production_orders`、`u9_query_mrp_result`、`u9_save_production_order`、`u9_push_production_pick` |
| 成本/资产 | `u9_query_material_cost`、`u9_query_cost_calculation`、`u9_query_fixed_asset`、`u9_query_asset_*` |
| 财务 | `u9_query_receipts`、`u9_query_report` |
| 基础资料/权限 | `u9_query_materials`、`u9_query_partners`、`u9_query_user`、`u9_query_role`、`u9_query_permission` |
| 元数据/探查 | `u9_list_forms`、`u9_get_fields`、`u9_list_form_operations`、`u9_get_bill_template`、`u9_discover_*`、`u9_query_table`、`u9_execute_sql` |
| 附件 | `u9_upload_attachment`、`u9_download_attachment` |
| 委外 | `u9_query_outsource_orders` |

> 完整 107 个工具见 `src/u9_mcp/server.py`。部分生产计划/成本/资产/审计/工作流对象
> 在 U9C OpenAPI 中没有对应 Service，工具会明确报错；此时改用 SQL 只读查询或 U9C 界面。

## 四、使用约定

1. **先探查后查询**：不知道 `form_id` 时，用 `u9_list_forms` 搜索、`u9_get_fields` 取字段；
   通用查询用 `u9_query_bills`（必须传 `form_id`）。
2. **只读优先**：查询用 `u9_query_*`；看单据全貌用 `u9_view_bill`。
3. **写操作谨慎**：`u9_save_bill` / `u9_submit_bills` / `u9_audit_bills` / `u9_push_and_audit`
   会改动 ERP 数据，执行前必须确认单据类型、数量/金额、目标单号；必要时二次确认。
4. **U9C 动作差异**：PurchaseOrder 没有 `Modify`；`Release`=挂起、`Hold`=解除挂起。
   若工具返回“不支持动作”，不要猜测其他 Action，先查 `u9_list_form_operations`。
5. **中文呈现**：结果用中文表格/要点输出，金额、数量、日期保留原值并注明单位。
6. **错误处理**：认证失败检查 OAuth2 五项与 U9C 用户权限；连接失败检查
   `U9_API_SERVER_URL`（不要带 `/webapi`）。

## 五、常见 form_id

`PUR_PurchaseOrder` 采购订单 · `SAL_SaleOrder` 销售订单 · `PUR_Requisition` 采购申请 ·
`STK_InStock` 采购入库 · `SAL_OUTSTOCK` 销售出库 · `STK_TransferDirect` 直接调拨 ·
`STK_Inventory` 即时库存 · `BD_Material` 物料 · `BD_Customer` 客户 · `BD_Supplier` 供应商 ·
`BD_User` 用户 · `PRD_MO` 生产订单

## 六、依赖

- **u9-mcp**：`pip install u9-mcp` 或 `uvx u9-mcp`。
- 安装与配置见仓库根目录 `README.md`、`docs/AGENT-API.md`、`PUBLISH.md`。
