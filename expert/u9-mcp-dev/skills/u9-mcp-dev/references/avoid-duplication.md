# 防止重复开发（必读红线）

> 适用：主理人排期、范探源出映射、寇豆码写工具、严过关回归时都要遵守。
> 现状：u9-mcp 已有 **107 个 `@mcp.tool`**，覆盖 17 大业务域。底层已切换为
> U9C OpenAPI；标准动作由通用工具解析各 Service 的真实 Action。盲目按业务模块
> 逐个新建工具会大量重复。

## 核心认知：通用工具是 FormId 参数化的

下面这些工具**接收 FormId 参数**，单个就能服务任意单据的标准动作，**不要为每个模块再各建一个**：

| 标准动作 | 复用工具 |
|----------|----------|
| 保存 | `u9_save_bill` |
| 提交 | `u9_submit_bills` |
| 审核 | `u9_audit_bills` |
| 反审核 | `u9_unaudit_bills` |
| 查看 | `u9_view_bill` |
| 删除 | `u9_delete_bills` |
| 下推 | `u9_push_bill` |
| 单据查询 | `u9_query_bills` |
| 保存前校验 | `u9_validate_bill` |
| 保存并审核 | `u9_create_and_audit` |
| 下推并审核 | `u9_push_and_audit` |
| 撤销 | `u9_cancel_bills` |
| 作废 | `u9_void_bills` |
| 整单关闭 | `u9_close_bill` |
| 反关闭 | `u9_unclose_bill` |
| 禁用 | `u9_forbid_bills` |
| 反禁用 | `u9_enable_bills` |

> 例：采购订单保存 = `u9_save_bill(FormId="PUR_PurchaseOrder", ...)`，无需新建 `u9_save_purchase_order`。

## 标准动作通用工具（FormId 参数化）

以下 6 个工具无需为每个模块重复创建。U9C 没有跨 Service 的统一操作端点，
工具会读取本地 OpenAPI 目录中该 Service 的真实 Action 与中文摘要，再发起
`POST /webapi/{Service}/{Action}`：

| 工具 | U9C 动作解析方式 | 适用 |
|------|------------------|------|
| `u9_cancel_bills` | 解析 `CancelAssign` 等撤销/取消下达动作，或显式传 `operation` | 单据 + 基础资料 |
| `u9_void_bills` | 解析 `Cancel`（终止/作废），不同 Service 语义以摘要为准 | 单据 |
| `u9_close_bill` | 按摘要匹配“整单关闭/关闭单据”，回退 `Close` | 单据 |
| `u9_unclose_bill` | 按摘要匹配“整单反关闭/反关闭/打开”，回退 `Open` | 单据 |
| `u9_forbid_bills` | 按摘要匹配“挂起/禁用/冻结/停用”，回退 `Forbid` | 基础资料 |
| `u9_enable_bills` | 按摘要匹配“解除挂起/启用/反禁用”，回退 `Enable` | 基础资料 |

**关键约定**：
1. **端点统一为 `POST /webapi/{Service}/{Action}`**，没有通用的 `ExecuteOperation` + `opNumber` 请求格式。
2. **请求体**为 `OptDocRData[]`（如 `[{"ID": 100723, "Code": "CGDD000198"}]`），或该动作要求的 DTO。
3. **动作随 Service 变化**：先用 `u9_list_form_operations` 查询真实 Action；目标 Service 没有对应动作时工具返回明确错误，不猜测调用。
4. **命名陷阱**：`PurchaseOrder.Release` 是“挂起”、`Hold` 是“解除挂起”；`SO.CancelReleaseSO` 是“取消下达”，不是作废。
5. **标准动作覆盖现状**：保存/批量保存/提交/审核/反审核/删除/关闭/反关闭/撤销/作废/挂起/解除挂起/通用动作均有对应工具；报表由 `u9_query_report`（U9C `Report/GetReportPdfFile`，输出 PDF）覆盖。

## 专用工具（已存在，须扩展而非新建）

以下模块已有**专用**工具，新需求优先扩展它们（加参数/分支），不要并行再建同名逻辑的。
（全部带 `u9_` 前缀，与 `bin/kmcp tools` 输出、源码 `@mcp.tool(name=...)` 完全一致）

