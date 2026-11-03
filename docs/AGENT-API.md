# 用友 U9C MCP Server — Agent 接口调用文档

> 面向 AI Agent（Claude、Cursor、WorkBuddy 等）。底层协议为 **U9C OpenAPI**
> （`https://openapi.yyu9c.com/doc.html#/home`），由 MCPServer（mcp 2.x）暴露
> **107 个工具 / 17 个业务域**。本文中的 `form_id` 会由服务自动解析为 U9C
> `Service` 与实体全名（如 `PUR_PurchaseOrder` → `PurchaseOrder` →
> `UFIDA.U9.PM.PO.PurchaseOrder`）。

---

## 1. 环境配置

### 1.1 必需变量（OAuth2，二选一）

| 变量 | 说明 | 示例 |
|------|------|------|
| `U9_API_SERVER_URL` | U9C 根地址，**不要带 `/webapi`** | `https://u9.example.com:8080` |
| `U9_API_CLIENT_ID` | OAuth2 client id | `your-client-id` |
| `U9_API_CLIENT_SECRET` | OAuth2 client secret | `your-client-secret` |
| `U9_API_ENT_CODE` | 企业账套编码（entCode） | `001` |
| `U9_API_ORG_CODE` | 组织编码（orgCode） | `01` |
| `U9_API_USERNAME` | 用户编码（userCode） | `demo` |

或直接注入已签发 token：

| 变量 | 说明 |
|------|------|
| `U9_API_SERVER_URL` | U9C 根地址 |
| `U9_API_TOKEN` | 已有 token；静态 token 失效时若同时配置 OAuth2 凭证会自动重登 |

### 1.2 可选变量

| 变量 | 说明 |
|------|------|
| `U9_API_LANGUAGE` | 语言，默认 `zh-CN` |
| `U9_API_LOGIN_TYPE` | OAuth2 登录类型，默认 `1` |
| `U9_API_LOGIN_DATE` | 登录上下文日期，`yyyy-MM-dd` |
| `U9_API_ENTITY_MAP` | form_id → 实体全名覆盖映射（JSON） |
| `U9_API_ENTITY_MAP_FILE` | 上述映射的 JSON 文件路径 |
| `U9_ATTACHMENT_TIMEOUT` | 附件传输读超时（秒，默认 120；连接超时 30） |
| `MCP_SQLSERVER_*` | SQL Server 只读探查配置（可选） |
| `U9_SCHEMA_FILE` | 离线数据字典路径（可选） |

### 1.3 认证流程

```http
GET /webapi/OAuth2/AuthLogin?clientid=...&clientsecret=...&entCode=...&userCode=...&orgCode=...
```

响应 `Data` 即 token；此后所有业务请求携带：

```http
token: <token>
```

Token 过期（HTTP 401 / `ResCode=401` 或 `-10001` / 未登录提示）时自动重登并重试一次。
写操作只在确认是认证失败时重试，业务失败不会重复提交。

---

## 2. 协议核心

### 2.1 通用响应

```json
{
  "ResCode": 0,
  "Success": true,
  "ResMsg": "",
  "Data": null,
  "Exception": ""
}
```

- `Success=true` 且 `ResCode=0` 才算成功；
- 批量接口的 `Data[]` 可能逐条带 `IsSucess` / `IsSuccess`、`ErrorMsg`、`ID`、`Code`；
- MCP 工具会把 U9C 响应归一化为统一 JSON 字符串，失败时含 `errors` / `next_action` 等提示。

### 2.2 查询：`CommonEntity/Query`

```http
POST /webapi/CommonEntity/Query
```

```json
{
  "PageSize": 20,
  "PageIndex": 1,
  "Orders": "BusinessDate desc, DocNo",
  "Filters": [
    {"Field": "DocStatus", "Operator": "eq", "Value": 2,
     "ValueIsField": false, "Logic": "and"}
  ],
  "EntityFullName": "UFIDA.U9.PM.PO.PurchaseOrder",
  "ReturnFields": ["ID", "DocNo", "BusinessDate", "Supplier.Code"]
}
```

