"""常用表单目录（form_id → 名称/字段/业务规则/数据库表映射）。"""




# 💡 REMEMBER: 元数据自动纠错 - 使用 U9C OpenAPI 目录验证和修正字段名

# ─────────────────────────────────────────────
# 常用表单目录（form_id 映射）
# 字段说明：
#   name       — 表单中文名称
#   alias      — 常用别名列表（用于 AI 理解用户意图）
#   desc       — 表单用途描述（帮助 AI 判断何时使用该表单）
#   fields     — 推荐查询字段（U9C 字段名优先；旧 F* 别名由 u9c_mapping 翻译）
#   business_rules — 关键业务规则（字段→含义 / 操作限制）
#   db_tables  — U9 数据库物理表名（主表 + 明细/行表），取自 u9_schema.json；
#                与上面的 WebAPI 字段不是同一套命名（U9 库表主键是 ID，单据号是 DocNo）
#
# 环境说明：
#   字段标注 [需启用供应链] 表示需要采购/库存模块启用后才存在
#   业务规则字段（如 FLinkQty/FBusinessClose）在 demo 环境可能不存在
#   💡 REMEMBER: demo 环境缺失字段：FLinkQty, FBusinessClose, FFreezeStatus, FTerminateStatus, FDlyCntl_Low/High, FCloseStatus, FTotalAmount
#   如遇字段不存在错误，请用 u9_get_fields(form_id) 查看实际可用字段
# ─────────────────────────────────────────────

