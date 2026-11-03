"""api.production"""

from typing import Any

from ._delegates import _get_metadata_validator, _post, _post_raw, _query_payload
from . import mcp
from ..models.query import MRPResultQueryInput, ProductionOrderBillIdsInput, ProductionOrderSaveInput, ProductionPickPushInput, ProductionPlanQueryInput, ProductionReportQueryInput, ProductionStockInPushInput, QueryInput, ViewInput
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt, _rows



@mcp.tool(
    name="u9_query_production_orders",
    annotations={"title": "查询生产订单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_production_orders(params: QueryInput) -> str:
    """查询生产订单（PRD_MO / U9C Service: MODoc）列表。

    常用 filter_string（U9C 字段；旧 F* 别名也可用）：
    - 指定日期: "BusinessDate>='2024-01-01'"
    - 已开工: "IsStartMO=true"
    - 指定物料: "ItemMaster.Code='MAT001'"
    - 指定编号: "DocNo like 'MO%'"

    推荐 field_keys：
    DocNo,BusinessDate,ItemMaster.Code,ItemMaster.Name,ProductQty,StartDate,CompleteDate

    Returns:
        str: JSON 格式的生产订单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "DocNo,BusinessDate,ItemMaster.Code,ItemMaster.Name,ProductQty,StartDate,CompleteDate"
        result = await _post("query", _query_payload(
            "PRD_MO", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_production_pick_materials",
    annotations={"title": "查询生产领料单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_production_pick_materials(params: QueryInput) -> str:
    """查询生产领料单（PRD_PickMtrl / U9C Service: IssueDoc）列表。

    常用 filter_string（U9C 字段；旧 F* 别名也可用）：
    - 已审核: "DocStatus=2"
    - 指定生产订单: "MOs.Code='MO000001'"
    - 指定仓库: "IssueWh.Code='CK001'"

    推荐 field_keys：
    ID,DocNo,BusinessDate,DocStatus,MOs.Code,Item.Code,Item.Name,IssueQty,IssueWh.Name

    Returns:
        str: JSON 格式的生产领料单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "ID,DocNo,BusinessDate,DocStatus,MOs.Code,Item.Code,Item.Name,IssueQty,IssueWh.Name"
        result = await _post("query", _query_payload(
            "PRD_PickMtrl", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_production_stock_in",
    annotations={"title": "查询生产入库单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_production_stock_in(params: QueryInput) -> str:
    """查询生产入库单（PRD_Instock / U9C Service: RcvRptDoc）列表。

    常用 filter_string（U9C 字段；旧 F* 别名也可用）：
    - 指定日期: "BusinessDate>='2024-01-01'"
    - 指定生产订单: "CompleteList.MOKey='MO000001'"
    - 指定仓库: "CompleteList.Wh.Code='CK001'"

    推荐 field_keys：
    DocNo,BusinessDate,Item.Code,Item.Name,CompleteQty,Wh.Name

    Returns:
        str: JSON 格式的生产入库单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "DocNo,BusinessDate,Item.Code,Item.Name,CompleteQty,Wh.Name"
        result = await _post("query", _query_payload(
            "PRD_Instock", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_view_production_order",
    annotations={"title": "查看生产订单详情", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_view_production_order(params: ViewInput) -> str:
    """查看生产订单（PRD_MO / U9C Service: MODoc）完整详情。

    必填参数：
    - form_id: "PRD_MO"（或 U9C Service "MODoc"）
    - bill_id: 单据内码 ID（旧版 FID 也兼容）

    Returns:
        str: JSON 格式的生产订单完整数据
    """
    try:
        result = await _post("view", ["PRD_MO", {"Id": params.bill_id}])
        return _fmt({"form_id": "PRD_MO", "data": result.get("Data", result)})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_save_production_order",
    annotations={"title": "新建或修改生产订单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_save_production_order(params: ProductionOrderSaveInput) -> str:
    """新建或修改生产订单（PRD_MO / U9C Service: MODoc）。

    - 新建：model 不传 ID/FID，调用 ``POST /webapi/MODoc/Create``
    - 修改：model 传 ID（旧版 FID 也兼容），按 MODoc 实际提供的动作处理
    - 字段名使用 U9C MODoc DTO 字段；旧版 F* 会尝试翻译

    新建示例：
    {
      "BusinessDate": "2024-01-15",
      "ItemMaster": {"Code": "MAT001"},
      "ProductQty": 100,
      "StartDate": "2024-01-20",
      "CompleteDate": "2024-01-25"
    }

    Returns:
        str: JSON，含成功状态与 U9C 返回数据
    """
    try:
        model = dict(params.model)
        if model.get("ID") in (None, "", 0, "0") and model.get("FID") in (None, "", 0, "0"):
            model.setdefault("FID", 0)

        # 自动修正字段名（与 u9_save_bill 同口径）：生产订单同样支持元数据纠错
        auto_fixes = []
        unknown_fields = []
        validator = await _get_metadata_validator("PRD_MO")
        if validator:
            model, auto_fixes, unknown_fields = validator.validate_and_fix(model)

        result = await _post_raw(
            "save", "PRD_MO", model,
            need_return_fields=["FID", "FBillNo"],
        )
        status_data = _result_status(result, "save")
        if status_data.get("success"):
            status_data["tip"] = "生产订单已保存为草稿，需要提交+审核后才能下推领料单"
            if auto_fixes:
                status_data["auto_fixes"] = auto_fixes
                status_data["tip"] += f"（自动修正了 {len(auto_fixes)} 处字段名，详见 auto_fixes）"
            if unknown_fields:
                status_data["unknown_fields"] = unknown_fields
                status_data["tip"] += (
                    f"（另有 {len(unknown_fields)} 个字段无法识别、用友可能不认，"
                    f"详见 unknown_fields）"
                )
        else:
            if auto_fixes:
                status_data["auto_fixes"] = auto_fixes
            if unknown_fields:
                status_data["unknown_fields"] = unknown_fields
                status_data["field_hint"] = (
                    "部分字段无法识别（见 unknown_fields），"
                    "请用 u9_get_fields 查生产订单的真实字段名后重试"
                )
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="save")


@mcp.tool(
    name="u9_submit_production_orders",
    annotations={"title": "提交生产订单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_submit_production_orders(params: ProductionOrderBillIdsInput) -> str:
    """提交生产订单（PRD_MO）至审核队列。

    Returns:
        str: JSON，含 success / next_action / bill_ids
    """
    try:
        result = await _post_raw("submit", "PRD_MO", {"Ids": params.bill_ids})
        status_data = _result_status(result, "submit", requested_ids=params.bill_ids)
        if status_data.get("success"):
            status_data["next_action"] = "u9_audit_production_orders"
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="submit")


@mcp.tool(
    name="u9_audit_production_orders",
    annotations={"title": "审核生产订单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_audit_production_orders(params: ProductionOrderBillIdsInput) -> str:
    """审核生产订单（PRD_MO）。

    Returns:
        str: JSON，含 success / bill_ids
    """
    try:
        result = await _post_raw("audit", "PRD_MO", {"Ids": params.bill_ids})
        return _fmt(_result_status(result, "audit", requested_ids=params.bill_ids))
    except Exception as e:
        return _err(e, op="audit")


@mcp.tool(
    name="u9_push_production_pick",
    annotations={"title": "生产订单下推领料单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_push_production_pick(params: ProductionPickPushInput) -> str:
    """从生产订单下推生成生产领料单（PRD_PickMtrl）。

    ⚠️ U9C OpenAPI 没有通用 push 接口；本工具会返回明确的“不支持”错误。
    请在 U9 界面使用单据转换，或先确认该账套是否提供 MODoc/IssueDoc 的
    来源单创建接口（CreateBySrc）。

    Returns:
        str: JSON，含 success / target_bill_nos / next_action
    """
    try:
        push_data: dict[str, Any] = {"TargetFormId": "PRD_PickMtrl", "Numbers": params.bill_nos}
        if params.rule_id:
            push_data["RuleId"] = params.rule_id
        if params.draft_on_fail:
            push_data["IsDraftWhenSaveFail"] = "true"
        result = await _post_raw("push", "PRD_MO", push_data)
        status_data = _result_status(result, "push")
        if status_data.get("success"):
            status_data["next_action"] = "u9_submit_bills + u9_audit_bills"
            status_data["tip"] = "领料单审核时扣减即时库存"
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="push")


@mcp.tool(
    name="u9_push_production_stock_in",
    annotations={"title": "生产领料单下推入库单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_push_production_stock_in(params: ProductionStockInPushInput) -> str:
    """从生产领料单下推生成生产入库单（PRD_Instock）。

    ⚠️ U9C OpenAPI 没有通用 push 接口；本工具会返回明确的“不支持”错误。
    请在 U9 界面使用单据转换，或先确认该账套是否提供对应的来源单创建接口。

    Returns:
        str: JSON，含 success / target_bill_nos / next_action
    """
    try:
        push_data: dict[str, Any] = {"TargetFormId": "PRD_Instock", "Numbers": params.bill_nos}
        if params.rule_id:
            push_data["RuleId"] = params.rule_id
        if params.draft_on_fail:
            push_data["IsDraftWhenSaveFail"] = "true"
        result = await _post_raw("push", "PRD_PickMtrl", push_data)
        status_data = _result_status(result, "push")
        if status_data.get("success"):
            status_data["next_action"] = "u9_submit_bills + u9_audit_bills"
            status_data["tip"] = "入库单审核时增加即时库存"
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="push")


@mcp.tool(
    name="u9_query_mrp_result",
    annotations={"title": "MRP运算结果查询", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_query_mrp_result(params: MRPResultQueryInput) -> str:
    """查询 MRP 运算结果（PLAN_MRPResult）。

    ⚠️ U9C OpenAPI 只有 PlanOrder/Create 写接口，没有计划/MRP 查询 Service/实体；
    默认会返回明确的“无法解析实体”错误。只读统计请用
    ``u9_query_table`` / ``u9_execute_sql``，或通过 ``U9_API_ENTITY_MAP`` 配置账套实体。

    来自销售订单/销售预测/库存不足等需求，经 MRP 运算生成的计划订单建议。
    可下推生成采购申请/生产订单。

    Returns:
        str: JSON 数组，每条含 FBillNo/FMaterialId/FSrcBillNo/FPurchaseQty 等字段。
    """
    try:
        payload = _query_payload("PLAN_MRPResult", "FDetailId,FPlanQty,FBillNo,FMaterialId,FUnitId,FPlanDate,FMoBillNo,FPOBillNo,FPRBillNo,FSourceBillType,FSrcBillNo,FSupplyOrgId,FRequireOrgId,FSupplyDate,FDocumentStatus", params.filter_string, params.orderby, 0, params.top)
        result = await _post("query", payload)
        return _fmt(result)
    except Exception as e:
        return _err(e, op="query")


@mcp.tool(
    name="u9_query_production_plan",
    annotations={"title": "生产计划单查询", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_query_production_plan(params: ProductionPlanQueryInput) -> str:
    """查询生产计划单（PLAN_ProductionPlan）。

    ⚠️ U9C OpenAPI 只有 PlanOrder/Create 写接口，没有计划/MRP 查询 Service/实体；
    默认会返回明确的“无法解析实体”错误。只读统计请用
    ``u9_query_table`` / ``u9_execute_sql``，或通过 ``U9_API_ENTITY_MAP`` 配置账套实体。

    生产计划单是 MRP 运算后手工调整的计划单据，可直接下推生成生产订单。

    Returns:
        str: JSON 数组。
    """
    try:
        payload = _query_payload("PLAN_ProductionPlan", "FBillNo,FMaterialId,FMaterialName,FPlanQty,FPlanStartDate,FPlanEndDate,FStatus,FWorkShopId,FDocumentStatus", params.filter_string, params.orderby, 0, params.top)
        result = await _post("query", payload)
        return _fmt(result)
    except Exception as e:
        return _err(e, op="query")


@mcp.tool(
    name="u9_query_production_report",
    annotations={"title": "生产汇报单查询", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_query_production_report(params: ProductionReportQueryInput) -> str:
    """查询生产汇报单（PRD_MOReport）。

    ⚠️ U9C OpenAPI 只有 WorkCenterOperationRpt/Create 写接口，没有生产汇报单
    查询 Service/实体；默认会返回明确的“无法解析实体”错误。只读统计请用
    ``u9_query_table`` / ``u9_execute_sql``，或通过 ``U9_API_ENTITY_MAP`` 配置账套实体。

    生产汇报记录工序完成数量/工时/良品率等信息，是生产入库的提前工序。

    Returns:
        str: JSON 数组，含 FBillNo/FMOId/FMaterialId/FReportQty/FHourQty 等。
    """
    try:
        payload = _query_payload("PRD_MOReport", "FBillNo,FMOId,FMOBillNo,FMaterialId,FMaterialName,FReportQty,FUnitId,FFinishedQty,FScrapQty,FHourQty,FWorkStationId,FWorkGroupId,FProcessId,FDocumentStatus,FCreateDate", params.filter_string, params.orderby, 0, params.top)
        result = await _post("query", payload)
        return _fmt(result)
    except Exception as e:
        return _err(e, op="query")