支持的过滤运算符：`eq` / `ne` / `lt` / `gt` / `le` / `ge` / `in` / `nin` / `like`。
Agent 可以继续使用旧 `F*` 条件（如 `FDocumentStatus='C' and FDate>='2026-01-01'`），
MCP 会翻译为 U9C 字段与 `Criterion` 结构（`DocStatus=2`）；新调用建议直接使用 U9C 字段名。

### 2.3 标准动作：`/webapi/{Service}/{Action}`

提交、审核、删除、关闭、挂起等动作的请求体为 `OptDocRData[]`：

```json
[{"ID": 100723, "Code": "CGDD000198"}]
```

工具会按单据类型解析真实 Action。**U9C 动作并不完全统一**，例如：

| 业务意图 | PurchaseOrder | SO | 说明 |
|----------|---------------|----|------|
| 提交 | `Submit` | `Submit` | |
| 审核 | `Approve` | `Approve` | |
| 反审核 | `UnApprove` | `UnApprove` | |
| 删除 | `Delete` | `Delete` | |
| 关闭 | `Close` | `Close` | |
| 反关闭 | `Open` | `Open` | |
| 作废/终止 | `Cancel` | — | PO 的 `Cancel` 是“终止” |
| 挂起/禁用 | `Release` | — | **U9C PurchaseOrder 的 Release 是“挂起”** |
| 解除挂起/反禁用 | `Hold` | — | **Hold 是“解除挂起”** |
| 撤销下达 | — | `CancelReleaseSO` | |
| 修改 | — | `Modify` | PurchaseOrder 没有 Modify |

MCP 会读取 OpenAPI 中动作的 `summary` 语义，而不是硬编码动作名；
若目标 Service 没有对应动作，会返回明确的“不支持动作”错误，不会猜测调用。

### 2.4 保存

| 操作 | 工具 | 请求 |
|------|------|------|
| 新建 | `u9_save_bill` | `POST /webapi/{Service}/Create`，body 为 `[DTO]` |
| 修改 | `u9_save_bill`（`ID`/`FID` 非 0） | `POST /webapi/{Service}/Modify`（若服务提供） |
| 批量保存 | `u9_batch_save_bills` | 自动拆成 `Create` 与 `Modify` 两组，分别调用后合并 `Data` |
| 保存并审核 | `u9_create_and_audit` | save → submit → audit |
| 通用动作 | `u9_execute_operation` | 指定 U9C Action 或标准动作别名 |

> PurchaseOrder 只提供 `Create`，没有 `Modify`；修改已有采购订单会明确报错。
> 请先在 U9C 界面确认该单据是否允许 API 修改，或使用对应变更单接口。

---

## 3. 常用 form_id → Service

| form_id | U9C Service | 实体全名 |
|---------|-------------|----------|
| `PUR_PurchaseOrder` | `PurchaseOrder` | `UFIDA.U9.PM.PO.PurchaseOrder` |
| `PUR_Requisition` | `PR` | `UFIDA.U9.PM.PR.PR` |
| `PUR_ReceiveBill` / `STK_InStock` | `Receivement` | `UFIDA.U9.PM.Rcv.Receivement` |
| `SAL_SaleOrder` | `SO` | `UFIDA.U9.SM.SO.SO` |
| `SAL_OUTSTOCK` | `Ship` | `UFIDA.U9.SM.Ship.Ship` |
| `SAL_Quotation` | `Quot` | `UFIDA.U9.SM.Quot.Quot` |
| `STK_Inventory` | `ItemQty` | `UFIDA.U9.CBO.SCM.Item.ItemQty` |
| `PRD_MO` / `SUB_SubReqOrder` | `MODoc` | `UFIDA.U9.MO.MODoc.MODoc` |
| `PRD_PickMtrl` | `IssueDoc` | `UFIDA.U9.MO.IssueDoc.IssueDoc` |
| `PRD_Instock` | `RcvRptDoc` | `UFIDA.U9.MO.RcvRptDoc.RcvRptDoc` |
| `QIS_InspectBill` | `QCDoc` | `UFIDA.U9.QC.QCDoc.QCDoc` |
| `AP_Payable` | `APBill` | `UFIDA.U9.AP.APBill.APBill` |
| `AR_Receivable` | `ARBill` | `UFIDA.U9.AR.ARBill.ARBill` |
| `BD_Material` | `ItemMaster` | `UFIDA.U9.CBO.SCM.Item.ItemMaster` |
| `BD_Customer` | `Customer` | `UFIDA.U9.CBO.SCM.Customer.Customer` |
| `BD_Supplier` | `Supplier` | `UFIDA.U9.CBO.SCM.Supplier.Supplier` |
| `BD_User` | `UserInfo` | `UFIDA.U9.CBO.Sys.UserInfo` |