FORM_CATALOG = {
    # ══════════════════════════════════════════════════════
    # 基础资料
    # ══════════════════════════════════════════════════════
    "BD_Material": {
        "name": "物料",
        "alias": ["物料", "材料", "商品", "产品"],
        "desc": "企业采购、生产、销售的最小存货单位，是供应链和财务核算的基础。",
        "fields": "FMaterialId,FNumber,FName,FSpecification,FUnitID.FName,FMaterialGroup.FName,FDocumentStatus",
        "db_tables": ("CBO_ItemMaster",),
    },
    "BD_Customer": {
        "name": "客户",
        "alias": ["客户", "客户档案", "客户资料"],
        "desc": "企业销售业务中的购买方（下游）。",
        "fields": "FNumber,FName,FShortName,FContact,FPhone,FDocumentStatus",
        "db_tables": ("CBO_Customer",),
    },
    "BD_Supplier": {
        "name": "供应商",
        "alias": ["供应商", "供应商档案", "厂家", "供货商"],
        "desc": "企业采购业务中的供应方（上游）。",
        "fields": "FSupplierId,FNumber,FName,FShortName,FContact,FPhone,FDocumentStatus",
        "db_tables": ("CBO_Supplier",),
    },
    "BD_Department": {
        "name": "部门",
        "alias": ["部门", "组织", "组织架构"],
        "desc": "企业内部组织单元，用于业务归属和权限控制。",
        "fields": "FDeptId,FNumber,FName,FFullName,FParentID.FName",
        "db_tables": ("CBO_Department",),
    },
    "BD_Empinfo": {
        "name": "员工",
        "alias": ["员工", "人员", "职员", "用户", "采购员"],
        "desc": "企业职员资料，常用于采购员、销售员等业务角色指定。",
        "fields": "FID,FStaffNumber,FName,FDeptId.FName,FDocumentStatus",
        "db_tables": ("CBO_Person",),
    },
    "BD_Stock": {
        "name": "仓库",
        "alias": ["仓库", "库房", "仓位", "库存组织"],
        "desc": "物料存储位置，是出入库和库存管理的核心维度。",
        "fields": "FStockId,FNumber,FName,FGroup.FName,FStockType.FName,FDocumentStatus",
        "db_tables": ("CBO_InventoryInfo",),
    },
    "BD_Unit": {
        "name": "计量单位",
        "alias": ["单位", "计量单位", "单位组"],
        "desc": "物料数量的计量标准，如个、件、箱、吨等。",
        "fields": "FUnitId,FNumber,FName,FType",
        "db_tables": ("Base_UOM",),
    },
    "BD_Currency": {
        "name": "币别",
        "alias": ["币别", "货币", "币种"],
        "desc": "业务交易的货币类型，如人民币、美元等。",
        "fields": "FCurrencyId,FNumber,FName,FSymbol,FExchangeRateType",
        "db_tables": ("Base_Currency",),
    },

    # ══════════════════════════════════════════════════════
    # 供应链：采购
    # ══════════════════════════════════════════════════════

    "PUR_PurchaseOrder": {
        "name": "采购订单",
        "alias": ["采购订单", "采购单", "PO", "采购合同订单"],
        "desc": (
            "企业与供应商的采购协议，记录货物规格、价格、交货条件，是采购业务的核心单据。"
            "与收料通知单、采购入库单、退料申请单有上下游关联关系。"
        ),
        # 注：FTotalAmount/FLinkQty/FBusinessClose 等字段在 demo 环境可能不存在，
        #     如遇字段不存在错误，请用 u9_get_fields 确认实际可用字段
        "fields": (
            "FID,FBillNo,FDate,FDocumentStatus,"
            "FSupplierId.FName,FSupplierId.FNumber,"
            "FPurchaseDeptId.FName,FPurchaserId.FName,"
            "FTaxAmount,FAllAmount,"
            "FMaterialId.FName,FMaterialId.FNumber,FQty,"
            "FReceiveQty,FStockInQty"
        ),
        "db_tables": ("PM_PurchaseOrder", "PM_POLine"),
        "business_rules": {
            "FReceiveQty": "累计收料数量（收料单审核时累加，反审核时扣减）",
            "FStockInQty": "累计入库数量（入库单审核时累加，反审核时扣减）",
            "FLinkQty [需启用供应链]": "关联数量 = 累计收料数量 + 累计入库数量，>=订单数量时无法下推",
            "FBusinessClose [需启用供应链]": "业务关闭状态（A=正常 B=业务关闭）",
            "FFreezeStatus [需启用供应链]": "冻结状态（A=正常 B=冻结）",
            "FTerminateStatus [需启用供应链]": "终止状态（A=正常 B=终止）",
            "FDlyCntl_Low [需启用供应链]": "交货下限，勾选控制交货数量后生效",
            "FDlyCntl_High [需启用供应链]": "交货上限，勾选控制交货数量后生效",
            "FCloseStatus [需启用供应链]": "整单关闭状态（A=未关闭 B=已关闭）",
            "下推收料通知单": "单据状态=已审核 + 关闭状态=未关闭 + 业务状态=正常 + 关联数量<订单数量",
            "下推采购入库单": "单据状态=已审核 + 关闭状态=未关闭 + 业务状态=正常 + 关联数量<订单数量 + 来料检验=未勾选",
            "交货数量控制 [需启用供应链]": "勾选后：关联数量>=交货下限无法下推；关联数量+本次>交货上限目标单据无法保存",
            "业务关闭条件 [需启用供应链]": "累计入库数量>=交货下限时，该行自动业务关闭；<交货下限自动反关闭",
            "冻结/终止限制 [需启用供应链]": "冻结或终止的分录行只允许查看、反冻结/反终止、打印、引入引出",
            "预付关联": "采购订单被付款单关联后，不可反审核",
        },
    },

    "PUR_ReceiveBill": {
        "name": "收料通知单",
        "alias": ["收料通知", "到货通知", "收料单", "来料通知"],
        "desc": (
            "供应商发货到货后创建的通知单，用于来料检验和入库准备。"
            "可直接下推采购入库单；若物料勾选来料检验，则入库必须经由收料单。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FStockOrgId.FName,FInspectStatus",
        "db_tables": ("PM_ASN", "PM_ASNLine"),
        "business_rules": {
            "来料检验": "物料勾选来料检验时，入库必须先收料再检验，无法直接从订单下推入库单",
            "审核更新": "收料单审核时，累加采购订单【累计收料数量】；反审核时扣减",
            "下推入库": "可下推采购入库单；下推时入库单日期须在最早/最晚交货时间内",
        },
    },

    "PUR_MRB": {
        "name": "采购退料单",
        "alias": ["采购退料", "退货单", "来料不良退货"],
        "desc": "供应商供货存在质量问题时，向供应商退货的单据。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FReturnReason,FReturnQty",
        "db_tables": ("QC_MRB", "QC_MRBLine"),
        "business_rules": {
            "退料前提": "采购订单【检验可退数量】或【库存可退数量】>0 时才可发起退料",
            "补料方式": "与采购订单关联的退料单【补料方式】必须为按原单补料",
        },
    },

    "PUR_Requisition": {
        "name": "采购申请单",
        "alias": ["采购申请", "申购单", "请购单", "采购需求"],
        "desc": (
            "企业内部各需求部门发起的采购需求，是采购流程的起点。"
            "可下推生成采购订单、采购询价单等。审核后流转至采购部门执行。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FRequestDeptId.FName,FApplicantDeptId.FName,FTotalAmount",
        "db_tables": ("PR_PR", "PR_PRLine"),
        "business_rules": {
            "流转方向": "采购申请单 → 采购订单 或 采购询价单（RFQ）",
            "单人审核": "同一采购员同一天只能审核一张采购申请单",
        },
    },

    "PUR_MRAPP": {
        "name": "退料申请单",
        "alias": ["退料申请", "退料申请单"],
        "desc": "库存物料需要退还给供应商时，发起的退料申请。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FReturnType,FReturnQty",
        "db_tables": ("QC_MRB", "QC_MRBLine"),
    },

    "PUR_Contract": {
        "name": "采购合同",
        "alias": ["采购合同", "合同", "采购协议"],
        "desc": "与供应商签订的框架采购协议，可关联具体采购订单执行。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FTotalAmount,FContractStatus",
        "db_tables": ("PM_PurchaseContract",),
    },

    "PUR_PriceCategory": {
        "name": "采购价目表",
        "alias": ["采购价目", "采购价格", "价格资料", "供应商价格"],
        "desc": "供应商对特定物料的定价清单，采购订单可直接引用价目表价格。",
        "fields": "FID,FBillNo,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPrice,FTaxPrice,FCurrencyId.FName",
        "db_tables": ("PPR_PurPriceList", "PPR_PurPriceLine"),
    },

    "PUR_PAT": {
        "name": "采购调价表",
        "alias": ["采购调价", "调价表", "价格调整"],
        "desc": "调整采购价目表中物料价格的单据，有生效日期控制。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FMaterialId.FName,FOldPrice,FNewPrice,FEffectiveDate",
        "db_tables": ("PPR_PurPriceAdjustment", "PPR_PurPriceAdjustLine"),
    },

    # ══════════════════════════════════════════════════════
    # 供应链：供应商协同
    # ══════════════════════════════════════════════════════

    "SVM_InquiryBill": {
        "name": "采购询价单",
        "alias": ["询价单", "询价", "RFQ", "请求报价"],
        "desc": "向供应商发起采购询价（Request for Quotation），收集报价信息。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FExpiryDate",
        "db_tables": ("PPR_RequestForQuotation", "PPR_RFQLine"),
    },

    "SVM_QuoteBill": {
        "name": "供应商报价单",
        "alias": ["报价单", "报价", "供应商报价", "报价响应"],
        "desc": "供应商对询价单的响应，包含物料价格、货期等信息。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPrice,FQuantity,FDeliveryDate",
        "db_tables": ("PPB_QuoteDoc", "PPB_QuoteDocLine"),
    },

    "SVM_ComparePrice": {
        "name": "比价单",
        "alias": ["比价", "比价单", "价格比较"],
        "desc": "对多个供应商报价进行比价分析，辅助采购决策。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FMaterialId.FName,FSupplierId.FName,FPrice,FBestSupplier",
        "db_tables": ("PPR_CP", "PPR_CPLine"),
    },

    # ══════════════════════════════════════════════════════
    # 供应链：销售
    # ══════════════════════════════════════════════════════

    "SAL_SaleOrder": {
        "name": "销售订单",
        "alias": ["销售订单", "销售单", "SO", "销售合同"],
        "desc": (
            "企业与客户的销售协议，记录销售货物、价格、交货条件。"
            "可下推生成销售出库单、销售退货单、发货通知单等。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FSalesOrgId.FName,FSalesManId.FName,FTotalAmount,FLinkQty,FStockOutQty,FDeliQty",
        "db_tables": ("SM_SO", "SM_SOLine"),
        "business_rules": {
            "FLinkQty": "关联数量 = 已出库数量 + 已关联数量",
            "FStockOutQty": "累计出库数量（销售出库单审核时累加）",
            "FDeliQty": "累计发货数量",
            "关闭条件": "累计出库数量 >= 订单数量时自动行关闭",
            "冻结/终止": "冻结或终止的分录行不允许编辑和关联操作",
        },
    },

    "SAL_OUTSTOCK": {
        "name": "销售出库单",
        "alias": ["销售出库", "出货单", "发货单", "销售发货"],
        "desc": (
            "销售订单下推或手工创建的发货单据，确认货物出库并更新库存。"
            "审核时自动更新销售订单的累计出库数量。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FStockOrgId.FName,FStockId.FName,FOutQty",
        "db_tables": ("SM_Ship", "SM_ShipLine"),
        "business_rules": {
            "审核更新": "审核时累加销售订单【累计出库数量】；反审核时扣减",
            "可发量控制": "可发量不足时无法出库（勾选控制可发量时）",
        },
    },

    "SAL_RETURNSTOCK": {
        "name": "销售退货单",
        "alias": ["销售退货", "退货", "客户退货"],
        "desc": "客户因质量问题等原因退货的单据，审核时更新原销售订单的退货数量。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FReturnReason,FReturnQty",
        "db_tables": ("SM_RMA", "SM_RMALine"),
    },

    "SAL_Quotation": {
        "name": "销售报价单",
        "alias": ["销售报价", "报价单", "SQ", "销售提案"],
        "desc": "向客户提供的商品或服务价格方案，可作为销售订单的参考价格。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FSalesmanId.FName,FTotalAmount,FExpiryDate",
        "db_tables": ("SM_Quotation", "SM_QuotationLine"),
    },

    "SAL_DELIVERYNOTICE": {
        "name": "发货通知单",
        "alias": ["发货通知", "送货通知", "发货单"],
        "desc": "销售出库前的发货准备单据，可下推生成销售出库单。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FDeliveryDate,FNoticeQty",
        "db_tables": ("SM_PreShip", "SM_PreShipLine"),
    },

    "SAL_RetuenNotice": {
        "name": "退货通知单",
        "alias": ["退货通知", "退货单", "客户退货通知"],
        "desc": "客户退货时的通知单，可下推生成销售退货单。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FReturnReason,FReturnQty",
        "db_tables": ("SM_RMA", "SM_RMALine"),
    },

    "SAL_AvailableQuery": {
        "name": "可发量查询",
        "alias": ["可发量", "可用量", "可用库存", "库存可用量"],
        "desc": "查询物料在指定仓库的可用库存数量（可发量 = 即时库存 - 已分配量）。",
        "fields": "FMaterialId.FNumber,FMaterialId.FName,FStockId.FName,FAvailableQty,FUnitId.FName",
        "db_tables": ("CBO_ItemQty",),
    },

    # ══════════════════════════════════════════════════════
    # 供应链：库存
    # ══════════════════════════════════════════════════════

    "STK_InStock": {
        "name": "采购入库单",
        "alias": ["采购入库", "入库单", "入库", "来货入库"],
        "desc": (
            "物料实际验收入库的单据。来料检验的物料须先收料检验，合格后再入库；"
            "不需检验的物料可直接从采购订单下推入库。"
            "审核时累加采购订单【累计入库数量】。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName,FStockId.FName,FMaterialId.FName,FInQty,FSupplierId.FName",
        "db_tables": ("InvDoc_OnStoreCheck", "InvDoc_OnStoreCheckL"),
        "business_rules": {
            "审核更新": "入库单审核时累加采购订单【累计入库数量】；反审核时扣减",
            "交货数量控制": "勾选控制交货数量时，入库数量不能超过采购订单【交货上限】",
            "交货时间控制": "入库日期须在采购订单【最早/最晚交货时间】之间",
        },
    },

    "STK_MisDelivery": {
        "name": "其他出库单",
        "alias": ["其他出库", "杂发", "领料", "生产领料"],
        "desc": "除销售出库外的物料出库单据，如生产领料、样品领用等。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName,FStockId.FName,FOutQty,FReason",
        "db_tables": ("InvDoc_MiscShip", "InvDoc_MiscShipL"),
    },

    "STK_Miscellaneous": {
        "name": "其他入库单",
        "alias": ["其他入库", "杂收", "盘盈入库"],
        "desc": "除采购入库外的物料入库单据，如盘盈入库、样品入库等。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName,FStockId.FName,FInQty,FReason",
        "db_tables": ("InvDoc_MiscRcvTrans", "InvDoc_MiscRcvTransL"),
    },

    "STK_TransferDirect": {
        "name": "直接调拨单",
        "alias": ["调拨", "调拨单", "库存调拨", "仓库调拨"],
        "desc": "仓库之间的物料调拨，单据审核后直接更新即时库存。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOutId.FName,FStockInId.FName,FMaterialId.FName,FTransferQty",
        "db_tables": ("InvDoc_TransferForm", "InvDoc_TransferFormL"),
    },

    "STK_Inventory": {
        "name": "即时库存",
        "alias": ["库存", "即时库存", "库存查询", "现存量"],
        "desc": "物料在各仓库的实时库存数量，是出入库业务的结果。",
        "fields": "FMaterialId.FNumber,FMaterialId.FName,FStockId.FName,FStockLocId.FName,FBaseQty,FUnitId.FName",
        "db_tables": ("CBO_ItemQty",),
        "business_rules": {
            "库存冻结": "冻结的库存行不允许出库",
            "批次管理": "有批号的物料出库须指定批号",
        },
    },

    "STK_StockCountInput": {
        "name": "盘点单",
        "alias": ["盘点", "盘点单", "库存盘点", "盘点"],
        "desc": "定期或不定期对仓库物料进行清点，差异生成其他出入库单据。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockId.FName,FInspectorId.FName,FStockTakeStatus",
        "db_tables": ("InvDoc_InventorySheet", "InvDoc_InventorySheetLine"),
    },

    "STK_TransferApply": {
        "name": "调拨申请单",
        "alias": ["调拨申请", "调拨单申请"],
        "desc": "申请仓库之间物料调拨，审核后下推生成调拨单。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSendStockId.FName,FReceiveStockId.FName,FMaterialId.FName,FApplyQty",
        "db_tables": ("InvDoc_TransferApply", "InvDoc_TransApplyLine"),
    },

    "STK_TRANSFERIN": {
        "name": "分布式调入单",
        "alias": ["调入单", "调拨入库", "调拨接收"],
        "desc": "分布式调拨模式下的调入单，由调出单下推生成。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName,FStockId.FName,FInQty",
        "db_tables": ("InvDoc_TransferIn",),
    },

    "STK_TRANSFEROUT": {
        "name": "分布式调出单",
        "alias": ["调出单", "调拨出库", "调拨发出"],
        "desc": "分布式调拨模式下的调出单，审核后下推生成调入单。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName,FStockId.FName,FOutQty",
        "db_tables": ("InvDoc_TransferOut",),
    },

    "STK_AssembledApp": {
        "name": "组装拆卸单",
        "alias": ["组装", "拆卸", "组装拆卸", "拆装"],
        "desc": "将多个物料组装为产成品，或将产成品拆卸为原材料。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockId.FName,FAssembleType,FMaterialId.FName",
        "db_tables": ("MO_SemiMOAssembly", "MO_SemiMOAssemblyLine"),
    },

    "STK_OutStockApply": {
        "name": "出库申请单",
        "alias": ["出库申请", "领料申请"],
        "desc": "物料需要出库时发起的申请，如生产领料申请。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName,FMaterialId.FName,FApplyQty",
        "db_tables": ("Issue_IssueApplyDoc", "Issue_IssueApplyDocLine"),
    },

    "STK_StatusConvert": {
        "name": "形态转换单",
        "alias": ["形态转换", "库存状态", "状态转换"],
        "desc": "物料在仓库内的状态变更（如合格品→不良品），仅更新库存状态不移动数量。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FStockId.FName,FMaterialId.FName,FStatusBefore,FStatusAfter,FConvertQty",
        "db_tables": ("CBO_ItemStatus",),
    },

    # ══════════════════════════════════════════════════════
    # 供应链：质量
    # ══════════════════════════════════════════════════════

    "QIS_InspectBill": {
        "name": "来料检验单",
        "alias": ["来料检验", "质检单", "质量检验", "IQC", "来料质检"],
        "desc": (
            "对采购物料进行质量检验，判断是否允许入库。"
            "来料检验单须关联收料通知单生成；检验结果决定物料入合格品还是不良品库。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPassQty,FFailQty,FInspectResult",
        "db_tables": ("QC_QCDoc", "QC_QCDocLine"),
        "business_rules": {
            "检验结果": "FPassQty=合格数量，FFailQty=不合格数量",
            "合格品入库": "合格物料下推入库单至合格品仓库",
            "不合格处理": "不合格物料需走特采或退货流程",
        },
    },

    # ══════════════════════════════════════════════════════
    # 财务
    # ══════════════════════════════════════════════════════

    "AP_Payable": {
        "name": "应付单",
        "alias": ["应付", "应付单", "应付账款", "采购发票"],
        "desc": "记录企业对供应商的应付账款，由采购入库单下推或手工创建。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FAmount,FCloseStatus",
        "db_tables": ("AP_APBillHead", "AP_APBillLine"),
        "business_rules": {
            "核销": "付款单核销后，采购订单的预付金额会被占用",
            "付款关联": "采购订单被付款单关联后，不可反审核",
        },
    },

    "AR_Receivable": {
        "name": "应收单/收款单",
        "alias": ["应收", "应收单", "收款单", "回款", "应收账款", "营收", "现金回款", "票据回款"],
        "desc": "记录客户应收账款，包含应收金额、已核销金额和核销状态。"
                "是营收、回款、应收余额等财务指标的核心数据来源。"
                "注：不同用友账套字段名可能不同（如 FCUSTOMERID vs FCustId），"
                "先调用 u9_get_fields 确认可用字段。",
        "fields": (
            "FID,FBillNo,FDATE,FDocumentStatus,"
            "FCUSTOMERID.FName,FCUSTOMERID.FNumber,"
            "FALLAMOUNTFOR,FNOTAXAMOUNTFOR,FRELATEHADPAYAMOUNT,"
            "FWRITTENOFFSTATUS,FOPENSTATUS,FENDDATE_H,"
            "FSETTLEORGID.FName,FISINIT"
        ),
        "db_tables": ("AR_ARBillHead", "AR_ARBillLine"),
        "common_filters": [
            "FDocumentStatus='C'                           # 已审核",
            "FDATE>='2026-01-01' and FDATE<='2026-01-31'  # 指定月份",
            "FWRITTENOFFSTATUS='A'                         # 未核销",
            "FOPENSTATUS='A'                               # 未关闭",
            "FISINIT=false                                 # 业务单据（排除期初）",
        ],
    },

    # ══════════════════════════════════════════════════════
    # 二开单据
    # ══════════════════════════════════════════════════════

    "TRNV_Receipt": {
        "name": "二开收款单",
        "alias": ["收款单", "二开收款", "SKD"],
        "desc": "二开定制的收款单（不走标准 AR_Receivable），支持从销售订单或销售订单收款计划下推生成。",
        "fields": "FID,FBillNo,FDocumentStatus,F_TRNV_BusinessDate",
        "db_tables": ("TRNV_t_Cust100002", "TRNV_t_Cust_Entry100007"),
        "entity_key": "FEntity",
        "entry_fields": {
            "TRNV_t_Cust_Entry100007": "FEntryID,F_TRNV_Amount_bh8,F_TRNV_SourceBillType_986,F_TRNV_SourceBillNo_0ev,F_TRNV_ReceiveType,F_TRNV_PONo,F_TRNV_Material,F_TRNV_Qty2,F_TRNV_OriginalPrice,F_TRNV_UnitPrice"
        },
        "business_rules": {
            "源单关联": "F_TRNV_SourceBillNo_0ev 存销售订单号(FBILLNO)；FEntity_Link.STableName ∈ {SM_SOLine(按销售订单分录), SM_SOInstalmentRecTerm(按销售订单收款计划)}",
            "金额字段": "明细收款金额 = F_TRNV_Amount_bh8",
            "已收汇总": "SUM(F_TRNV_Amount_bh8) WHERE FDOCUMENTSTATUS='C' GROUP BY F_TRNV_SourceBillNo_0ev",
            "反写约束": "不走标准 AR 链路，标准收款审核插件不监听本单；销售订单 FRECEIVEDAMOUNT 需自定义审核后插件反写",
            "字段命名": "用友 BOS WebAPI 字段名混合大小写（如 F_TRNV_Amount_bh8），不是全大写",
        },
    },

    "TRNV_PaymentSlip": {
        "name": "二开付款单",
        "alias": ["付款单", "二开付款", "FKD"],
        "desc": "二开定制的付款单（不走标准 AP_Payable），支持从采购订单或采购订单付款计划下推生成。F_TRNV_SONo 用于回挂对应销售订单做毛利闭环。",
        "fields": "FID,FBillNo,FDocumentStatus,F_TRNV_BusinessDate,F_TRNV_Base_hpu",
        "db_tables": ("TRNV_t_Cust100003", "TRNV_t_Cust_Entry100008"),
        "entity_key": "FEntity",
        "entry_fields": {
            "TRNV_t_Cust_Entry100008": "FEntryID,F_TRNV_Amount_bh8,F_TRNV_SourceBillType_986,F_TRNV_SourceBillNo_0ev,F_TRNV_PushDownType,F_TRNV_SONo,F_TRNV_Qty,F_TRNV_MaterialId,F_TRNV_OriginalPrice,F_TRNV_UnitPrice,F_TRNV_WaterBillNumber"
        },
        "business_rules": {
            "源单关联": "F_TRNV_SourceBillNo_0ev 存采购订单号；F_TRNV_SONo 冗余存关联销售订单号(用于毛利闭环对账)",
            "_LK 源表": "FEntity_Link.STableName ∈ {PM_POLine(按订单分录下推), PM_PaymentSchedule(按付款计划下推)}",
            "PushDownType": "1=按付款计划下推(对应 PM_PaymentSchedule)；2/3=按订单分录下推(对应 PM_POLine)",
            "金额字段": "明细付款金额 = F_TRNV_Amount_bh8",
            "反写约束": "不走标准 AP 链路；采购订单已付金额需自定义审核后插件反写",
            "毛利闭环": "同一笔销售：SUM(收款.F_TRNV_Amount_bh8 WHERE F_TRNV_SourceBillNo_0ev=SO号) - SUM(付款.F_TRNV_Amount_bh8 WHERE F_TRNV_SONo=SO号)",
            "字段命名": "用友 BOS WebAPI 字段名混合大小写（如 F_TRNV_Amount_bh8），不是全大写",
        },
    },

    # ══════════════════════════════════════════════════════
    # 委外加工
    # ══════════════════════════════════════════════════════

    "SUB_SubReqOrder": {
        "name": "委外加工订单",
        "alias": ["委外订单", "委外加工", "外协", "CP委外", "WIP", "在制", "委外在制"],
        "desc": (
            "外协生产任务单据，记录 CP 测试、封装、FT 成品测试等工序委托加工情况。"
            "FNoStockInQty 为当前未入库在制量，FPlanFinishDate 为计划完工日。"
            "FStatus 枚举：1=开工，3=完工，6=结案，7=结算。"
            "注：F_XTR_Qty 为晶圆辅单位片数（自定义扩展字段，非用友标准字段）。"
        ),
        "fields": (
            "FID,FBillNo,FDate,FDocumentStatus,FStatus,"
            "FSupplierId.FName,FSupplierId.FNumber,"
            "FTreeEntity_FEntryID,"
            "FMaterialId.FNumber,FMaterialId.FName,FMaterialId.FSpecification,"
            "FQty,FStockInQty,FNoStockInQty,"
            "FPlanFinishDate,FUnitId.FName,"
            "FLot.FNumber,FPurOrderNo"
        ),
        "db_tables": ("MO_MO", "MO_MOSubcontratorList"),
        "common_filters": [
            "FDocumentStatus='C' and FStatus not in ('6','7')   # 已审核未结案（在制）",
            "FPlanFinishDate<GETDATE() and FStatus='1'           # 逾期开工中",
            "FStatus='3'                                         # 已完工待入库",
            "FSupplierId.FName like '%华力%'                     # 指定供应商",
        ],
    },

    # ══════════════════════════════════════════════════════
    # 生产
    # ══════════════════════════════════════════════════════

    "PRD_MO": {
        "name": "生产订单",
        "alias": ["生产订单", "生产单", "MO", "工单", "工单生产"],
        "desc": (
            "生产部门依据生产计划下达的生产任务单，关联物料清单（BOM）和工艺路线。"
            "可下推生成生产领料单、产品入库单。"
        ),
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FMaterialId.FName,FUnitId.FName,FQty,FStockInQty,FPickMtrlQty,FPlanStartDate,FPlanFinishDate",
        "db_tables": ("MO_MO", "MO_MOOutput"),
        "business_rules": {
            "FStockInQty": "累计产品入库数量（产品入库单审核时累加）",
            "FPickMtrlQty": "累计领料数量（生产领料单审核时累加）",
            "汇报投料": "生产汇报时投料数量累加至【累计投料数量】",
        },
    },

    "PRD_PickMtrl": {
        "name": "生产领料单",
        "alias": ["生产领料", "领料单", "领料"],
        "desc": "依据生产订单或工序汇报发起的领料单据，审核时扣减即时库存。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FMaterialId.FName,FStockId.FName,FPickQty,FMoBillNo",
        "db_tables": ("MO_MOPickList", "MO_MOPickListPeriodQty"),
        "business_rules": {
            "审核扣库": "审核时扣减即时库存；反审核时回补库存",
            "超领控制": "超领须经审批后才能继续领料",
        },
    },

    "PRD_Instock": {
        "name": "产品入库单",
        "alias": ["产品入库", "完工入库", "生产入库"],
        "desc": "生产完工的产品入库单据，审核时增加即时库存并更新生产订单。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FMaterialId.FName,FStockId.FName,FInQty,FMoBillNo",
        "db_tables": ("MO_CompleteRpt", "MO_CompleteRptRcvLine"),
    },

    # ══════════════════════════════════════════════════════
    # 费用报销
    # ══════════════════════════════════════════════════════

    "ER_ExpenseRequest": {
        "name": "费用申请单",
        "alias": ["费用申请", "申请单", "事前申请"],
        "desc": "业务发生前的事前费用申请，审核后可作为报销的依据。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FRequestDeptId.FName,FTotalAmount,FExpenseTypeId.FName",
        "db_tables": ("ER_ExpenseRequest",),
    },

    "ER_ExpenseReimburse": {
        "name": "费用报销单",
        "alias": ["费用报销", "报销单", "报销", "事后报销"],
        "desc": "业务发生后的费用报销单据，可关联费用申请单，审核后生成付款单。",
        "fields": "FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FRequestDeptId.FName,FTotalReimAmount,FExpenseTypeId.FName",
        "db_tables": ("ER_ReimburseBillHead", "ER_ReimburseBillDetails"),
        "business_rules": {
            "关联申请": "可关联费用申请单；无申请单的报销须走预算外审批流程",
            "审核后付款": "审核后可下推生成付款单",
        },
    },
}
