"""api.cost"""


from ._delegates import _post, _post_raw, _query_payload
from . import mcp
from ..config import u9c_catalog
from ..models.query import QueryInput, SaveInput
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt, _rows



@mcp.tool(
    name="u9_query_material_cost",
    annotations={"title": "查询物料成本库", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_material_cost(params: QueryInput) -> str:
    """查询物料成本库（BD_MaterialCost）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    返回物料的标准成本、最新成本、平均成本等信息。

    常用 filter_string：
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定成本组织: "FCostOrgId.FNumber='100'"

    推荐 field_keys：
    FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FStdCost,FLatestCost,FAvgCost

    Returns:
        str: JSON 格式的物料成本列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FStdCost,FLatestCost,FAvgCost"
        result = await _post("query", _query_payload(
            "BD_MaterialCost", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_material_target_cost",
    annotations={"title": "查询物料目标成本单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_material_target_cost(params: QueryInput) -> str:
    """查询物料目标成本单（BD_MatTargetCost）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定物料: "FMaterialId.FNumber='MAT001'"

    推荐 field_keys：
    FBillNo,FDate,FDocumentStatus,FMaterialId.FNumber,FMaterialId.FName,FTargetCost

    Returns:
        str: JSON 格式的目标成本单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FBillNo,FDate,FDocumentStatus,FMaterialId.FNumber,FMaterialId.FName,FTargetCost"
        result = await _post("query", _query_payload(
            "BD_MatTargetCost", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_cost_calculation",
    annotations={"title": "查询成本计算单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_cost_calculation(params: QueryInput) -> str:
    """查询成本计算单（CB_CostCalBill）列表。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 指定年度: "FYear=2024"
    - 指定期间: "FPeriod='01'"
    - 指定物料: "FMaterialId.FNumber='MAT001'"

    推荐 field_keys：
    FYear,FPeriod,FMaterialId.FNumber,FMaterialId.FName,FCostAmt,FMaterialCost,FLabourCost

    Returns:
        str: JSON 格式的成本计算单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FYear,FPeriod,FMaterialId.FNumber,FMaterialId.FName,FCostAmt,FMaterialCost,FLabourCost"
        result = await _post("query", _query_payload(
            "CB_CostCalBill", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_cost_centers",
    annotations={"title": "查询成本中心", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_cost_centers(params: QueryInput) -> str:
    """查询成本中心基础资料（CB_CostCenter）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 指定编码: "FNumber like 'CC%'"
    - 启用状态: "FIsActive='1'"

    推荐 field_keys：
    FNumber,FName,FDeptId.FName,FIsActive

    Returns:
        str: JSON 格式的成本中心列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FNumber,FName,FDeptId.FName,FIsActive"
        result = await _post("query", _query_payload(
            "CB_CostCenter", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_cost_items",
    annotations={"title": "查询成本项目", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_cost_items(params: QueryInput) -> str:
    """查询成本项目基础资料（CB_CostItem）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 指定编码: "FNumber like 'CI%'"
    - 成本项目类型: "FCostItemType='1'"

    推荐 field_keys：
    FNumber,FName,FCostItemType,FIsActive

    Returns:
        str: JSON 格式的成本项目列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FNumber,FName,FCostItemType,FIsActive"
        result = await _post("query", _query_payload(
            "CB_CostItem", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_product_standard_cost",
    annotations={"title": "查询产品标准成本", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_product_standard_cost(params: QueryInput) -> str:
    """查询产品标准成本（STD_ProductCostQuery）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定成本版本: "FCostVersionId.FNumber='STD01'"

    推荐 field_keys：
    FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FStdCost,FMaterialCost,FLabourCost,FFeeCost

    Returns:
        str: JSON 格式的产品标准成本列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FMaterialId.FNumber,FMaterialId.FName,FUnitId.FName,FStdCost,FMaterialCost,FLabourCost,FFeeCost"
        result = await _post("query", _query_payload(
            "STD_ProductCostQuery", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_cost_adjustments",
    annotations={"title": "查询成本调整单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_cost_adjustments(params: QueryInput) -> str:
    """查询成本调整单（STK_CostAdjust）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定调整类型: "FAdjustType='1'"

    推荐 field_keys：
    FBillNo,FDate,FDocumentStatus,FCostOrgId.FNumber,FCostOrgId.FName,FAdjustType,FAdjustAmount

    Returns:
        str: JSON 格式的成本调整单列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FBillNo,FDate,FDocumentStatus,FCostOrgId.FNumber,FCostOrgId.FName,FAdjustType,FAdjustAmount"
        result = await _post("query", _query_payload(
            "STK_CostAdjust", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_save_cost_adjustment",
    annotations={"title": "保存成本调整单", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_save_cost_adjustment(params: SaveInput) -> str:
    """新建或修改成本调整单（STK_CostAdjust）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    model 示例：
    {
      "FDate": "2024-01-15",
      "FCostOrgId": {"FNumber": "100"},
      "FAdjustType": "1",
      "FCostAdjustEntry": [
        {"FMaterialId": {"FNumber": "MAT001"}, "FAdjustQty": 100, "FAdjustPrice": 10.5}
      ]
    }

    Returns:
        str: JSON，含 FID 和 FBillNo
    """
    try:
        if not u9c_catalog.has_service("STK_CostAdjust"):
            return _fmt({
                "op": "save",
                "success": False,
                "unsupported": True,
                "form_id": "STK_CostAdjust",
                "error": "U9C OpenAPI 未提供成本调整单的 Service/DTO，无法通过接口保存。",
                "next_action": (
                    "请在 U9 客户端录入成本调整单；只读统计可使用 "
                    "u9_query_table / u9_execute_sql。"
                ),
            })
        model = dict(params.model)
        if model.get("ID") in (None, "", 0, "0") and model.get("FID") in (None, "", 0, "0"):
            model.setdefault("FID", 0)
        result = await _post_raw(
            "save", "STK_CostAdjust", model,
            need_return_fields=["FID", "FBillNo"],
        )
        status_data = _result_status(result, "save")
        if status_data.get("success"):
            status_data["tip"] = "成本调整单已保存，需要提交+审核后才能生效"
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="save")


@mcp.tool(
    name="u9_query_instant_cost_compare",
    annotations={"title": "即时成本对比分析", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_instant_cost_compare(params: QueryInput) -> str:
    """查询即时成本对比分析表（STK_InstantCostCompare）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    对比即时成本与核算成本的差异。

    常用 filter_string：
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定仓库: "FStockId.FNumber='WH01'"

    推荐 field_keys：
    FMaterialId.FNumber,FMaterialId.FName,FStockId.FName,FInstantCost,F核算成本,FDiffAmt

    Returns:
        str: JSON 格式的即时成本对比列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FMaterialId.FNumber,FMaterialId.FName,FStockId.FName,FInstantCost,FCostPrice,FDiffAmt"
        result = await _post("query", _query_payload(
            "STK_InstantCostCompare", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_cost_trend",
    annotations={"title": "成本价趋势分析", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_cost_trend(params: QueryInput) -> str:
    """查询成本价趋势分析表（STK_CostTrend）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    分析物料成本价格的变化趋势。

    常用 filter_string：
    - 指定物料: "FMaterialId.FNumber='MAT001'"
    - 指定日期范围: "FDate>='2024-01-01' and FDate<='2024-12-31'"

    推荐 field_keys：
    FMaterialId.FNumber,FMaterialId.FName,FDate,FCostPrice,FPriceChange

    Returns:
        str: JSON 格式的成本价趋势列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FMaterialId.FNumber,FMaterialId.FName,FDate,FCostPrice,FPriceChange"
        result = await _post("query", _query_payload(
            "STK_CostTrend", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_finished_product_cost",
    annotations={"title": "完工入库成本查询", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_finished_product_cost(params: QueryInput) -> str:
    """查询完工入库产品成本（CB_FinishInCostQuery）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 指定生产订单: "FMoBillNo='MO000001'"
    - 指定期间: "FYear=2024 and FPeriod='01'"

    推荐 field_keys：
    FMoBillNo,FMaterialId.FNumber,FMaterialId.FName,FFinishQty,FCostPrice,FCostAmt

    Returns:
        str: JSON 格式的完工成本列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FMoBillNo,FMaterialId.FNumber,FMaterialId.FName,FFinishQty,FCostPrice,FCostAmt"
        result = await _post("query", _query_payload(
            "CB_FinishInCostQuery", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_material_cost_usage",
    annotations={"title": "材料耗用成本查询", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_material_cost_usage(params: QueryInput) -> str:
    """查询生产材料耗用成本（CB_MaterialCostQuery）。

    ⚠️ U9C OpenAPI 未提供成本类 Service/实体；默认会返回明确的“无法解析实体”错误。
    如账套自定义了 U9C 接口，可通过 ``U9_API_ENTITY_MAP`` 映射 form_id 后使用；
    否则请改用数据库只读查询（``u9_query_table`` / ``u9_execute_sql``）。

    常用 filter_string：
    - 指定生产订单: "FMoBillNo='MO000001'"
    - 指定物料: "FMaterialId.FNumber='MAT001'"

    推荐 field_keys：
    FMoBillNo,FMaterialId.FNumber,FMaterialId.FName,FConsumeQty,FCostPrice,FCostAmt

    Returns:
        str: JSON 格式的材料耗用成本列表
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" \
            else "FMoBillNo,FMaterialId.FNumber,FMaterialId.FName,FConsumeQty,FCostPrice,FCostAmt"
        result = await _post("query", _query_payload(
            "CB_MaterialCostQuery", fk, params.filter_string,
            params.order_string, params.start_row, params.limit
        ))
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)
