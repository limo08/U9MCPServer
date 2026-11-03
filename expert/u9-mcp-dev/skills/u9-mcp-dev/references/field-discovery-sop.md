# 探字段标准操作流程（SOP）

> 适用：范探源（WebAPI 集成）。在写任何 `@mcp.tool` 之前，必须先把目标单据的字段摸清楚，否则会踩二开坑（见 `ercustom-pitfalls.md`）。

## 步骤

### Step 1：确定 FormId 与单据类型
- ApiDoc 每个「业务领域 → 模块 → 操作」对应一个用友单据（FormId，如 `SAL_SaleOrder` / `PUR_PurchaseOrder` / `SAL_Quotation`）。
- 若不确定 FormId，先用 `u9_discover_metadata_candidates` 模糊候选。

### Step 2：u9_get_fields 探字段
调用 `u9_get_fields`（传 FormId）获取该单据全部字段 Key 与显示名、是否必填、是否在表体。

重点确认四类核心字段：
- **主键**：`FID`
- **组织 / 客户 / 供应商**：如 `FSaleOrgId`、`FCustId` / `FCUSTID`、`FSupplierId`
- **日期 / 单据编号**：`FDate`、`FBillNo`
- **金额 / 表体集合**：如 `FEntity`、`FQUOTATIONENTRY`

### Step 3：区分「标准字段」与「二开字段」
- 标准字段在 BOS 元数据里都查得到；若 `u9_get_fields` 报「元数据中标识为 XXX 的字段不存在」，说明这是**二开定制字段或标准字段被改名**——立即查阅 `ercustom-pitfalls.md`。
- 典型陷阱：`SAL_SaleOrder` 是二开版，标准 `FSalesManId` / `FTotalAmount` **不存在**；客户字段在本环境是**全大写 `FCUSTID`**。

### Step 4：产出字段/操作映射表
范探源回传主理人的标准产出格式：

| ApiDoc 操作 | 用友 WebAPI 动作 | FormId | 必填字段(Key) | 样例数据包 | 二开注意 |
|-------------|------------------|--------|---------------|------------|----------|
| 销售订单.保存 | `Save` | `SAL_SaleOrder` | `FSaleOrgId`,`FCUSTID` | `{...}` | 二开版，无 `FSalesManId` |

### Step 5：本地联调验证
连真实 U9C 环境（配置 `U9_API_SERVER_URL` / OAuth2 参数），用 `validate_bill` 做保存前校验，确认必填与字段别名无误后再交付寇豆码实现工具。
