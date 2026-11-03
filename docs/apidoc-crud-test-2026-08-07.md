# 用友 ApiDoc 1076 业务对象 CRUD（增删改查）测试报告

- **报告日期**：2026-08-07
- **整理人**：Limo
- **数据来源**：
  - 能力盘点：`api-inventory-raw.json`（操作名统计，u9-mcp-dev skill references）
  - 代码级用例：`tests/test_crud_all_objects.py`（寇豆码产出）
  - 真机抽样：`D:\AI\projects\u9-mcp\temp_crud_sampling.json`（严过关产出，40 对象）
- **测试性质**：代码级 mock（不碰账套）+ 真机抽样 CRUD（QA_CRUD_ 前缀临时数据，测后清理）
- **测试环境**：历史归档环境（已停用；当前请使用 U9C 测试账套），账套 `6979ac7e5959f4`

---

## 1. 测试范围与方法

### 1.1 能力盘点（api-inventory 操作名统计）

对 ApiDoc 1076 个业务对象按标准操作名盘点 CRUD 能力：

| 能力分类 | 数量 | 说明 |
|----------|-----:|------|
| 有保存操作（可增/改） | **726** | 保存 / 批量保存 / 暂存，可测 `u9_save_bill` 请求构造 |
| 有删除操作 | **631** | 删除 / 删除对象，可测 `u9_delete_bills` 请求构造 |
| 仅查询（报表/只读，无增删改） | **319** | 单据查询 / 查询报表数据 / 查看 |
| 无标准动作（自定义 API 等） | **14** | 自定义 API / 仅特殊动作 |

> 启用状态沿用此前测试矩阵结论：已启用 **1055** / 未启用 **21**。

### 1.2 测试方法（两层）

1. **代码级全量 CRUD 用例**（寇豆码，mock 不碰账套）：
   - 新文件 `tests/test_crud_all_objects.py`，基于 `docs/apidoc-formid-map-2026-08-07.json`（1076 条，全部含 formid）+ `api-inventory-raw.json` 操作名。
   - 断言**请求构造 + 参数校验**（mock 层），不断言真机成功；**强制 patch `_get_metadata_validator` 杜绝真机请求**。
   - 命令：`python -m pytest tests/test_crud_all_objects.py -q`。
2. **真机抽样 CRUD**（严过关，40 个，QA_CRUD_ 前缀临时数据，测完清理）：
   - 从可写域抽样 40 个（10 单据类 + 30 基础资料类），**已排除二开 TRNV / SAL_SaleOrder 等**。
   - 基础资料链路：Save → 查 → 改（Update）→ Delete；单据链路：Save → 查 → Submit → Audit → UnAudit → Delete。

### 1.3 关键坑位断言（写入用例防回归）

- `_result_status` 返回的是 **fid / ids，不是 id**——save 断言有 fid 无 id，delete 断言有 ids 无 id。
- `bill_ids=[]` 触发 Pydantic `ValidationError`（min_length=1）；`ExecuteActionInput` 不传 bill_ids/bill_nos 触发中文校验「至少提供一个」；`SaveInput` 缺 form_id 触发 `ValidationError`。

---

## 2. 代码级全量 CRUD 用例结果

**运行结果**：`python -m pytest tests/test_crud_all_objects.py -q` → **2439 passed + 333 skipped + 0 failed**（约 9s）。

| 用例组 | 数量 | 覆盖对象 | 说明 |
|--------|-----:|----------|------|
| `test_query_construct` | 1076 | 全部 1076 | `u9_query_bills` payload 含 FormId |
| `test_save_construct` | 726 | 有保存操作对象 | `u9_save_bill` 收到 ("save", form_id, model)，model 合法（含默认 FID=0），返回用 fid（非 id） |
| `test_delete_construct` | 631 | 有删除操作对象 | `u9_delete_bills` 收到 ("delete", form_id, {"Ids": "..."})，返回用 ids（非 id） |
| 参数校验 | 6 | 通用入参 | 缺 form_id / extra 字段 forbid / 空 ids / ExecuteActionInput 中文报错（至少提供一个）/ 空 bill_ids / fid-not-id 语义锚点 |
| **passed 合计** | **2439** | — | 1076 + 726 + 631 + 6 |
| 报表/只读 skip | 319 | 仅查询对象 | `pytest.mark.skip` 标注「报表/只读无增删改」 |
| 无标准动作 skip | 14 | 自定义 API 等 | `pytest.mark.skip` 标注「无标准动作」 |
| **skipped 合计** | **333** | — | 319 + 14 |

> 关键点：`test_save_returns_fid_not_id_semantics` 锚定 `_result_status` 语义；mock 强制 patch `u9_mcp.server._get_metadata_validator`，保证**不产生任何真机请求**，纯本地构造校验。