- 销售：`u9_query_sale_orders` / `u9_query_sale_quotations` / `u9_query_sales_outstock`（2026-08-07 新增，对应 ApiDoc 销售出库 SAL_OUTSTOCK；本环境客户字段 Key 为 `FCustomerID` 非 `FCustId`）/ `u9_query_delivery_notice`（发货通知单，FormId=SAL_DELIVERYNOTICE，默认字段含 FCustomerID.FName）
- 人人报销：`u9_query_expense_reimburse` / `u9_query_loan_balance`（后者 2026-08-07 新增，对应 ApiDoc「历史借款余额」FormId=ER_HistoricalLoanBalance；**注意目标账套若未启用该模块则查不到数据**）
- 采购：`u9_query_purchase_orders` / `u9_query_purchase_requisitions` / `u9_query_purchase_inquiry` / `u9_query_purchase_order_progress` / `u9_query_supplier_quotes`
- 库存/库存单据：`u9_query_inventory` / `u9_query_stock_bills` / `u9_query_stock_transfer_apply` / `u9_query_transfer_apply` / `u9_query_transfer_direct` / `u9_query_transfer_pending_detail` / `u9_push_stock_transfer` / `u9_query_misc_movement_detail` / `u9_query_stock_in`（采购入库单，FormId=STK_InStock，默认字段含 FSupplierId.FName）
- 生产：`u9_query_production_orders` / `u9_query_production_plan` / `u9_query_production_report` / `u9_query_production_stock_in` / `u9_query_production_pick_materials` / `u9_query_mrp_result` / `u9_save_production_order` / `u9_submit_production_orders` / `u9_audit_production_orders` / `u9_push_production_pick` / `u9_push_production_stock_in` / `u9_view_production_order`
- 成本：`u9_query_cost_adjustments` / `u9_query_cost_calculation` / `u9_query_cost_centers` / `u9_query_cost_items` / `u9_query_cost_trend` / `u9_query_finished_product_cost` / `u9_query_instant_cost_compare` / `u9_query_material_cost` / `u9_query_material_cost_usage` / `u9_query_material_target_cost` / `u9_query_product_standard_cost` / `u9_save_cost_adjustment`
- 资产：`u9_query_asset_card` / `u9_query_asset_depreciation` / `u9_query_asset_scrape` / `u9_query_asset_transfer` / `u9_query_fixed_asset` / `u9_save_asset`
- 其他：`u9_query_partners` / `u9_query_user` / `u9_query_role` / `u9_query_permission` / `u9_query_workflow_status` / `u9_query_approval_flow` / `u9_query_audit_log` / `u9_query_change_log` / `u9_query_operation_logs` / `u9_query_pending_approvals` / `u9_query_system_config` / `u9_query_number_rule` / `u9_query_sequence` / `u9_query_report` / `u9_query_data_backup` / `u9_query_quality_inspections` / `u9_create_lx_billing` / `u9_workflow_approve`
- 元数据/探查：`u9_get_fields` / `u9_get_bill_template` / `u9_discover_metadata_candidates` / `u9_discover_tables` / `u9_discover_columns` / `u9_describe_table` / `u9_list_forms` / `u9_refresh_metadata`

> ⚠️ **已知历史重复（勿处理）**：`u9_query_permission` 在源码中被注册了两次（启动有 WARNING，无害）。
> QA 回归时把它当作「既有重复」忽略，不要为「消除重复」而新增第三个或改动既有注册。

## 决策树（动手前必走）

```
目标：把 ApiDoc {领域→模块→操作} 集成进来
  │
  ├─ 操作 ∈ 标准单据动作（保存/提交/审核/反审核/查看/删除/下推/单据查询）？
  │     ├─ 是 → 查通用工具（见上表）是否已存在？
  │     │        ├─ 是 → REUSE（传 FormId），【禁止新建】
  │     │        └─ 否 → 先确认不是历史遗漏；一般不应出现
  │     └─ 否（专属动作，如 申请单退款 / 报表导出 / 暂存特殊逻辑）？
  │              ├─ 该模块已有专用 `u9_<动作>_<模块>` 工具？
  │              │     ├─ 是 → EXTEND 既有工具（加参数/分支），【禁止并行新建】
  │              │     └─ 否 → 仅在「需要二开字段/复杂拼包/通用工具服务不好」时
  │              │              新建专用工具，并在工具 docstring 注明 FormId 与为何不复用通用工具
  │
  └─ 任何新建/扩展后，跑 `bin/kmcp tools <模块关键字>` 复核无同名/同 FormId 的重复工具
```

## 落地手段

- **查重命令**：`python bin/kmcp tools <关键字>`（如 `python bin/kmcp tools purchase` / `python bin/kmcp tools save`）会扫描 `server.py` 的 `@mcp.tool` 名，列出已覆盖的工具，立刻判断是否重复。
- **统计**：`python bin/kmcp list-tools` 看总数变化（新增应是有理由的净增，而非批量重复）。
- **回归**：严过关回归时把「是否引入了与既有工具同 FormId/同语义的重复工具」列为检查项。

## 判重口诀

> 先查通用（FormId 参数化）→ 再查专用（模块已建）→ 都无且确需特殊处理，才新建，并写明为什么不复用。

> 💡 **查重搜索陷阱**：`bin/kmcp tools` 按**子串匹配**工具名。注册名带下划线（如 `u9_query_stock_in`），用 `stockin` 会**漏匹配**；搜「采购入库单」请用 `stock_in`（含下划线）。同理 `deliverynotice` 漏匹配，用 `delivery_notice`。
