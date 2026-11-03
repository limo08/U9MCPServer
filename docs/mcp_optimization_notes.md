# u9-mcp 优化笔记

> 维护规则：每次实际使用 u9-mcp 后，把本次发现的、可优化该 MCP（代码/默认参数/错误处理/文档）的点追加到本文档，按日期分组。
> 目标不是记"怎么用"，而是记"MCP 哪里能做得更好"。
>
> **历史说明**：本文档早期条目可能引用旧版字段名或旧接口形态；当前实现统一使用
> U9C OpenAPI，相关旧端点与旧字段名仅保留作问题背景。

---

## 2026-07-16

### 1. SAL_SaleOrder 推荐字段在该环境直接报错（二开定制）
- **现象**：用 README / `u9_list_forms` 给出的 `recommended_fields`（含 `FSalesManId.FName`、`FTotalAmount`）查询 `SAL_SaleOrder` 时，用友返回
  `ErrorCode 500, Message="元数据中标识为FSalesManId的字段不存在"`；去掉业务员后再查，又报 `FTotalAmount` 不存在。
- **影响**：首次查询即失败，体验差；`u9_list_forms` 返回的 `recommended_fields` 也会诱导 AI 用错字段。
- **根因**：该环境的销售订单是二开定制版，缺标准字段。MCP 把 `recommended_fields` 当常量硬编码，未做字段存在性校验。
- **建议修复**：
  1. 查询类工具不要把 `recommended_fields` 写死；改为先调 `u9_get_fields` 探测真实字段再拼 `field_keys`；
  2. 或提供"环境字段覆盖/白名单"配置，避免对不存在字段发起请求；
  3. 当 WebAPI 返回"字段不存在"时，MCP 自动剔除该字段重试一次并提示用户，而非直接透传 500。

### 2. `u9_query_permission` 重复注册（启动噪声）
- **现象**：启动 / 列工具时打印 `WARNING Tool already exists: u9_query_permission`（`tool_manager.py:70`）。
- **影响**：无害，但掩盖真正需要关注的警告。
- **建议修复**：在 `server.py` 确认是否同一函数被 `@mcp.tool()` 注册了两次，去重。
- **【已修复 · 2026-08-06】根因不是「同一函数注册两次」，而是两个不同函数抢了同名 `u9_query_permission`**：
  - 行 ~3988：`u9_query_permission`（`PermissionQueryInput`）→ 查询权限列表；
  - 行 ~5174：`u9_query_permission`（`PermissionChangeInput`）→ 查询权限变更记录（审计）。
  - 后者覆盖前者，导致「查询权限列表」工具实际丢失 + 启动告警。
  - **修复**：第二个改名为 `u9_query_permission_changes`（语义贴合「查询权限变更记录」），同步更新 `tests/TEST_GUIDE.md` 7.5 示例。两个工具现已独立共存，无重复注册告警。
  - 另：`__init__.py` 的 `__version__` 漏写为 `"0.1.0"`，已对齐 PyPI 实际版本 `"0.2.1"`。

### 3. WebAPI 错误对 AI 不友好（多层嵌套）
- **现象**：字段缺失等错误包裹在 `Result.ResponseStatus.Errors[].Message` 里，AI 需解析多层 JSON 才能拿到可读信息。
- **建议修复**：MCP 层把 `ResponseStatus` 的错误提取成顶层 `error` 字段（含 Message + ErrorCode），便于 AI 直接读取并自愈（如自动改字段重试）。

### 4. 表单清单缺少"标准 vs 二开"标注
- **现象**：`u9_list_forms` 返回 48 个表单，含二开 `TRNV_Receipt`（二开收款单）、`TRNV_PaymentSlip`（二开付款单），与标准 Cloud 表单集不同。
- **建议修复**：文档/示例区分标准表单与二开表单；`list_forms` 可按 `has_business_rules` 或二开前缀（如 `TRNV_`）做标注，减少误用。

### 5. （部署）本机无 uvx，改用本地 venv
- **现象**：官方文档默认 `uvx u9-mcp`，但本机未装 `uv`/`uvx`。
- **建议**：在 README/部署文档里补一条「无 uvx 时」的本地 venv 启动方式（见 `C:\Users\ZnL\.workbuddy\mcp.json` 的 command 写法），降低落地门槛。

