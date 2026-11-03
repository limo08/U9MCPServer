"""api.supply_chain"""

from typing import Any

from ._delegates import _post, _post_raw, _query_payload
from . import mcp
from ..models.query import PushDownInput, QueryInput
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt, _rows



@mcp.tool(
    name="u9_query_sales_outstock",
    annotations={"title": "查询销售出库单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_sales_outstock(params: QueryInput) -> str:
    """查询销售出库单（发货单）。

    对应用友 ApiDoc 销售管理域「销售出库」模块，FormId: SAL_OUTSTOCK。
    用于查询已发货/出库的明细，支持按客户、仓库组织、日期、单据状态筛选。

    ⚠️ 字段 Key 警示（真机实测，2026-08-07）：
    本环境客户字段的元数据 Key 是 **FCustomerID**（大写 ID 后缀），并非 SAL_SaleOrder
    常见的 FCustId，也不是 u9_list_forms 推荐的 FCustId。直接传 FCustId 会报
    「元数据中标识为FCustId的字段不存在」。字段 Key 一律以 u9_get_fields 元数据为准。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定客户: "FCustomerID.FNumber='C001'"
    - 日期区间: "FDate>='2026-05-01' and FDate<='2026-05-31'"

    推荐 field_keys（已按本环境元数据校验可用）：
    FID,FBillNo,FDate,FDocumentStatus,FCustomerID.FName,FStockOrgId.FName
    """
    try:
        form_id = "SAL_OUTSTOCK"
        field_keys = params.field_keys or "FID,FBillNo,FDate,FDocumentStatus,FCustomerID.FName,FStockOrgId.FName"

        payload = [form_id, {
            "FormId": form_id,
            "FieldKeys": field_keys,
            "FilterString": params.filter_string or "",
            "OrderString": params.order_string or "FDate DESC",
            "Limit": params.limit,
            "StartRow": params.start_row
        }]

        result = await _post("query", payload)
        rows = _rows(result)

        return _fmt({
            "form_id": form_id,
            "form_name": "销售出库单",
            "start_row": params.start_row,
            "count": len(rows),
            "has_more": len(rows) >= params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_delivery_notice",
    annotations={"title": "查询发货通知单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_delivery_notice(params: QueryInput) -> str:
    """查询发货通知单。

    对应用友 ApiDoc 销售管理域「发货通知」模块，FormId: SAL_DELIVERYNOTICE。
    用于查询待发货/已发货通知单及其客户信息，支持按客户、日期、单据状态筛选。

    ⚠️ 字段 Key 警示（真机实测，范探源已验证）：
    本账套客户字段的元数据 Key 是 **FCustomerID**（大写 ID 后缀）。误用 FCustId 会报
    「元数据中标识为FCustId的字段不存在」——本环境的 FCustId 在元数据中不存在，切勿改回 FCustId。
    字段 Key 一律以 u9_get_fields 元数据为准。

    ⚠️ 动作范围说明：标准保存/提交/审核动作已由通用 u9_save_bill / u9_submit_bills /
    u9_audit_bills 等按 FormId 参数化覆盖，本工具仅做查询，不负责写操作。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定客户: "FCustomerID.FNumber='C001'"
    - 日期区间: "FDate>='2026-05-01' and FDate<='2026-05-31'"

    推荐 field_keys（已按本环境元数据校验可用）：
    FID,FBillNo,FDate,FDocumentStatus,FCustomerID.FName
    """
    try:
        form_id = "SAL_DELIVERYNOTICE"
        field_keys = params.field_keys or "FID,FBillNo,FDate,FDocumentStatus,FCustomerID.FName"

        payload = [form_id, {
            "FormId": form_id,
            "FieldKeys": field_keys,
            "FilterString": params.filter_string or "",
            "OrderString": params.order_string or "FDate DESC",
            "Limit": params.limit,
            "StartRow": params.start_row
        }]

        result = await _post("query", payload)
        rows = _rows(result)

        return _fmt({
            "form_id": form_id,
            "form_name": "发货通知单",
            "start_row": params.start_row,
            "count": len(rows),
            "has_more": len(rows) >= params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_stock_in",
    annotations={"title": "查询采购入库单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_stock_in(params: QueryInput) -> str:
    """查询采购入库单。

    对应用友 ApiDoc 库存管理域「采购入库」模块，FormId: STK_InStock。
    用于查询已完成/在途的采购入库单及其供应商信息，支持按供应商、仓库、日期、单据状态筛选。

    ⚠️ 字段 Key 警示（真机实测，范探源已验证）：
    本单据业务伙伴是**供应商**，字段 Key 用 **FSupplierId**（注意与销售类单据的 FCustId /
    FCustomerID 不同，采购入库单的客户字段并不存在）。误用 FCustId 会报「字段不存在」。
    字段 Key 一律以 u9_get_fields 元数据为准。

    ⚠️ 动作范围说明：标准保存/提交/审核动作已由通用 u9_save_bill / u9_submit_bills /
    u9_audit_bills 等按 FormId 参数化覆盖，本工具仅做查询，不负责写操作。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定供应商: "FSupplierId.FNumber='V001'"
    - 日期区间: "FDate>='2026-05-01' and FDate<='2026-05-31'"

    推荐 field_keys（已按本环境元数据校验可用）：
    FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName
    """
    try:
        form_id = "STK_InStock"
        field_keys = params.field_keys or "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName"

        payload = [form_id, {
            "FormId": form_id,
            "FieldKeys": field_keys,
            "FilterString": params.filter_string or "",
            "OrderString": params.order_string or "FDate DESC",
            "Limit": params.limit,
            "StartRow": params.start_row
        }]

        result = await _post("query", payload)
        rows = _rows(result)

        return _fmt({
            "form_id": form_id,
            "form_name": "采购入库单",
            "start_row": params.start_row,
            "count": len(rows),
            "has_more": len(rows) >= params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


# ─────────────────────────────────────────────
# SCM 供应链工具
# ─────────────────────────────────────────────

@mcp.tool(
    name="u9_query_purchase_requisitions",
    annotations={"title": "查询采购申请单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_purchase_requisitions(params: QueryInput) -> str:
    """查询采购申请单（PUR_Requisition）列表。

    采购申请单是采购流程的起点，用于向采购部门提出物料或服务采购需求。
    申请单可下推生成采购订单、采购询价单等。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定申请人: "FApplicantId.FNumber='EMP001'"
    - 指定申请部门: "FRequestDeptId.FNumber='D001'"

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FRequestDeptId.FName,FTotalAmount

    Returns:
        str: JSON 格式的采购申请单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FRequestDeptId.FName"
        result = await _post("query", _query_payload(
            "PUR_Requisition", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_quality_inspections",
    annotations={"title": "查询来料检验单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_quality_inspections(params: QueryInput) -> str:
    """查询来料检验单（QIS_InspectBill/IQC）列表。

    来料检验单用于对采购物料进行质量检验，判断是否允许入库。

    常用 filter_string：
    - 已检验: "FDocumentStatus='C'"
    - 检验结果-合格: "FResult='1'" 或 "FPassQty>0"
    - 检验结果-不合格: "FFailQty>0"

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPassQty,FFailQty,FInspectTypeId.FName

    Returns:
        str: JSON 格式的来料检验单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPassQty,FFailQty"
        result = await _post("query", _query_payload(
            "QIS_InspectBill", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_stock_transfer_apply",
    annotations={"title": "查询调拨申请单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_stock_transfer_apply(params: QueryInput) -> str:
    """查询调拨申请单（STK_TransferApply）列表。

    调拨申请单用于申请仓库之间物料的转移，经审核后可下推生成调拨单。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定调出仓库: "FSendStockId.FNumber='WH01'"
    - 指定调入仓库: "FReceiveStockId.FNumber='WH02'"

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FSendStockId.FName,FReceiveStockId.FName

    Returns:
        str: JSON 格式的调拨申请单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FSendStockId.FName,FReceiveStockId.FName"
        result = await _post("query", _query_payload(
            "STK_TransferApply", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_purchase_inquiry",
    annotations={"title": "查询采购询价单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_purchase_inquiry(params: QueryInput) -> str:
    """查询采购询价单（SVM_InquiryBill/RFQ）列表。

    ⚠️ U9C OpenAPI 未提供采购询价单的 Service/实体；默认会返回明确的
    “无法解析实体”错误。只读统计请用 ``u9_query_table`` / ``u9_execute_sql``，
    或通过 ``U9_API_ENTITY_MAP`` 配置账套自定义实体。

    采购询价单（Request for Quotation）用于向供应商询价，收集报价信息。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定供应商: "FSupplierId.FNumber='S001'"

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPrice

    Returns:
        str: JSON 格式的询价单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName"
        result = await _post("query", _query_payload(
            "SVM_InquiryBill", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_supplier_quotes",
    annotations={"title": "查询供应商报价单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_supplier_quotes(params: QueryInput) -> str:
    """查询供应商报价单（SVM_QuoteBill）列表。

    ⚠️ U9C OpenAPI 未提供供应商报价单的 Service/实体；默认会返回明确的
    “无法解析实体”错误。只读统计请用 ``u9_query_table`` / ``u9_execute_sql``，
    或通过 ``U9_API_ENTITY_MAP`` 配置账套自定义实体。

    供应商报价单是供应商对询价单的响应，包含物料价格信息。
    可用于比价分析，选择最优供应商。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定供应商: "FSupplierId.FNumber='S001'"
    - 指定物料: "FMaterialId.FNumber='MAT001'"

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPrice,FQuantity

    Returns:
        str: JSON 格式的报价单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FID,FBillNo,FDate,FDocumentStatus,FSupplierId.FName,FMaterialId.FName,FPrice"
        result = await _post("query", _query_payload(
            "SVM_QuoteBill", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)




# ─────────────────────────────────────────────
# 杂项出入库和调拨工具
# ─────────────────────────────────────────────

@mcp.tool(
    name="u9_query_misc_movement_detail",
    annotations={"title": "查询杂项出入库明细表", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_misc_movement_detail(params: QueryInput) -> str:
    """查询杂项出入库明细表（STK_MiscMovementDetail）。

    ⚠️ U9C OpenAPI 提供 MiscRcvTrans/MiscShip 写接口，但没有杂项出入库明细
    查询 Service/实体；默认会返回明确的“无法解析实体”错误。只读统计请用
    ``u9_query_table`` / ``u9_execute_sql``，或通过 ``U9_API_ENTITY_MAP`` 配置实体。

    用于查看杂项出入库的明细数据，包括其他入库、其他出库等。

    常用 filter_string：
    - 指定日期范围: "FBillDate>='2024-01-01' and FBillDate<='2024-12-31'"
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定仓库: "FStockId.FNumber='WH01'"

    推荐 field_keys（默认已包含关键字段）：
    FID,FBillNo,FBillDate,FDocumentStatus,FStockOrgId.FName,
    FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FQty,FPrice,FAmount

    Returns:
        str: JSON 格式的杂项出入库明细列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else (
                "FID,FBillNo,FBillDate,FDocumentStatus,FStockOrgId.FName,"
                "FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,"
                "FQty,FPrice,FAmount"
            )
        result = await _post("query", _query_payload(
            "STK_MiscMovementDetail", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "form_id": "STK_MiscMovementDetail",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_transfer_pending_detail",
    annotations={"title": "查询分步式调出未调入明细", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_transfer_pending_detail(params: QueryInput) -> str:
    """查询分步式调出未调入明细表（STK_TransferPendingDetail）。

    ⚠️ U9C OpenAPI 提供 TransferOut/TransferIn 写接口，但没有“已调出未调入”
    明细查询 Service/实体；默认会返回明确的“无法解析实体”错误。只读统计请用
    ``u9_query_table`` / ``u9_execute_sql``，或通过 ``U9_API_ENTITY_MAP`` 配置实体。

    用于查看分步式调拨流程中，已调出但未调入的单据明细。

    常用 filter_string：
    - 指定调出日期范围: "FOutDate>='2024-01-01' and FOutDate<='2024-12-31'"
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定调出仓库: "FOutStockId.FNumber='WH01'"

    推荐 field_keys（默认已包含关键字段）：
    FID,FBillNo,FOutDate,FInDate,FDocumentStatus,FStockOrgId.FName,
    FOutStockId.FName,FInStockId.FName,FMaterialId.FNumber,FMaterialId.FName,
    FUnitId.FName,FOutQty,FInQty,FPendingQty

    Returns:
        str: JSON 格式的分步式调出未调入明细列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else (
                "FID,FBillNo,FOutDate,FInDate,FDocumentStatus,FStockOrgId.FName,"
                "FOutStockId.FName,FInStockId.FName,FMaterialId.FNumber,FMaterialId.FName,"
                "FUnitId.FName,FOutQty,FInQty,FPendingQty"
            )
        result = await _post("query", _query_payload(
            "STK_TransferPendingDetail", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "form_id": "STK_TransferPendingDetail",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_transfer_apply",
    annotations={"title": "查询调拨申请单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_transfer_apply(params: QueryInput) -> str:
    """查询调拨申请单（STK_TransferApply）列表。

    调拨申请单是调拨业务的起点，可下推生成直接调拨单或分步式调拨单。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定日期范围: "FBillDate>='2024-01-01' and FBillDate<='2024-12-31'"
    - 指定调出仓库: "FOutStockId.FNumber='WH01'"
    - 指定调入仓库: "FInStockId.FNumber='WH02'"
    - 未关闭: "FCloseStatus='A' and FBusinessClose='A'"

    推荐 field_keys（默认已包含关键字段）：
    FID,FBillNo,FBillDate,FDocumentStatus,FStockOrgId.FName,
    FOutStockId.FName,FInStockId.FName,FTransferType,
    FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FQty,FPrice,FAmount

    Returns:
        str: JSON 格式的调拨申请单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else (
                "FID,FBillNo,FBillDate,FDocumentStatus,FStockOrgId.FName,"
                "FOutStockId.FName,FInStockId.FName,FTransferType,"
                "FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FQty,FPrice,FAmount"
            )
        result = await _post("query", _query_payload(
            "STK_TransferApply", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "form_id": "STK_TransferApply",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_transfer_direct",
    annotations={"title": "查询直接调拨单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_transfer_direct(params: QueryInput) -> str:
    """查询直接调拨单（STK_TransferDirect）列表。

    直接调拨单用于一步完成调拨业务，同时更新调出仓和调入仓库存。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定日期范围: "FBillDate>='2024-01-01' and FBillDate<='2024-12-31'"
    - 指定调出仓库: "FOutStockId.FNumber='WH01'"
    - 指定调入仓库: "FInStockId.FNumber='WH02'"
    - 未关闭: "FCloseStatus='A' and FBusinessClose='A'"

    推荐 field_keys（默认已包含关键字段）：
    FID,FBillNo,FBillDate,FDocumentStatus,FStockOrgId.FName,
    FOutStockId.FName,FInStockId.FName,FMaterialId.FNumber,
    FMaterialId.FName,FUnitId.FName,FQty,FPrice,FAmount

    Returns:
        str: JSON 格式的直接调拨单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else (
                "FID,FBillNo,FBillDate,FDocumentStatus,FStockOrgId.FName,"
                "FOutStockId.FName,FInStockId.FName,FMaterialId.FNumber,"
                "FMaterialId.FName,FUnitId.FName,FQty,FPrice,FAmount"
            )
        result = await _post("query", _query_payload(
            "STK_TransferDirect", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({
            "form_id": "STK_TransferDirect",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_push_stock_transfer",
    annotations={"title": "调拨申请下推调拨单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_push_stock_transfer(params: PushDownInput) -> str:
    """从调拨申请单下推到直接调拨单（STK_TransferApply -> STK_TransferDirect）。

    用于将调拨申请单下推生成直接调拨单，一步完成调拨。

    参数说明：
    - form_id: 固定为 STK_TransferApply（调拨申请单）
    - target_form_id: 固定为 STK_TransferDirect（直接调拨单）
    - source_bill_nos: 调拨申请单的单据编号列表

    转换规则说明：
    - 默认（rule_id=空）：使用系统配置的默认转换规则
    - enable_default_rule=true：强制启用默认下推规则
    - rule_id 显式指定：绕过默认规则，使用指定规则

    响应包含：
    - Result.ResponseStatus：保存结果（IsSuccess 判断整体是否成功）
    - Result.ConvertResponseStatus：每行下推转换结果

    Returns:
        str: JSON，含 success / bill_nos / next_action 字段
    """
    try:
        push_data: dict[str, Any] = {
            "TargetFormId": "STK_TransferDirect",
            "Numbers": params.source_bill_nos,
        }
        if params.rule_id:
            push_data["RuleId"] = params.rule_id
        if params.enable_default_rule:
            push_data["IsEnableDefaultRule"] = "true"
        if params.draft_on_fail:
            push_data["IsDraftWhenSaveFail"] = "true"
        result = await _post_raw("push", "STK_TransferApply", push_data)
        status_data = _result_status(result, "push")
        rs = result.get("Result", result) if isinstance(result, dict) else {}
        numbers = rs.get("Numbers", [])
        ids = rs.get("Ids", [])
        if status_data.get("success"):
            status_data["source_bill_nos"] = params.source_bill_nos
            status_data["target_form_id"] = "STK_TransferDirect"
            if numbers:
                status_data["target_bill_nos"] = numbers
            if ids:
                status_data["target_fids"] = ids if isinstance(ids, list) else [ids]
            status_data["tip"] = (
                f"已生成 {len(numbers)} 张直接调拨单，"
                "请依次调用 u9_submit_bills + u9_audit_bills 完成提交和审核"
            )
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="push")