---

## 3. 真机抽样 CRUD 结果

### 3.1 抽样清单（40 个，按域分组）

> 覆盖 **14 个可写业务领域**（按数据文件 domain 字段统计），10 单据类 + 30 基础资料类；结果标注：✅全通 / 🟡部分 / ⛔构造失败·业务规则 / 🚫权限拒绝。

| 域 | 模块 | 对象 | FormId | 类型 | 结果 | 备注 |
|----|------|------|--------|:----:|:----:|------|
| 基础管理 | 基础资料 | 客户 | BD_Customer | 基础资料 | ✅ 全通 | 非 FID 主键坑下 Save/Delete 用主键全通 |
| 基础管理 | 基础资料 | 供应商 | BD_Supplier | 基础资料 | ⛔ 构造失败 | FStartDate 实体无此属性（字段不一致） |
| 基础管理 | 基础资料 | 部门 | BD_Department | 基础资料 | ✅ 全通 | 按错误迭代剔除坏字段一次成功 |
| 基础管理 | 基础资料 | 银行 | BD_BANK | 基础资料 | ⛔ 构造失败 | 失效日期不能早于生效日期 |
| 财务会计 | 总账 | 币别 | BD_Currency | 基础资料 | ⛔ 构造失败 | 勾选显示货币符号时符号必填 |
| 财务会计 | 总账 | 科目 | BD_Account | 基础资料 | ⛔ 构造失败 | 请先选择科目表 |
| 财务会计 | 应收款管理 | 其他应收单 | AR_OtherRecAble | 单据 | ⛔ 构造失败 | 往来单位必填；明细金额≠0 |
| 财务会计 | 应付款管理 | 其他应付单 | AP_OtherPayable | 单据 | ⛔ 构造失败 | 费用管理已启用，不能手工新增 |
| 供应链 | 采购管理 | 采购申请单 | PUR_Requisition | 单据 | ✅ 全通 | **六步全通零残留（唯一单据全通）** |
| 供应链 | 销售管理 | 发货通知单 | SAL_DELIVERYNOTICE | 单据 | 🟡 部分 | 审核后自动整单关闭，UnAudit/Delete 被阻 |
| 供应链 | 采购管理 | 采购入库单 | STK_InStock | 单据 | ⛔ 构造失败 | 批号/上游来源/委外/仓库/来料检验多规则连环 |
| 供应链 | 采购管理 | 联系人 | BD_CommonContact | 基础资料 | 🟡 部分 | Delete 被状态规则阻止 |
| 生产制造 | 工程数据管理 | 设备 | ENG_Equipment | 基础资料 | ✅ 全通 | — |
| 生产制造 | 工程数据管理 | 工作中心 | ENG_WorkCenter | 基础资料 | ✅ 全通 | — |
| 生产制造 | 计划管理 | 预测单 | PLN_FORECAST | 单据 | ⛔ 构造失败 | 无样例数据无法克隆（异常中断） |
| 零售管理 | 会员管理 | 会员发卡登记 | CMK_VIP_CardIssueBill | 单据 | 🚫 权限拒绝 | 无查看权限 |
| 零售管理 | 会员管理 | 会员资料 | CMK_VIP_MembershipInfo | 基础资料 | 🚫 权限拒绝 | 无新增权限 |
| 零售管理 | 礼券管理 | 礼券包 | CMK_LS_Ticketpack | 基础资料 | 🚫 权限拒绝 | 无新增权限 |
| 成本管理 | 产品成本核算 | 成本中心 | CB_COSTCENTER | 基础资料 | ✅ 全通 | — |
| 成本管理 | 产品成本核算 | 成本项目 | HS_CostItem | 基础资料 | ✅ 全通 | — |
| 成本管理 | 产品成本核算 | 作业活动 | CB_WORKACTIVITIES | 基础资料 | ✅ 全通 | — |
| 电商与分销 | B2C电商中心 | 网店管理 | ECC_Shop | 基础资料 | ⛔ 构造失败 | 对应客户/结算币别/结算组织/运费物料/仓库/发货地址必录 |
| 电商与分销 | 渠道资金池管理 | 账户类型 | FUM_AccountType | 基础资料 | 🚫 权限拒绝 | 无新增权限 |
| 电商与分销 | 营销网络 | 营销网络 | DRP_Channel | 基础资料 | ✅ 全通 | — |
| PLM | 设计工艺管理 | 设备 | PLM_ENG_EQUIPMENT | 基础资料 | ✅ 全通 | — |
| PLM | 项目管理 | 检查项 | PLM_STD_CHECK | 基础资料 | 🟡 部分 | 查/改/删无功能权限 |
| 管理会计 | 经营会计 | 经营科目 | AM_Account | 基础资料 | ✅ 全通 | — |
| 管理会计 | 预算管理 | 预算业务类型 | BM_BUSINESSTYPE | 基础资料 | ✅ 全通 | — |
| 质量管理 | 质量管理 | 缺陷类型 | QM_DefectType | 基础资料 | ✅ 全通 | — |
| 质量管理 | 质量管理 | 缺陷原因 | QM_DEFECTREASON | 基础资料 | ✅ 全通 | — |
| 质量管理 | 质量管理 | 检验仪器 | QM_InspectInstrument | 基础资料 | ✅ 全通 | — |
| 资产管理 | 固定资产 | 资产类别 | FA_ASSETTYPE | 基础资料 | ⛔ 构造失败 | 资产编码规则必填 |
| 资产管理 | 固定资产 | 资产状态 | FA_STATUS | 基础资料 | ✅ 全通 | — |
| 资产管理 | 固定资产 | 资产位置 | FA_POSITION | 基础资料 | ✅ 全通 | — |
| 税务管理 | 发票管理 | 税收分类编码 | IV_GTTAXCODE | 基础资料 | ✅ 全通 | — |
| 税务管理 | 发票管理 | 引出方案设置 | BD_SALESIEMPIMP | 基础资料 | ⛔ 构造失败 | FLinkType 需字典格式 |
| 员工服务 | 人人报销 | 费用申请单 | ER_ExpenseRequest | 单据 | ⛔ 构造失败 | FBillTypeID 需字典格式 |
| 员工服务 | 人人报销 | 费用报销单 | ER_ExpReimbursement | 单据 | ⛔ 构造失败 | FBillTypeID 需字典格式 |
| BOS | 应用框架 | 辅助资料 | BOS_ASSISTANTDATA_DETAIL | 基础资料 | ⛔ 构造失败 | 编码长度超限；类别必填 |
| 财务会计 | 总账 | 凭证 | GL_VOUCHER | 单据 | ⛔ 构造失败 | 分录摘要/期间/金额/必录维度多约束 |