### 6. 销售报价单接口已存在但字段写死导致 500（已修复）
- **现象**：用户要求"新增销售报价单接口"，结果 `server.py` 里**早就有** `u9_query_sale_quotations`（旧定义在约 4305 行），但其默认字段写死 `FCustId.FName,FSalesmanId.FName,FTotalAmount`。本二开环境实测 `FSalesmanId` 不存在（报 500「元数据中标识为FSalesmanId的字段不存在」），主表也无 `FTotalAmount`。
- **根因**：与笔记 #1（SAL_SaleOrder）同类——硬编码了标准字段名，二开环境缺这些字段。
- **修复**：删掉重复的旧坏定义，保留一份并改用**实测可用的真实字段** `FID,FBillNo,FDate,FDocumentStatus,FCUSTID.FName,FSalerId.FName,FExpiryDate`（客户字段实为 `FCUSTID`，销售员为 `FSalerId`）。消除重复注册 WARNING。
- **验证**：venv 内 `import u9_mcp.server` 成功，工具总数 82、该工具 count=1、无重复注册；用通用查询以安全字段实测返回 `XSBJD0001`（客户"用友东方集团"、销售员"张小明"）。
- **注意**：**当前在跑的连接器加载的是改之前的旧代码**，需重启/重新信任 u9 连接器才能生效。

### 7. README 与代码严重不同步（待整体刷新）
- **现象**：README「可用工具列表」只列了约 6 个 `u9_query_*` 专用查询工具，但 `server.py` 实际注册了 **54 个** `u9_query_*` 工具（生产订单 / 采购申请 / 来料检验 / 费用报销 / 供应商报价 / 调拨申请 / 资产 等均已实现），总工具数 82。
- **影响**：之前按 README 判断的"待补接口清单"大部分已实现，会造成误判。
- **建议**：以 `server.py` 实际注册工具为准整体刷新 README；或加脚本从 `mcp.list_tools()` 自动生成工具清单，避免再次过期。

### 8. 其它专用查询工具大概率有同类二开字段坑（建议扫一遍）
- **现象**：`u9_query_sale_quotations` 旧定义暴露的问题（硬编码标准字段名、二开环境不存在）很可能在其它早期专用工具中同样存在（如 `u9_query_quality_inspections` 用了 `FInspectTypeId.FName` 等）。
- **建议**：对 54 个 `u9_query_*` 工具逐一把默认 field_keys 拿到本环境，用 `u9_get_fields` / 实际查询核对；凡引用二开缺失字段的，改为真实字段，统一规避 500。

### 9. `find_similar_field` 模糊匹配过激，会把字段名静默改错（此前"含税单价≤0"误判的真正元凶）
- **现象**：保存销售报价单时，客户字段写成 `FCustId`（驼峰），`validate_and_fix` 调 `find_similar_field("FCustId")` 把它**错误改成 `FCustLocId`（客户地点）**，而真实字段是 `FCUSTID`（全大写）。字段被静默改到错误位置，且不报错。
- **连带影响**：之前反复报"第1行分录，未免费的物料，含税单价不能小于等于0"——实测定位后确认**`FTaxPrice` 字段本身完全正常**（传 0.01 保存成功，见 XSBJD0002 / XSBJD0003）。真正原因是模型结构整体错了：①客户字段被错改成 `FCustLocId`；②漏填必填的 `FSaleOrgId`（销售组织）；③`FTaxPrice` 没真正落到 `FQUOTATIONENTRY` 分录里，用友拿到默认 0。是"模型结构错误"而非"字段损坏"。
- **根因**：`find_similar_field` 的通用模糊匹配阈值太松——`len(set(wrong[i:]) - set(valid[i:])) <= 1` 只比字符集差、不比顺序，大小写不同/字符重排都会被当成"相似"，导致跨语义误匹配（FCustId→FCustLocId）。
- **建议修复**：
  1. 第一优先做**大小写不敏感精确匹配**（把候选 key 归一化后再比对），命中即用，根本不会进模糊；
  2. 模糊匹配改为"去掉大小写后前缀一致 + 编辑距离小"，且只对已知真实拼写错误（如 `FSales`→`FSale`）做映射，不要对无关字段兜底；
  3. 模糊命中后在返回里明确带 `auto_fixes` 提示（机制已有，但要更保守，避免把正确字段改名）。