完整目录来自打包的 U9C OpenAPI 规范（628 paths / 157 Services / 838 schemas），
可用 `u9_list_forms` 搜索，或直接传 U9C Service 名称。

---

## 4. 字段映射与保存示例

MCP 保留旧工具参数名（`FBillNo`、`FSupplierId`、`FPOOrderEntry` 等），内部转换为
U9C DTO。新调用优先使用 U9C 字段名。

### 4.1 采购订单新建

```json
{
  "params": {
    "form_id": "PUR_PurchaseOrder",
    "model": {
      "FBillNo": "PO-2026-001",
      "FDate": "2026-11-02",
      "FSupplierId": {"FNumber": "S001"},
      "FPOOrderEntry": [
        {"FMaterialId": {"FNumber": "MAT001"}, "FQty": 100, "FDeliveryDate": "2026-11-10"}
      ]
    }
  }
}
```

实际发送到 U9C 的 DTO：

```json
{
  "DocNo": "PO-2026-001",
  "BusinessDate": "2026-11-02",
  "Supplier": {"Code": "S001"},
  "POLineDTOList": [
    {"ItemInfo": {"Code": "MAT001"}, "ReqQtyTU": 100, "DeliveryDate": "2026-11-10"}
  ]
}
```

- `FID=0` / `FID=None` 不会发送给 `Create`；
- 分录也可直接使用 U9C 键名 `POLineDTOList` / `SOLineDTOList`；
- 无法映射的字段会返回 `unknown_fields`，不会静默丢弃；
- 供应商/物料等引用支持旧写法 `"FSupplierId": "S001"`，会转成 `{"Code":"S001"}`。

### 4.2 批量保存

`u9_batch_save_bills` 的 `models` 是数组；每个元素 `FID`/`ID` 为 0/空表示新增，否则修改。
混合批次会分别调用 `Create` 与 `Modify`，再把 `Data[]` 合并返回。

---

## 5. 工具速查

### 5.1 通用单据

| 工具 | 用途 |
|------|------|
| `u9_query_bills` | 任意 form_id 通用查询（分页/过滤/排序） |
| `u9_view_bill` | 按单据 ID 查看完整数据（`CommonEntity/Query`） |
| `u9_save_bill` / `u9_batch_save_bills` | 新建/修改/批量保存 |
| `u9_validate_bill` | 保存前字段校验与自动纠错 |
| `u9_submit_bills` / `u9_audit_bills` / `u9_unaudit_bills` | 提交/审核/反审核 |
| `u9_delete_bills` | 删除 |
| `u9_close_bill` / `u9_unclose_bill` | 关闭/反关闭 |
| `u9_void_bills` / `u9_unvoid_bills` | 作废/反作废（按 U9C 可用动作执行，不保证所有单据都有） |
| `u9_forbid_bills` / `u9_enable_bills` | 挂起/禁用、解除挂起/反禁用（按 summary 解析） |
| `u9_cancel_bills` | 撤销下达（目前明确支持 `SO/CancelReleaseSO`） |
| `u9_execute_operation` | 指定 U9C Action / 操作别名执行 |
| `u9_push_bill` | 下推；U9C 没有通用下推，当前仅支持 `PurchaseOrder/POCreateSO → SO` |
| `u9_create_and_audit` / `u9_push_and_audit` | 复合链路 |

### 5.2 领域查询

