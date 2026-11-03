"""api.finance"""


from ._delegates import _post, _query_payload
from . import mcp
from ..models.query import QueryInput, SaveInput
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt, _rows



@mcp.tool(
    name="u9_query_expense_reimburse",
    annotations={"title": "查询费用报销单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_expense_reimburse(params: QueryInput) -> str:
    """查询费用报销单。

    专门用于查询费用报销单据，支持按状态、金额、日期筛选。

    Returns:
        str: JSON 格式的费用报销单列表
    """
    try:
        form_id = "ER_ExpenseReimburse"
        field_keys = params.field_keys or "FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FTotalReimAmount,FDescription"

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
            "form_name": "费用报销单",
            "start_row": params.start_row,
            "count": len(rows),
            "has_more": len(rows) >= params.limit,
            "data": rows
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_loan_balance",
    annotations={"title": "查询借款余额", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_loan_balance(params: QueryInput) -> str:
    """查询历史借款余额（人人报销域）。

    对应用友 ApiDoc「人人报销 → 历史借款余额」模块，FormId: ER_HistoricalLoanBalance。
    用于查询员工/部门的借款余额快照，支持按状态、申请人、日期筛选。

    ⚠️ 环境注意：该单据在部分账套（如芯之蝶测试账套 <ACCT_ID>）未启用，
    u9_get_fields 会返回「未知表单」。本工具代码已就绪，待目标账套启用该模块后即可连真机使用；
    字段 Key 以用友标准元数据为准，若实测报「字段不存在」请先用 u9_get_fields 复核。

    推荐 field_keys：
    FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FEmployeeId.FName,FLoanAmount,FRepaidAmount,FUnRepayAmount
    """
    try:
        form_id = "ER_HistoricalLoanBalance"
        field_keys = params.field_keys or "FID,FBillNo,FDate,FDocumentStatus,FApplicantId.FName,FEmployeeId.FName,FLoanAmount,FRepaidAmount,FUnRepayAmount"

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
            "form_name": "历史借款余额",
            "start_row": params.start_row,
            "count": len(rows),
            "has_more": len(rows) >= params.limit,
            "data": rows,
            "env_note": "目标账套若未启用 ER_HistoricalLoanBalance，查询会返回空或报错，需启用模块后使用"
        })
    except Exception as e:
        return _err(e)


# ─────────────────────────────────────────────
# 资产管理工具
# ─────────────────────────────────────────────

@mcp.tool(name="u9_query_fixed_asset", annotations={"title": "查询固定资产", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def u9_query_fixed_asset(params: QueryInput) -> str:
    """查询固定资产卡片主数据（FA_FAGet / U9C Service: AssetCard）。
    固定资产是企业长期使用的有形资产，如房屋、机器设备、运输工具等。
    支持按资产编号、名称、状态、使用部门等条件筛选。

    ⚠️ U9C OpenAPI 的 AssetCard Service 未提供 Query 动作，规范里也没有
    AssetCard 实体全名；未通过 ``U9_API_ENTITY_MAP`` 配置实体时会返回明确错误。
    可改用数据库只读查询（u9_query_table / u9_execute_sql）。

    常用 filter_string：
    - 已审核: "DocStatus=2"
    - 指定资产编号: "Code='FA001'"
    - 指定使用部门: "Department.Code='D001'"
    推荐 field_keys（以 u9_get_fields 结果为准）：
    ID,Code,Name,Specification,OriginalAmount,AccumDepreciation,NetAmount,DocStatus
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" else "FID,FNumber,FName,FAssetSource,FSpecification,FUsedPeriod,FOriginalAmount,FDepreciateRate,FUseDeptId.FName,FDocumentStatus,FStatus"
        result = await _post("query", _query_payload("FA_FAGet", fk, params.filter_string, params.order_string, params.start_row, params.limit))
        return _fmt({"form_id": "FA_FAGet", "count": len(_rows(result)), "data": _rows(result)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="u9_query_asset_card", annotations={"title": "查询资产卡片", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def u9_query_asset_card(params: QueryInput) -> str:
    """查询资产卡片（FA_FAGet / U9C Service: AssetCard）。
    资产卡片是固定资产的详细记录，包含原值、累计折旧、净值、卡片状态等信息。

    ⚠️ U9C AssetCard 未提供 Query 动作；未配置 ``U9_API_ENTITY_MAP`` 时会
    返回明确的实体解析错误，可改用数据库只读查询。

    常用 filter_string：
    - 指定资产编号: "Code='FA001'"
    - 已审核: "DocStatus=2"
    - 已计提折旧: "AccumDepreciation>0"
    推荐 field_keys（以 u9_get_fields 结果为准）：
    ID,Code,Name,OriginalAmount,AccumDepreciation,NetAmount,UsefulLife,DocStatus
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" else "FID,FNumber,FName,FAssetSource,FOriginalAmount,FTotalDepreciate,FNetAmount,FDepreciateMonth,FUsefulLife,FSalvageValue,FCustodian.FName"
        result = await _post("query", _query_payload("FA_FAGet", fk, params.filter_string, params.order_string, params.start_row, params.limit))
        return _fmt({"form_id": "FA_FAGet", "count": len(_rows(result)), "data": _rows(result)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="u9_query_asset_depreciation", annotations={"title": "查询资产折旧记录", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def u9_query_asset_depreciation(params: QueryInput) -> str:
    """查询资产折旧记录（FA_DepreciationBill）。

    ⚠️ U9C OpenAPI 未提供该资产单据的查询 Service/实体。
    未通过 ``U9_API_ENTITY_MAP`` 配置实体时会返回明确错误；只读统计请用
    ``u9_query_table`` / ``u9_execute_sql``。
    折旧记录是固定资产计提折旧的明细，反映每月折旧费用、累计折旧、净值变化。
    常用 filter_string：
    - 指定期间: "FYear=2024 and FPeriod=3"
    - 指定资产: "FAssetId.FNumber='FA001'"
    推荐 field_keys：
    FID,FYear,FPeriod,FAssetId.FNumber,FAssetId.FName,FDepreciateDeptId.FName,FDepreciateAmount,FOriginalAmount,FTotalDepreciate,FNetAmount
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" else "FID,FYear,FPeriod,FAssetId.FNumber,FAssetId.FName,FDepreciateDeptId.FName,FDepreciateAmount,FOriginalAmount,FTotalDepreciate,FNetAmount"
        result = await _post("query", _query_payload("FA_DepreciationBill", fk, params.filter_string, params.order_string, params.start_row, params.limit))
        return _fmt({"form_id": "FA_DepreciationBill", "count": len(_rows(result)), "data": _rows(result)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="u9_save_asset", annotations={"title": "新增或修改固定资产", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def u9_save_asset(params: SaveInput) -> str:
    """新增或修改固定资产（FA_FAGet / U9C Service: AssetCard）。

    - 新建对应 ``POST /webapi/AssetCard/Create``，单据保存后需提交+审核；
    - U9C AssetCard 未开放 Modify 查询实体；修改/查询请先确认账套是否提供
      对应实体，可通过 ``U9_API_ENTITY_MAP`` 覆盖。
    - `model` 使用 U9C DTO 字段名；旧版 F* 字段会尝试翻译。

    Returns:
        str: JSON，含 success / message / data
    """
    try:
        result = await _post("save", [params.form_id, {"Model": params.model, "NeedUpdateFields": params.need_update_fields, "IsDeleteEntry": params.is_delete_entry}])
        return _fmt(_result_status(result, "save"))
    except Exception as e:
        return _err(e, op="save")


@mcp.tool(name="u9_query_asset_transfer", annotations={"title": "查询资产调拨单", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def u9_query_asset_transfer(params: QueryInput) -> str:
    """查询资产调拨单（FA_Transfer）。

    ⚠️ U9C OpenAPI 仅提供 AlterDoc 的 Create/Submit/Approve 写接口，没有
    资产变更查询实体。未通过 ``U9_API_ENTITY_MAP`` 配置实体时会返回明确错误；
    只读统计请用 ``u9_query_table`` / ``u9_execute_sql``。
    资产调拨记录固定资产在部门或使用人之间的转移。
    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定资产: "FAssetId.FNumber='FA001'"
    - 原使用部门: "FOldDeptId.FNumber='D001'"
    推荐 field_keys：
    FID,FBillNo,FTransferDate,FDocumentStatus,FAssetId.FNumber,FAssetId.FName,FOldDeptId.FName,FNewDeptId.FName,FTransferReason
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" else "FID,FBillNo,FTransferDate,FDocumentStatus,FAssetId.FNumber,FAssetId.FName,FOldDeptId.FName,FNewDeptId.FName,FTransferReason"
        result = await _post("query", _query_payload("FA_Transfer", fk, params.filter_string, params.order_string, params.start_row, params.limit))
        return _fmt({"form_id": "FA_Transfer", "count": len(_rows(result)), "data": _rows(result)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="u9_query_asset_scrape", annotations={"title": "查询资产报废单", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def u9_query_asset_scrape(params: QueryInput) -> str:
    """查询资产报废单（FA_Scrape）。

    ⚠️ U9C OpenAPI 仅提供 AlterDoc 的 Create/Submit/Approve 写接口，没有
    资产变更查询实体。未通过 ``U9_API_ENTITY_MAP`` 配置实体时会返回明确错误；
    只读统计请用 ``u9_query_table`` / ``u9_execute_sql``。
    资产报废记录固定资产的处置，包括正常报废、提前报废、毁损等。
    常用 filter_string：
    - 已审核: "FDocumentStatus='C'"
    - 指定资产: "FAssetId.FNumber='FA001'"
    - 报废类型: "FScrapeType='NORMAL'"
    推荐 field_keys：
    FID,FBillNo,FScrapeDate,FDocumentStatus,FAssetId.FNumber,FAssetId.FName,FOriginalAmount,FTotalDepreciate,FNetAmount,FScrapeType,FHandleMethod
    """
    try:
        fk = params.field_keys if params.field_keys != "FID,FBillNo,FDate,FDocumentStatus" else "FID,FBillNo,FScrapeDate,FDocumentStatus,FAssetId.FNumber,FAssetId.FName,FOriginalAmount,FTotalDepreciate,FNetAmount,FScrapeType,FHandleMethod"
        result = await _post("query", _query_payload("FA_Scrape", fk, params.filter_string, params.order_string, params.start_row, params.limit))
        return _fmt({"form_id": "FA_Scrape", "count": len(_rows(result)), "data": _rows(result)})
    except Exception as e:
        return _err(e)