### 10. 销售报价单 SAL_Quotation 本环境的必填字段与正确结构（已验证可保存）
- `FSaleOrgId`（销售组织，`must_input=True`）：保存时必须传，否则整单校验不通过；标准值 `"100"` 实测可用。
- 客户字段名是 **`FCUSTID`**（全大写），不是 `FCustId`；且 `find_similar_field` 会把它误改成 `FCustLocId`（见 #9），建议直接用 `FCUSTID`。
- 表体 `FQUOTATIONENTRY` 的 `FUnitID`（销售单位，`must_input=True`）必须传；本批 26 个新物料单位均为 `Pcs`。
- 含税单价 `FTaxPrice` 字段正常，与 `FPrice`/`FTaxRate` 同放在 `FQUOTATIONENTRY` 内即可；占位价 0.01 保存成功。
- **已验证可用的最小模型**：
  ```json
  {
    "FBillTypeID": {"FNumber": "XSBJD01_SYS"},
    "FSaleOrgId": {"FNumber": "100"},
    "FCUSTID":    {"FNumber": "CUST0001"},
    "FQUOTATIONENTRY": [
      {"FMaterialId": {"FNumber": "1.02.001.0007.00006"}, "FUnitID": {"FNumber": "Pcs"},
       "FQty": 1, "FPrice": 0.01, "FTaxPrice": 0.01, "FTaxRate": 13}
    ]
  }
  ```

### 11. `_result_status` 返回字段名与调用方假设不一致（submit/audit 踩坑）
- **现象**：save 成功后 `_result_status` 返回 `fid` / `ids`，但调用方常按 `id` 取值 → 得到 `None`，导致后续 `submit`/`audit` 报 `编码值或内码值必须传其一`。
- **建议**：统一返回字段名为 `id`（或文档示例明确用 `fid` / `ids[0]`），避免下游取错。

### 12. BD_Material 元数据无 `FUnitID` 字段（二开定制，与 #1/#8 同类）
- **现象**：用 `FUnitID.FNumber` 查 `BD_Material` 报「元数据中标识为FUnitID的字段不存在」；改用 `FBaseUnitId.FNumber` 正常，26 个新物料单位均为 `Pcs`。
- **建议**：物料单位查询统一用 `FBaseUnitId`；列入二开字段坑统一排查清单。

### 13. 本次实战成果（2026-07-16）
- 用正确结构成功创建销售报价单 **`XSBJD0003`（Id 100010，26 行）**，已提交+审核生效；客户=用友东方集团（CUST0001），单价/含税单价均占位 0.01、税率 13%。
- 顺带验证了 `XSBJD0002`（单行草稿）保存路径。`XSBJD0001` 为用户手动创建（作为结构参照）。
- 26 个新物料（1.02.001.0007.00006 ~ .00031，Id 113483~113508）已于此前创建并提交+审核，单位均为 Pcs。

### 14. 【已实施】修复 find_similar_field 字段名静默误改（对应 #9）
- **改动**：`MetadataValidator.find_similar_field` 改为「大小写不敏感精确匹配优先 + 已知前缀纠正 + 保守模糊匹配（长度差≤1 且编辑距离小且共享≥4字符前缀）」；`validate_and_fix` 三处纠错现在**传入正确的候选集**（顶层用非分录字段、分录内用该分录子字段），彻底杜绝跨语义误改名。
- **验证**：离线单测 `find_similar_field("FCustId", [FCUSTID,FCustLocId,...])` 返回 `FCUSTID`（不再是 `FCustLocId`）；`FSalesOrgId`/`FBillTypeID`/`FDate` 原样保留；无关 `FXYZ999` 返回 `None`。
- **效果**：之前那次"含税单价≤0"的误判根因（FCustId 被偷偷改成 FCustLocId + 漏 FSaleOrgId）在修复后，第一次保存即可被 `u9_validate_bill` 抓出，无需反复试错。