| 业务域 | 工具 |
|--------|------|
| 采购 | `u9_query_purchase_orders`、`u9_query_purchase_requisitions`、`u9_query_purchase_inquiry`、`u9_query_purchase_order_progress`、`u9_query_supplier_quotes` |
| 销售 | `u9_query_sale_orders`、`u9_query_sale_quotations`、`u9_query_sales_outstock`、`u9_query_delivery_notice` |
| 库存 | `u9_query_inventory`、`u9_query_stock_bills`、`u9_query_stock_in`、`u9_query_transfer_direct`、`u9_query_transfer_apply` 等 |
| 生产 | `u9_query_production_orders`、`u9_query_mrp_result`、`u9_query_production_pick_materials`、`u9_query_production_report` 等 |
| 成本/资产 | `u9_query_material_cost`、`u9_query_cost_calculation`、`u9_query_fixed_asset`、`u9_query_asset_*` 等 |
| 财务 | `u9_query_receipts`、`u9_query_report` |
| 基础资料/权限 | `u9_query_materials`、`u9_query_partners`、`u9_query_user`、`u9_query_role`、`u9_query_permission` |
| 元数据/探查 | `u9_list_forms`、`u9_get_fields`、`u9_list_form_operations`、`u9_get_bill_template`、`u9_refresh_metadata`、`u9_discover_*`、`u9_query_table`、`u9_execute_sql` |
| 附件 | `u9_upload_attachment`、`u9_download_attachment` |

> 部分业务域（生产计划、成本、资产、审计、工作流等）在 U9C OpenAPI 中没有对应
> Service/实体。工具会返回明确的“无 U9C Service/实体”错误，而不是退回旧版接口。
> 遇到该错误时，请改用 SQL 只读查询（`u9_query_table` / `u9_execute_sql`）或 U9C 界面。

---

## 6. 附件（U9C AttachmentFile）

### 6.1 上传

`POST /webapi/AttachmentFile/AttachmentFileUpload`

```json
{
  "EntityID": "100723",
  "EntityType": "UFIDA.U9.PM.PO.PurchaseOrder",
  "FlowID": "optional-flow-id",
  "files": [
    {"FileName": "合同.pdf", "FileSize": 12345, "FileContent": "JVBERi0xLjQK..."}
  ]
}
```

工具参数：

```json
{
  "params": {
    "form_id": "PUR_PurchaseOrder",
    "bill_id": "100723",
    "bill_no": "CGDD000198",
    "file_name": "合同.pdf",
    "send_byte": "JVBERi0xLjQK..."
  }
}
```

返回 `Data: [FileResult]`，`Handler` 是后续下载标识（工具同时用 `file_id` 兼容旧调用）。

**限制**：U9C 没有分块/续传协议；`is_last` 必须为 `true`，`file_id` / `entry_key` /
`entry_id` 必须为空；单文件最大 4 MiB（MCP 本地上限）；只支持表头附件。
上传不是幂等操作，网络中断返回 `outcome_unknown=true` 时先在 U9C 核对，不要直接重传。

### 6.2 下载

`POST /webapi/AttachmentFile/AttachmentFileDownload?handler=<Handler>`

返回 `FileResult`（`Handler` / `FileName` / `FileSize` / `FileUrl`）。MCP 若发现只有
`FileUrl`，会再取回文件并返回 Base64：

```json
{
  "params": {"handler": "23d8a447a9254a788f2d12a499898755"}
}
```

`start_index` 必须为 0；U9C 不支持分块下载。兼容旧字段 `file_id`。

`AttachmentFileDownloadByDocID?docid=...` 可按单据列出附件（当前未暴露为独立工具）。

---

## 7. 报表

`u9_query_report` 调用：

```http
POST /webapi/Report/GetReportPdfFile
```

```json
{"ReportCaseID": "报表用例ID"}
```

或：

```json
{"SubscirbeReportName": "订阅报表名称"}
```

返回：

```json
{"FileName": "balance.pdf", "FileContentBase64": "JVBERi0..."}
```

