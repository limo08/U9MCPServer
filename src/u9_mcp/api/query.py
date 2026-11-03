"""api.query"""


from ._delegates import _post, _post_query, _post_raw, _query_payload
from . import mcp
from ..models.query import InventoryQueryInput, MaterialQueryInput, OutsourceOrderQueryInput, PartnerQueryInput, PurchaseOrderProgressInput, QueryInput, ReceiptQueryInput, ViewInput
from ..services.bill_ops import _simplify_view_result
from ..utils.errors import _err
from ..utils.formatting import _fmt, _rows



# ─────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────

@mcp.tool(
    name="u9_query_bills",
    annotations={"title": "通用单据查询", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_bills(params: QueryInput) -> str:
    """查询 U9C 任意单据/基础资料列表，支持过滤、排序和分页。

    适用 form_id 示例：PUR_PurchaseOrder（采购订单）、SAL_SaleOrder（销售订单）、
    STK_InStock（采购入库）、SAL_OUTSTOCK（销售出库）、STK_MisDelivery（其他出库）。

    字段名建议使用 U9C 名称（如 ``ID`` / ``DocNo`` / ``BusinessDate`` /
    ``Supplier.Code``），可用 ``u9_get_fields`` 查询。旧版 ``F*`` 别名
    （``FID`` / ``FBillNo`` / ``FDate`` / ``FSupplierId.FNumber``）仍会被翻译，
    便于从旧配置迁移。

    查询由 ``POST /webapi/CommonEntity/Query`` 执行；字符串过滤语法仍兼容
    ``"DocStatus='A' and BusinessDate>='2026-01-01'"``。

    Returns:
        str: JSON，含 form_id / count / has_more / data 字段；
             发生字段翻译或自动降级时额外带 notice 字段说明
    """
    try:
        result, notice = await _post_query(
            params.form_id, params.field_keys, params.filter_string,
            params.order_string, params.start_row, params.limit
        )
        rows = _rows(result)
        out = {
            "form_id": params.form_id, "start_row": params.start_row,
            "count": len(rows), "has_more": len(rows) == params.limit, "data": rows,
        }
        if notice:
            out["notice"] = notice
        return _fmt(out)
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_view_bill",
    annotations={"title": "查看单据详情", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_view_bill(params: ViewInput) -> str:
    """根据单据内码 ID 获取单据详情。

    内部按 U9C 实体查询该 ID 对应的记录（默认返回字段含主表与分录字段）。
    mode=summary（默认）：关联对象只保留 Id / Number / Name，大幅缩减体积；
    mode=full：返回 U9C 原始 JSON。

    Returns:
        str: JSON 格式的单据数据
    """
    try:
        # View 使用 _post_raw（raw JSON body + 小写 formid，无 Model 包装）
        result = await _post_raw("view", params.form_id, {"Id": params.bill_id})
        if params.mode == "full":
            return _fmt(result)
        return _fmt(_simplify_view_result(result))
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_purchase_orders",
    annotations={"title": "查询采购订单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_purchase_orders(params: QueryInput) -> str:
    """查询采购订单（PUR_PurchaseOrder / U9C Service: PurchaseOrder）列表。

    常用 filter_string（U9C 字段；旧 F* 别名也可用）：
    - 指定供应商: "Supplier.Code='S001'"
    - 指定日期: "BusinessDate>='2026-01-01' and BusinessDate<='2026-12-31'"
    - 单据状态: "DocStatus='A'"（具体枚举以 U9C 单据状态为准）

    推荐字段：ID,DocNo,BusinessDate,DocStatus,Supplier.Name,Department.Name,
    TaxAmount,TotalAmount,ReceiveQty,StockInQty

    注：不同账套/二开单据字段可能不同；请用 u9_get_fields 或
    u9_list_forms 确认该环境真实可用字段。

    关联数量业务规则：
    - 关联数量 = 累计收料数量 + 累计入库数量
    - 关联数量 >= 订单数量时，采购订单无法下推收料单/入库单
    - 勾选控制交货数量时，关联数量 >= 交货下限时无法下推

    Returns:
        str: JSON 格式的采购订单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else (
                "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,"
                "FPurchaseDeptId.FName,FTaxAmount,FAllAmount,"
                "FReceiveQty,FStockInQty"
                # FLinkQty/FBusinessClose 在 demo 环境可能不存在，请用 u9_get_fields 确认
            )
        result = await _post("query", _query_payload(
            "PUR_PurchaseOrder", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_purchase_order_progress",
    annotations={"title": "查询采购订单执行进度", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_purchase_order_progress(params: PurchaseOrderProgressInput) -> str:
    """查询采购订单行明细及执行进度（含累计收料/入库数量）。

    与 u9_query_purchase_orders 的区别：
    - 本工具查询【表体分录级】字段，返回每行物料的详细执行情况
    - 默认返回已审核单据，可通过 filter_string 过滤

    返回的关键字段（demo 账套实测）：
    - FBillNo: 单据编号
    - FMaterialId.FNumber / FMaterialId.FName: 物料编码/名称
    - FQty: 订单数量
    - FReceiveQty: 累计收料数量
    - FStockInQty: 累计入库数量
    - FPrice: 单价（不含税）
    - FTaxPrice: 含税单价
    - FAllAmount: 价税合计

    以下字段需启用供应链模块后才存在（demo 环境可能不存在）：
    - FLinkQty: 关联数量（=累计收料数量+累计入库数量）
    - FBusinessClose: 业务关闭状态（A=正常，B=业务关闭）
    - FFreezeStatus: 冻结状态（A=正常，B=冻结）
    - FTerminateStatus: 终止状态（A=正常，B=终止）
    - FDlyCntl_Low / FDlyCntl_High: 交货下限/上限

    业务关闭规则（需启用供应链）：
    - 累计入库数量 >= 交货下限时，该行自动【业务关闭】
    - 累计入库数量 < 交货下限时，自动【业务反关闭】

    Returns:
        str: JSON 格式的采购订单执行进度列表
    """
    try:
        # 注：FLinkQty/FBusinessClose/FFreezeStatus/FTerminateStatus/FDlyCntl_* 在 demo 环境可能不存在
        # 如遇字段不存在错误，请用 u9_get_fields(form_id='PUR_PurchaseOrder') 确认
        field_keys = (
            "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,"
            "FMaterialId.FNumber,FMaterialId.FName,"
            "FQty,FReceiveQty,FStockInQty,"
            "FPrice,FTaxPrice,FAllAmount"
        )
        result = await _post("query", _query_payload(
            "PUR_PurchaseOrder", field_keys,
            params.filter_string or "FDocumentStatus='C'",
            "FBillNo DESC,FPOOrderEntry_LineID ASC",
            params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "tip": (
                "FLinkQty=关联数量（=FReceiveQty+FStockInQty），"
                "FLinkQty>=FQty时无法下推；"
                "累计入库数量>=交货下限时该行自动业务关闭"
            ),
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_sale_orders",
    annotations={"title": "查询销售订单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_sale_orders(params: QueryInput) -> str:
    """查询销售订单（SAL_SaleOrder）列表。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定客户: "FCustId.FNumber='C001'"

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FSalesOrgId.FName,FTotalAmount

    Returns:
        str: JSON 格式的销售订单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FCustId.FName,FTotalAmount"
        result = await _post("query", _query_payload(
            "SAL_SaleOrder", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_sale_quotations",
    annotations={"title": "查询销售报价单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_sale_quotations(params: QueryInput) -> str:
    """查询销售报价单（SAL_Quotation）列表。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定客户: "FCUSTID.FNumber='C001'"
    - 未失效: "FExpiryDate>='2026-01-01'"

    推荐 field_keys（默认已包含关键字段）：
    FID,FBillNo,FDate,FDocumentStatus,FCUSTID.FName,FSalerId.FName,FExpiryDate

    注（本环境为二开定制，与标准字段不同）：
    - 销售员字段为 FSalerId（非标准 FSalesmanId），写 FSalesmanId 会 500
    - 主表无 FTotalAmount（金额在分录 FQUOTATIONFIN 内），如需金额请用
      u9_query_bills 指定分录字段，或用 u9_get_fields 确认可用字段

    Returns:
        str: JSON 格式的销售报价单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else (
                "FID,FBillNo,FDate,FDocumentStatus,"
                "FCUSTID.FName,FSalerId.FName,FExpiryDate"
            )
        result = await _post("query", _query_payload(
            "SAL_Quotation", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_stock_bills",
    annotations={"title": "查询出入库单据", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_stock_bills(params: QueryInput) -> str:
    """查询出入库相关单据。

    form_id 常用取值：
    - STK_InStock:        采购入库单
    - SAL_OUTSTOCK:       销售出库单
    - STK_MisDelivery:    其他出库单
    - STK_Miscellaneous:  其他入库单
    - STK_TransferDirect: 直接调拨单

    Returns:
        str: JSON 格式的出入库单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FStockOrgId.FName"
        result = await _post("query", _query_payload(
            params.form_id, fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"form_id": params.form_id, "count": len(rows), "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_inventory",
    annotations={"title": "查询即时库存", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_inventory(params: InventoryQueryInput) -> str:
    """查询即时库存数量（STK_Inventory）。

    常用 filter_string：
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定仓库: "FStockId.FNumber='WH01'"
    - 有库存:   "FBaseQty>0"（默认已设置）

    Returns:
        str: JSON 格式的库存列表，含物料编码、名称、仓库、数量、单位
    """
    try:
        result = await _post("query", _query_payload(
            "STK_Inventory", params.field_keys, params.filter_string,
            "FMaterialId.FNumber ASC", params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_outsource_orders",
    annotations={"title": "查询委外加工订单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_outsource_orders(params: OutsourceOrderQueryInput) -> str:
    """查询委外加工订单（SUB_SubReqOrder）列表。

    委外加工订单记录外协生产任务，包含 CP 测试、封装、FT 成品测试等工序
    的委托加工情况，是 WIP 在制量、逾期分析、回货预测的核心数据来源。

    常用 filter_string：
    - 在制（未结案）：  "FDocumentStatus='C' and FStatus not in ('6','7')"（默认）
    - 指定供应商：     "FSupplierId.FName like '%华力%'"
    - 逾期未完工：     "FPlanFinishDate<GETDATE() and FStatus not in ('3','6','7')"
    - 30 天内到期：    "FPlanFinishDate>=GETDATE() and FPlanFinishDate<=DATEADD(day,30,GETDATE())"
    - 指定批次：       "FLot.FNumber='AP5E047'"
    - 指定产品型号：   "FMaterialId.FSpecification='APT32F004B'"
    - 已完工待入库：   "FStatus='3'"

    关键字段说明：
    - FQty：           委外订单总数量（颗）
    - FStockInQty：    已入库数量（已完工回厂的数量）
    - FNoStockInQty：  未入库在制量（FQty - FStockInQty，可为负表示超收）
    - FStatus：        执行状态（1=开工，3=完工，6=结案，7=结算）
    - FPlanFinishDate：计划完工日（逾期判断基准）
    - FPurOrderNo：    关联采购订单号（CP 委外专用，可反查晶圆来源采购单）
    - FLot.FNumber：   批次号（WIP 追溯用）
    - F_XTR_Qty：      晶圆辅单位片数（自定义扩展字段，如需可追加到 field_keys）

    💡 REMEMBER: 若报"字段不存在"，用 u9_get_fields('SUB_SubReqOrder') 确认该账套可用字段

    Returns:
        str: JSON，含 count / has_more / data 字段
    """
    try:
        result = await _post("query", _query_payload(
            "SUB_SubReqOrder", params.field_keys, params.filter_string,
            "FPlanFinishDate ASC,FBillNo ASC", params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows,
        })
    except Exception as e:
        return _err(e, op="query_outsource_orders")


@mcp.tool(
    name="u9_query_receipts",
    annotations={"title": "查询收款单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_receipts(params: ReceiptQueryInput) -> str:
    """查询应收单（AR_Receivable）列表，支持按客户、日期、核销状态、打开状态过滤。

    应收单记录客户应收账款，包含应收金额、已核销金额、核销状态等信息，
    是营收、回款、应收余额、票据占比等财务指标的核心数据来源。

    常用 filter_string：
    - 已审核：        "FDocumentStatus='C'"（默认）
    - 指定客户：      "FCUSTOMERID.FNumber='C001'"
    - 指定月份：      "FDATE>='2026-01-01' and FDATE<='2026-01-31'"
    - 未核销：        "FWRITTENOFFSTATUS='A'"
    - 未关闭：        "FOPENSTATUS='A'"
    - 期初数据：      "FISINIT=true"（初始化单）或 "FISINIT=false"（业务单）

    关键字段说明：
    - FALLAMOUNTFOR：     应收总金额（原币含税），财务核心指标
    - FNOTAXAMOUNTFOR：   应收不含税金额（原币），用于综合毛利率计算
    - FRELATEHADPAYAMOUNT：已核销金额
    - FWRITTENOFFSTATUS： 核销状态（A=未核销，B=部分核销，C=完全核销）
    - FOPENSTATUS：       打开状态（A=未关闭，B=已关闭，C=部分关闭）
    - FENDDATE_H：        到期日
    - FISINIT：           是否为初始化单据（期初数据）

    ⚠️ 不同用友账套字段名可能不同（如 FCUSTOMERID 可能为 FCustId、FDate 可能为 FDATE），
    先调用 u9_get_fields('AR_Receivable') 确认该账套可用字段。

    Returns:
        str: JSON，含 count / has_more / data 字段
    """
    try:
        result = await _post("query", _query_payload(
            "AR_Receivable", params.field_keys, params.filter_string,
            "FDATE DESC,FBillNo DESC", params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows,
        })
    except Exception as e:
        return _err(e, op="query_receipts")


@mcp.tool(
    name="u9_query_materials",
    annotations={"title": "查询物料档案", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_materials(params: MaterialQueryInput) -> str:
    """查询物料基础资料（BD_Material）。

    常用 filter_string：
    - 按编码前缀: "FNumber like 'HG%'"
    - 按名称模糊: "FName like '%钢板%'"
    - 已审核启用: "FDocumentStatus='C'"

    Returns:
        str: JSON 格式的物料列表，含编码、名称、规格、单位、物料分组
    """
    try:
        result = await _post("query", _query_payload(
            "BD_Material", params.field_keys, params.filter_string,
            "FNumber ASC", params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_partners",
    annotations={"title": "查询客户或供应商", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_partners(params: PartnerQueryInput) -> str:
    """查询客户（BD_Customer）或供应商（BD_Supplier）基础资料。

    partner_type 取值：BD_Customer 或 BD_Supplier

    Returns:
        str: JSON 格式的客户/供应商列表，含编码、名称、简称、联系人、电话
    """
    try:
        result = await _post("query", _query_payload(
            params.partner_type, params.field_keys, params.filter_string,
            "FNumber ASC", params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"type": params.partner_type, "count": len(rows), "data": rows})
    except Exception as e:
        return _err(e)
