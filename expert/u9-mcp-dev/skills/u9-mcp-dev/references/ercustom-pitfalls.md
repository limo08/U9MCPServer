# 本环境二开单据坑（必读）

> 适用：范探源、寇豆码。以下坑均已在测试 U9C 环境实测，集成 / 写工具前务必核对。

## 1. SAL_SaleOrder（销售订单）二开版
- **标准字段 `FSalesManId`（业务员）、`FTotalAmount`（金额）不存在**——直接查会报 WebAPI ErrorCode 500「元数据中标识为 XXX 的字段不存在」。
- 安全核心字段：`FID, FBillNo, FDate, FDocumentStatus, FCustId.FName, FCustId.FNumber` 可用。
- 集成销售订单相关查询时，绕过业务员/金额字段，或改用其他可查字段。

## 2. 客户字段全大写 `FCUSTID`
- 本环境销售报价单等单据的**客户字段 Key 是全大写 `FCUSTID`**（非标准 `FCustId`）。
- **MCP 代码坑（已修复但需警惕）**：旧版 `validate_and_fix` → `find_similar_field` 模糊匹配过激，会把 `FCustId` 静默错改成 `FCustLocId`（客户地点）。修复后大小写不敏感精确匹配优先 + 保守模糊。**调用方直接用 `FCUSTID` 规避歧义。**

## 3. 二开收付款单
- `TRNV_Receipt`（二开收款单）、`TRNV_PaymentSlip`（二开付款单）与标准 `AR_Receivable` / `AP_Payable` **并行存在**。
- 注意区分用户要的是二开单还是标准单；收款单联系单位字段是 `FCONTACTUNIT`。

## 4. BD_Material（物料）单位字段
- 查单位用 **`FBaseUnitId`**（非 `FUnitID`，后者在本环境元数据不存在）。

## 5. 提速工具支持的单据类型
- `u9_get_bill_template` 已验证骨架：`SAL_Quotation` / `SAL_SaleOrder` / `PUR_PurchaseOrder`。
- 新单据类型接入时，优先扩展 `get_bill_template` 的骨架库，而不是 each tool 重复拼包。

## 6. 源码重复注册噪音
- `server.py` 里 `u9_query_permission` 被重复注册，启动有 WARNING，**无害**，无需处理（除非重构期）。