U9C 该接口生成的是 **PDF 文件**，不是网关结构化行数据。Agent 应把 Base64 保存为
用户指定文件，或告知调用方解码；不要按旧版 `GetSysReportData` 的 `Rows/FieldKeys`
结构解析。

---

## 8. 元数据

`u9_list_forms` / `u9_get_fields` / `u9_get_bill_template` / `u9_refresh_metadata`
现在使用**打包的 U9C OpenAPI 规范**（`src/u9_mcp/data/u9c_openapi.json`）离线生成元数据：

- 字段来自 DTO `properties`；
- 操作来自 `/webapi/{Service}/{Action}` 的 `summary`；
- 返回 `service` / `entity` / `fields` / `entries` / `operations`；
- 不再调用外部元数据接口；
- 元数据带内存/磁盘缓存，`u9_refresh_metadata` 可强制刷新。

`u9_list_form_operations` 返回真实 U9C Action 及中文摘要，例如 PurchaseOrder 的
`Release`（挂起）与 `Hold`（解除挂起）。

---

## 9. SQL Server 只读探查

`MCP_SQLSERVER_*` 配置后可用：

| 工具 | 用途 |
|------|------|
| `u9_discover_tables` | 搜索表名 |
| `u9_discover_columns` | 搜索字段名 |
| `u9_describe_table` | 查看表结构 |
| `u9_discover_metadata_candidates` | form_id → 候选表名 |
| `u9_query_table` | 只读查询表数据（字段白名单 + 参数化 + 分页） |
| `u9_execute_sql` | 执行单条只读 SQL（SELECT/WITH；拦截 DML/DDL/多语句） |

**数据库直连始终只读**。不要尝试通过 SQL 写入 U9 业务表：U9 的单据编号、审核流、
业务规则必须由 U9C 服务端执行，绕过会导致数据不一致。写操作请走 OpenAPI。

未配置 SQL Server 时，结构探查回退到 `U9_SCHEMA_FILE` 指向的数据字典。

---

## 10. 错误与恢复

| 返回 | 含义 | 处理 |
|------|------|------|
| `success:false` + `errors[].message` | U9C 业务失败 | 按消息修正参数/权限，不自动重试 |
| `outcome_unknown:true` | 写操作网络中断，结果未知 | 先查询单据/附件确认，勿盲目重传 |
| `U9C OpenAPI 没有通用端点` | 调用了非 U9C 端点 | 改用对应 Service/Action |
| `没有对应的 U9C Service` | form_id 无法解析 | 用 `u9_list_forms` 搜索，或传 U9C Service |
| `没有 Modify` | 该 Service 只支持新增 | 新建，或改用变更单/界面处理 |
| `不支持动作` | 该 Service 无此动作 | 查询 `u9_list_form_operations` 或 OpenAPI |
| `无法映射到 U9C ... DTO` | 字段名错误 | 用 `u9_get_fields` 查 U9C 字段名 |

常见排查：

1. `--check` 确认 token 与数据库配置；
2. `U9_API_SERVER_URL` 不要带 `/webapi`；
3. `entCode` / `orgCode` / `userCode` 必须是 U9C 中的编码，不是显示名称；
4. 权限不足时检查 U9C 用户角色、组织与数据权限。

---

## 11. 完整调用流程示例

### 查询已审核采购订单

```json
{
  "tool": "u9_query_purchase_orders",
  "params": {
    "filter_string": "DocStatus=2 and BusinessDate>='2026-01-01'",
    "field_keys": "ID,DocNo,Supplier.Code,BusinessDate,TotalMnyTC",
    "order_string": "BusinessDate desc",
    "limit": 20
  }
}
```

### 新建并审核采购订单

1. `u9_get_fields({form_id:"PUR_PurchaseOrder"})` 确认字段；
2. `u9_save_bill` 传 `model`（见 4.1）；
3. 若返回 `ID`，调用 `u9_submit_bills`；
4. 再调用 `u9_audit_bills`；
5. 或直接使用 `u9_create_and_audit` 完成 save → submit → audit。

每一步都以 U9C 返回的 `Success` / `Data[].IsSucess` 为准；失败时读取 `errors[].message`。