### 15. 【已实施】新增 u9_validate_bill 保存前校验工具（对应提速核心）
- **改动**：新增 MCP 工具 `u9_validate_bill(form_id, model)`——不真正保存，跑元数据校验，返回 `ok / is_new / auto_fixes(将被改名的字段) / missing_required(缺失必填) / entry_issues(分录缺失必填) / suggestions`。
- **验证**：离线端到端测试，对 `{FCustId, FQUOTATIONENTRY[...]}`（缺 FSaleOrgId）返回 `auto_fixes:[FCustId→FCUSTID]`、`missing_required:[FSaleOrgId]`、`ok:false` + 修正建议。
- **推荐工作流**：`u9_get_bill_template` 取骨架 → 填数据 → `u9_validate_bill` 校验（秒级）→ `u9_save_bill` 保存。基本消除"失败→诊断"的小时级试错。

### 16. 【已实施】新增常用单据 model 模板缓存（u9_get_bill_template）
- **改动**：新增 `BILL_TEMPLATES` 常量（销售报价单 SAL_Quotation / 销售订单 SAL_SaleOrder / 采购订单 PUR_PurchaseOrder 的已验证骨架，含正确字段名+必填项+分录必填），并暴露 `u9_get_bill_template(form_id)` 工具。
- **验证**：实机调用返回 SAL_Quotation 骨架正确（FBillTypeID/FSaleOrgId/FCUSTID/FQUOTATIONENTRY 齐全）。
- **注意**：SAL_SaleOrder / PUR_PurchaseOrder 的字段名按标准用友填写、本二开环境未逐一实测，使用前请用 `u9_validate_bill` 校验一次。

### 17. 【已实施】元数据查询结果落盘缓存
- **改动**：`_query_metadata` 增加磁盘缓存（目录 `~/.workbuddy/u9_metadata_cache/`，按 服务地址hash+form_id 命名，避免多环境串缓存），并支持 `force=True` 强制刷新；新增 `u9_refresh_metadata(form_id)` 工具主动刷新。
- **效果**：新会话/脚本不再每次重查最慢的 QueryBusinessInfo；元数据变更后用 `u9_refresh_metadata` 刷新即可。
- **验证**：缓存路径逻辑已确认（`_metadata_cache_path` 正确生成）。注：本次实机刷新因 ERP 登录被拒（见下方"待办"）未能跑通落盘，但代码路径与旧逻辑一致，登录恢复后可正常使用。

### 18. 【待办/环境】当前 ERP 登录被拒（阻塞实机验证，非代码问题）
- **现象**：2026-07-16 傍晚起，用 demo 用户 + 当前 AppID 登录用友返回 `第三方应用：BOM配单 不允许用户demo 登录，请联系系统管理员添加！`。
- **影响**：`u9_validate_bill` 等依赖元数据的工具、以及任何写操作暂时无法实机验证（但 #14~#17 的代码逻辑已离线/模板验证正确）。
- **排查方向**：① 该 AppID 是否关联了"BOM配单"第三方应用而 demo 无权限（早些时候同凭据可登录，疑权限/应用绑定被改）；② 请系统管理员确认 demo 用户对集成应用的登录授权，或在用友【集成管理】检查 AppID 绑定；③ 也可能是会话/并发限制，稍后重试。
- **恢复后建议**：重跑 `scripts/` 下保存脚本或 `u9_validate_bill` 做一次端到端确认。