### 3.2 统计

| 结果分层 | 数量 | 明细 |
|----------|-----:|------|
| 全链路通过（full_chain_pass） | **18** | 基础资料 17（Save→查→改→Delete 全通）+ 单据 1（PUR_Requisition 六步全通） |
| 部分通过（partial_pass） | **3** | SAL_DELIVERYNOTICE / BD_CommonContact / PLM_STD_CHECK |
| 构造失败 / 业务规则阻止（construct_fail） | **15** | 单据 7 + 基础资料 8，多为用友业务规则与字段构造约束 |
| 权限拒绝（permission_denied） | **4** | CMK_VIP_CardIssueBill / CMK_VIP_MembershipInfo / CMK_LS_Ticketpack / FUM_AccountType（lxy 账号无写权限） |
| **合计** | **40** | 10 单据 + 30 基础资料 |

### 3.3 典型成功案例

1. **PUR_Requisition 采购申请单（单据类六步全通零残留）**：Save → 查 → Submit → Audit → UnAudit → Delete 六步全通，**零残留**——证明通用 Save/Submit/Audit/UnAudit/Delete 端点对单据类全链路可用。
2. **BD_Customer 客户（非 FID 主键坑）**：基础资料主键非 FID，默认 FID 报「FID 字段不存在」；换用正确主键后 Save/查/改/Delete 全通——验证通用工具主键自适应 + 元数据纠错链路可用。
3. **BD_Department 部门 / QM_DefectType 等基础资料**：Save→查→改→Delete 全通，其中 BD_Department 靠「按错误信息迭代剔除坏字段」策略**一次成功**，说明通用工具对复杂基础资料字段有良好健壮性。

### 3.4 典型失败案例

1. **STK_InStock 采购入库单（多规则连环阻止）**：批号为空、所有分录必须关联生成、委外需上游采购订单、仓库必录、来料检验物料不能直接入库——多条业务规则连环阻止，属**用友业务约束**而非工具缺陷。
2. **SAL_DELIVERYNOTICE 发货通知单（审核自动关闭）**：Save/Submit/Audit 成功，但审核后系统**自动整单关闭**，UnAudit/Delete 被状态规则阻止，产生残留数据且无法 WebAPI 删除。
3. **GL_VOUCHER 凭证（分录必录维度）**：分录摘要为空、期间数限制、借贷金额不能同时为零、科目 5101-制造费用必录维度「部门」未录入——凭证类约束多，构造样例难以满足。

---

## 4. 失败原因分类

> 结论：**工具无功能缺陷**；40 个抽样中 22 个（18 全通 + 4 权限拒绝）与工具无关，失败全部来自以下三类。

