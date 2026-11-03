# 用友 U9C OpenAPI 接口说明（本项目对接版）

> 数据来源：<https://openapi.yyu9c.com/doc.html#/home>
> 本地规范快照：`src/u9_mcp/data/u9c_openapi.json`（OpenAPI 3.0.1，`title=U9C OPENAPI`，`version=v1`）。
>
> 规范规模：**628 个 Path、157 个 Service/Tag、838 个 Schema**。
> 本文只描述本项目实际使用的协议形状；具体业务字段以本地规范为准。

---

## 1. 协议总览

U9C OpenAPI 采用以下协议形状：

| 项目 | U9C OpenAPI（本项目） |
|------|------------------------|
| 端点 | `/webapi/{Service}/{Action}` |
| 认证 | OAuth2 + `token` 请求头 |
| 请求体 | 直接传 DTO 或 DTO 数组 |
| 查询 | `POST /webapi/CommonEntity/Query` |
| 标准动作 | 每个 Service 自己的 `/Submit`、`/Approve` 等 |
| 响应 | `ResCode/Success/ResMsg/Data/Exception` |
| 附件 | 一次传完整 Base64，不支持分块 |

统一响应：

```json
{
  "ResCode": 0,
  "Success": true,
  "ResMsg": "",
  "Data": null,
  "Exception": ""
}
```

判断成功：`Success == true && ResCode == 0`。

---

## 2. 认证

### 2.1 AuthLogin（主流程）

```http
GET /webapi/OAuth2/AuthLogin
```

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| `clientid` | query | 是 | OAuth2 应用 ID |
| `clientsecret` | query | 是 | OAuth2 应用密钥 |
| `entCode` | query | 是 | 企业账套编码 |
| `userCode` | query | 是 | 用户编码 |
| `orgCode` | query | 是 | 组织编码 |
| `loginType` | query | 否 | 登录类型 |
| `loginDate` | query | 否 | 上下文日期 |
| `language` | query | 否 | 语言，如 `zh-CN` |

成功响应 `Data` 为 token 字符串（也兼容 `Data.Token` / `AccessToken`）：

```json
{"ResCode": 0, "Success": true, "Data": "eyJ..."}
```

### 2.2 兼容流程

部分旧部署只暴露：

1. `GET /webapi/OAuth2/GetAuthorizeCode?clientid=...&clientsecret=...`
2. `GET /webapi/OAuth2/Login?entCode=...&userCode=...&orgCode=...&code=...`

本项目在 `AuthLogin` 失败时会尝试该流程。其他认证端点：
`RefreshToken`、`DestroyToken`、`GetSalt`、`SSOLogin`。

### 2.3 业务请求

所有业务请求带：

```http
token: <token>
Accept: application/json
```

token 过期时自动重登并重试一次。写操作只在确认认证失败时重试。

---

## 3. 公共查询

### 3.1 端点

```http
POST /webapi/CommonEntity/Query
Content-Type: application/json
token: <token>
```

请求体 Schema：`UFSoft.UBF.MVC.Common.ApiComParms`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `PageSize` | int | 是 | 每页数量 |
| `PageIndex` | int | 是 | 页码（从 1 开始） |
| `Orders` | string | 否 | 如 `BusinessDate desc, DocNo` |
| `Filters` | array | 否 | 条件数组 |
| `EntityFullName` | string | 是 | 实体全名 |
| `ReturnFields` | array | 是 | 返回字段 |

示例：

```json
{
  "PageSize": 20,
  "PageIndex": 1,
  "Orders": "BusinessDate desc",
  "Filters": [
    {"Field": "DocStatus", "Operator": "eq", "Value": 2,
     "ValueIsField": false, "Logic": "and"}
  ],
  "EntityFullName": "UFIDA.U9.PM.PO.PurchaseOrder",
  "ReturnFields": ["ID", "DocNo", "BusinessDate", "Supplier.Code"]
}
```

> `DocStatus` 是数字枚举：`0` 开立、`1` 审核中、`2` 已审核、`3` 关闭。
> 旧写法 `FDocumentStatus='C'` 会被翻译为 `DocStatus=2`。

### 3.2 过滤运算符

| 运算符 | 含义 |
|--------|------|
| `eq` | 等于 |
| `ne` | 不等于 |
| `lt` / `le` | 小于 / 小于等于 |
| `gt` / `ge` | 大于 / 大于等于 |
| `in` / `nin` | 包含 / 不包含 |
| `like` | 模糊匹配 |

字段可以带路径：`Supplier.Code`、`POLines.ReqQtyTU`。

### 3.3 返回形状

`Data` 可能是：

```json
{"RecordList": [...], "RecordCount": 100}
```

也可能是 `Rows` / `Records` / `Items` / `List` / 直接数组。本项目
`extract_query_result()` 会统一为 `{rows, total}`；单对象 `Data` 也按一行处理。

---

## 4. 标准动作

### 4.1 路由

```http
POST /webapi/{Service}/{Action}
```