### 19. 【已实施】登录改为「仅账号密码登录」，彻底移除第三方应用授权（根治 #18）
- **背景**：#18 的登录被拒本质是第三方应用授权登录 `LoginByAppSecret` 依赖 APP_ID(BOM配单) 的用户白名单，账号不在白名单即被拒。这不是密码/权限问题，而是登录方式问题。
- **首版（18:43）**：新增 `U9_API_PASSWORD` + `ValidateUser` 端点，`_login()` 配密码走 ValidateUser、否则回退 LoginByAppSecret（向后兼容）。
- **终版（18:48，用户要求去掉第三方）**：按用户"只能用账号密码登录"要求，**删除所有第三方回退**：
  1. 删除配置项 `APP_ID`(U9_APP_ID)、`APP_SEC`(U9_APP_SEC)。
  2. 删除 `_EP["login"]`(LoginByAppSecret) 端点，仅保留 `login_user`(ValidateUser)。
  3. `_login()`：无 `if/else` 分支；首行 `if not PASSWORD: raise RuntimeError("未配置 U9_API_PASSWORD...")`；否则直接打 ValidateUser。
  4. `_run_check()`：`required` 固定为 SERVER_URL/ACCT_ID/USERNAME/PASSWORD，失败提示说明「第三方授权已不再使用」。
- **配套配置**：`~/.workbuddy/mcp.json` 的 u9.env 已删除 APP_ID/APP_SEC 两行，新增 `U9_API_PASSWORD": ""`（占位待填真实密码）。
- **验证**：`py_compile` 通过；`tests/manual/test_login.py` 空密码下正确抛 `未配置 U9_API_PASSWORD...`；全仓 grep 无 `APP_ID/APP_SEC/LoginByAppSecret/"login"` 残留。
- **待办**：用户在 mcp.json 填入 `U9_API_PASSWORD` 真实值 + 重启 u9 连接器，即可实机跑通。

### 20. 【已确认·更正】"含税单价不能小于等于0"的真正根因 = 字段顺序（FQUOTATIONFIN 必须在 FQUOTATIONENTRY 之前）
- **更正说明**：此前 #9/#10 把"第1行分录，未免费的物料，含税单价不能小于等于0"归因于 `FCustId→FCustLocId` 误改 + 漏 `FSaleOrgId` + `FTaxPrice` 未落分录。**这是错的**。本次（2026-07-16 晚）用独立脚本直连 WebAPI 做了控制变量验证：
  - 即便 `FCUSTID`/`FSaleOrgId` 都正确、`FPrice=1.0`/`FTaxPrice=1.13`/`FTaxRate=13` 都明传，只要 **`FQUOTATIONENTRY` 排在 `FQUOTATIONFIN` 之前**，仍 100% 报"含税单价≤0"；
  - 仅把顺序调成 **`FQUOTATIONFIN` 在前、`FQUOTATIONENTRY` 在后**（其余完全不变），**立即保存成功**。
  - 数值用 `1.0`/`1.13`（float）或 `"1.13"`（string）都不影响——确认**不是值类型问题，是本环境用友 Save 对字段顺序敏感**。
- **根因（推断）**：本二开账套里销售报价单的金额计算依赖财务信息（结算币别 `FSettleCurrId`、是否含税 `FIsIncludedTax` 等，都在 `FQUOTATIONFIN`）。分录单价在反序列化/计算时若先于财务信息被处理，会因币种/含税标志未就绪而被算成 0，触发该校验规则。**这是用友服务端行为，MCP 无法靠改字段名规避。**
- **已实施修复（server.py）**：
  1. `u9_save_bill` 在 `validate_and_fix` 之后、发请求之前，新增防御性排序：把所有**非 ENTRY 键**（含 `FQUOTATIONFIN` 与表头字段）统一置于 **ENTRY 键**之前，保持"表头→FIN→ENTRY"的已知可用顺序，从根本上避免顺序踩坑；
  2. `BILL_TEMPLATES["SAL_Quotation"]` 补上 `FQUOTATIONFIN: {"FSettleCurrId": {"FNumber": "PRE001"}}`，并**放在 `FQUOTATIONENTRY` 之前**，`get_bill_template` 现在直接给出正确顺序的骨架（结算币别默认 PRE001 人民币）。
- **实测**：修复后 `u9_save_bill` 成功创建销售报价单 **`XSBJD0011`（FID 100024，26 行）**，客户=用友东方集团(CUST0001)，26 个电子料（1.02.001.0007.00006~.00031），单价/含税单价占位 0.01、税率 13%、销售组织 100、币别 PRE001。状态：草稿。
- **注意**：改的是 `server.py` 源码，**当前在跑的连接器仍是旧代码**，需重启/重新信任 u9 连接器才能让排序修复与模板生效。