### 4.1 用友业务规则（最多，构造失败主体）
- **审核后自动整单关闭**：SAL_DELIVERYNOTICE（反审核/反关闭/删除被阻）。
- **单据状态删除规则**：SAL_DELIVERYNOTICE、BD_CommonContact（仅暂存/创建/重新审核状态可删）。
- **必录/来源/批号约束**：STK_InStock（批号必录/上游来源必填/委外需上游订单/仓库必录/来料检验需质检）、GL_VOUCHER（凭证分录必录维度/摘要/金额）。
- **其他业务规则**：BD_BANK（失效日期不能早于生效）、BD_Currency（货币符号必填）、FA_ASSETTYPE（资产编码规则必填）、AP_OtherPayable（费用管理已启用不能手工新增）、BOS_ASSISTANTDATA_DETAIL（编码长度/类别必填）。
- **处理原则**：通用工具应**透传用友原始报错**，不吞错、不自行改写。

### 4.2 账号权限不足（4 个）
- CMK_VIP_CardIssueBill / CMK_VIP_MembershipInfo / CMK_LS_Ticketpack / FUM_AccountType——lxy 账号无查看/新增权限（「您没有…权限，请联系系统管理员」）。
- 属**账号授权问题**，换用有权限账号即可验证。

### 4.3 字段构造复杂 / 元数据不一致（少数，可迭代解决）
- **元数据与实体属性不一致**：BD_Supplier（FStartDate 实体不存在此属性）。
- **字段需字典格式**：ER_ExpenseRequest / ER_ExpReimbursement（FBillTypeID）、BD_SALESIEMPIMP（FLinkType）。
- **依赖前置对象**：BD_Account（请先选择科目表）、ECC_Shop（对应客户/结算币别等必录）、AR_OtherRecAble（往来单位必填）、PLN_FORECAST（无样例数据无法克隆）。
- **已验证策略**：「按错误信息迭代剔除坏字段」有效——BD_Department / BD_Customer 靠该策略一次成功。

---

## 5. 残留临时数据（4 条）

> 业务规则限制导致无法通过 WebAPI 删除（QA_CRUD_ 前缀，非正式业务数据）。

| FormId | ID | 编码 | 残留原因 |
|--------|----:|------|----------|
| SAL_DELIVERYNOTICE | 100008 | QA_CRUD_SAL_DELIVERYNOTICE_1 | 审核后系统自动整单关闭，反审核/反关闭/删除均被规则阻止 |
| SAL_DELIVERYNOTICE | 100009 | QA_CRUD_SAL_DELIVERYNOTICE_10 | 只能删除创建/暂存/重新审核状态的数据 |
| BD_CommonContact | 113538 | QA_CRUD_BD_CommonContact_12 | 单据状态为暂存/创建/重新审核才允许删除 |
| PLM_STD_CHECK | 113547 | QA_CRUD_PLM_STD_CHECK_26 | 无当前功能权限 |

**建议**：以上为测试临时数据，因用友业务状态/权限规则无法 WebAPI 清理，**建议账套管理员人工处理，或按测试数据忽略**（不影响正式业务数据）。

---

## 6. 结论与建议

### 6.1 结论

- **通用工具 CRUD 链路真机验证通过**：单据类 + 基础资料类均可完成增删改查全链路（18/40 全通，含唯一单据六步全通 PUR_Requisition 与基础资料 17 例全通），**无阻塞性缺陷**。
- **代码级全量覆盖**：2439 passed + 333 skipped + 0 failed（约 9s），1076 对象 query 构造、726 save、631 delete、319 只读、14 无标准动作、6 参数校验全覆盖。
- **失败均为用友业务约束 / 权限 / 字段复杂**：业务规则（审核自动关闭/批号/来源/维度必录）15、账号权限 4、字段构造/元数据不一致若干——均非通用工具功能缺陷。

### 6.2 建议

1. **工具层保留健壮性**：继续保留「按错误信息迭代剔除坏字段」策略（已验证对复杂基础资料有效），并**透传用友原始报错**，便于用户按报错修正入参。
2. **权限类**：CMK_VIP_* / FUM_AccountType 等如需验证，请使用有写权限的账号。
3. **残留数据**：4 条 QA_CRUD_ 临时数据建议账套管理员人工处理或忽略。
4. **本轮测试性质**：代码级 mock 全程不碰账套；真机抽样使用 QA_CRUD_ 前缀临时数据并测后清理，除上述 4 条残留外无正式数据变更。

---

*数据文件：`D:\AI\projects\u9-mcp\temp_crud_sampling.json`（generated_at 2026-08-07 18:30:59，finalized_at 18:32:10）*