请求体通常为 `OptDocRData[]`：

```json
[{"ID": 100723, "Code": "CGDD000198"}]
```

`OptDocRData` 字段（`UFIDA.U9.ISV.PUB.RestSV.Model.Pub.OptDocRData`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ID` | int64 | 单据/档案 ID |
| `Code` | string | 单据编号 / 档案编码 |
| `OtherID` | string | 第三方唯一标识 |
| `HoldOrReleaseReasonCode` | string | 挂起/解除原因 |
| `CancelResean` | string | 终止原因 |

### 4.2 不是所有 Service 都有相同动作

`/webapi/{Service}/{Action}` 的 Action 由该 Service 实际提供，不存在统一
“ExecuteOperation + opNumber”。本项目读取 OpenAPI 操作列表后解析。

常见 Service 动作（以本地规范为准）：

| Service | 动作 |
|---------|------|
| `PurchaseOrder` | `Create`、`CreatePurchaseOrderBySrc`、`Delete`、`Submit`、`Approve`、`UnApprove`、`Cancel`、`Hold`、`Release`、`Open`、`Close`、`OpenLine`、`CloseLine`、`POCreateSO` |
| `SO` | `Create`、`Modify`、`Delete`、`Submit`、`Approve`、`UnApprove`、`Close`、`Open`、`CloseLine`、`OpenLine`、`ReleaseSO`、`CancelReleaseSO` |
| `ItemMaster` | `Create`、`CreateByAttributes`、`CreateByAutoCode`、`Modify`、`Delete`、`Query` |
| `Customer` | `Create`、`Modify`、`Delete`、`Submit`、`Query` |
| `Supplier` | `Create`、`NewCreate`、`CreateByScheme`、`Modify`、`DelSup`、`QrySupplier`、`QueryPage` |
| `Receivement` | `CreateReceivement`、`CreateRcvBySrcPO`、`CreateRcvBySrcASN`、`Submit`、`Approve`、`UnApprove`、`HoldLine`、`ReleaseLine`、`Delete` 等 |
| `Ship` | `Create`、`CreateBySrcDoc`、`Submit`、`Approve`、`SubmitAndApprove`、`UnApproved`、`Delete`、`Query` |
| `PR` | `Create`、`Approved`、`UnApproved`、`Submit`、`Delete`、`Open`、`Close`、`OpenLine`、`CloseLine` |
| `PC` | `Create`、`Submit`、`Approved`、`UnApproved`、`Delete`、`CreateBIP`、`DeleteBIP`（采购合同） |
| `MODoc` | `Create`、`StartMo`、`CompleteMo`、`ApproveMo`、`CancelMo`、`DeleteMO`、`Query` 等 |
| `QCDoc` | `CreateOtherQC`、`QualityCheck`、`CalcQCResult`、`Complete`、`Approve`、`UnApprove`、`PullCreate`、`Rtn` |
| `ARBill` / `APBill` | `Create`、`CreateBySrc`、`Submit`、`Approve`、`UnApprove`、`Delete` |

### 4.3 命名陷阱

- `PurchaseOrder` 的 **`Release` = 挂起**，**`Hold` = 解除挂起**（与英文直觉相反）。
- `SO` 的 `CancelReleaseSO` = 取消下达，不是作废。
- `PurchaseOrder` 没有 `Modify`；修改采购订单不能调用 `Modify`。
- `SO` 没有 `Cancel`；作废销售订单需查该单据类型是否有其他终止接口。
- 行级动作带 `Line` 后缀（如 `CloseLine`），请求体 DTO 与整单动作不同。

本项目 `resolve_action()` 会用 `summary` 语义修正挂起/解除挂起，并在动作不存在时
返回明确错误，不猜测。

---

## 5. 保存与 DTO

### 5.1 Create / Modify

```http
POST /webapi/{Service}/Create
POST /webapi/{Service}/Modify
```

请求体为 DTO 数组：

```json
[
  {
    "DocNo": "PO-2026-001",
    "BusinessDate": "2026-11-02",
    "Supplier": {"Code": "S001"},
    "POLineDTOList": [
      {"ItemInfo": {"Code": "MAT001"}, "ReqQtyTU": 100}
    ]
  }
]
```

- 新建时不要传 `ID=0`（本项目会移除）；
- 修改时 `ID` 或 `Code` 必须存在；
- 分录字段放在 Service 对应的 DTO 数组里，如 `POLineDTOList`、`SOLineDTOList`；
- 基础资料字段名不一定与单据一致，例如 `Supplier` 使用 `m_code` / `m_iD`。

### 5.2 批量保存

U9C 没有通用 `BatchSave` 端点。本项目把批量模型拆成：

1. `ID/FID` 为空或 0 → `Create` 数组；
2. 其他 → `Modify` 数组；
3. 分别调用后合并 `Data[]`。

---

## 6. 附件

### 6.1 上传

```http
POST /webapi/AttachmentFile/AttachmentFileUpload
```

```json
{
  "EntityID": "100723",
  "EntityType": "UFIDA.U9.PM.PO.PurchaseOrder",
  "FlowID": "optional",
  "files": [
    {"FileName": "合同.pdf", "FileSize": 12345, "FileContent": "JVBERi0..."}
  ]
}
```

`EntityID` / `EntityType` 必填；`files[]` 每项 `FileName` / `FileSize` / `FileContent`。
`FileContent` 是标准 Base64，无分块协议。

返回 `ApiResult<List<FileResult>>`：

```json
{
  "ResCode": 0,
  "Success": true,
  "Data": [
    {"IsSuccess": true, "Handler": "h-1", "FileName": "合同.pdf",
     "FileSize": 12345, "FileUrl": "https://..."}
  ]
}
```

### 6.2 下载

```http
POST /webapi/AttachmentFile/AttachmentFileDownload?handler=<Handler>
```

返回 `FileResult`。若 `FileContent` 为空，需要再按 `FileUrl` 取文件。
`start_index`（断点）不被 U9C 支持。

### 6.3 其他附件接口

| 端点 | 说明 |
|------|------|
| `AttachmentFile/AttachmentFileDownloadByDocID?docid=...` | 按单据列出附件 |
| `AttachmentFile/AttachmentFileDelete` | 删除附件 |
| `AttachmentFile/AttachmentFileDeleteByDocID` | 按单据删除附件 |

---

## 7. 报表

```http
POST /webapi/Report/GetReportPdfFile
```

请求 `GetReportPdfFileReq`：

```json
{"ReportCaseID": "..."}
```

或：

```json
{"SubscirbeReportName": "..."}
```

响应 `Data`：

```json
{"FileName": "report.pdf", "FileContentBase64": "JVBERi0..."}
```

注意：这生成的是 PDF 文件，不是结构化行数据；
没有“报表 formId + FieldKeys + Model 过滤”的协议。

---

## 8. 元数据与本项目实现

本项目不请求远程元数据接口，而是从打包规范离线生成：

| 模块 | 作用 |
|------|------|
| `config/u9c_catalog.py` | 加载 OpenAPI 规范、form_id → Service/Entity、字段/动作索引 |
| `services/u9c_client.py` | OAuth2、`/webapi/{Service}/{Action}`、公共查询、标准动作 |
| `services/u9c_mapping.py` | 旧 F* 字段/过滤/模型 → U9C 字段与 DTO |
| `services/client.py` | 保留旧工具签名，路由到 U9C 实现 |
| `data/u9c_openapi.json` | 本地规范快照 |

`u9_list_forms` / `u9_get_fields` / `u9_get_bill_template` / `u9_list_form_operations`
都读取该目录，不依赖 U9 租户或外部元数据服务。

---

## 9. 本项目明确不支持的功能

以下能力在 U9C OpenAPI 中**没有对应端点**，工具会返回明确错误或降级：

| 功能 | 现状 |
|------|------|
| 旧版通用查询接口 | 已移除；改用 `CommonEntity/Query` 与离线目录 |
| 旧版批量保存接口 | 改为 Create/Modify 分组 |
| 通用下推 `Push` | 仅支持 `PurchaseOrder/POCreateSO → SO` |
| 通用 `ExecuteOperation` + `opNumber` | 改为每个 Service 的真实 Action |
| 反作废 / 整单反关闭 / 归档 / 冻结等专属动作 | 仅当目标 Service 提供同名/近义 Action 时可用 |
| 分块附件 / 分录附件 | U9C 附件接口不支持 |
| 旧报表 `GetSysReportData` | 改为 `Report/GetReportPdfFile`（PDF） |
| MRP 结果 / 生产计划 / 生产汇报查询 | U9C 只有 `PlanOrder/Create`、`WorkCenterOperationRpt/Create` 等写接口，没有对应查询 Service/实体 |
| 采购询价 / 供应商报价 / 比价 | U9C 规范未开放对应 Service/实体 |
| 杂项出入库明细 / 调出未调入明细 | U9C 有 `MiscRcvTrans`、`MiscShip`、`TransferOut`、`TransferIn` 写接口，但没有明细查询实体 |
| 角色/权限/编码规则/系统配置写入 | 若无 U9C Service，返回明确不支持 |
| 成本核算 / 资产评估折旧调拨 / 审计日志 / 上机日志 / 数据备份 | U9C 规范中没有对应 Service；工具返回明确错误，只读统计请用数据库查询 |

数据库直连（`u9_query_table` / `u9_execute_sql`）仍然只读，不能用来绕过上述限制写业务表。

---

## 10. 自检

```bash
u9-mcp --check
./start.sh check
```

检查项：

1. `U9_API_SERVER_URL` 可访问；
2. OAuth2 五项齐全，或 `U9_API_TOKEN` 非空；
3. token 获取成功；
4. 可选：SQL Server 只读连接成功。

接口根路径由程序拼接为 `/webapi/...`，配置中不要重复写 `/webapi`。
