"""api.report"""


from ._delegates import _post
from . import mcp
from ..models.query import ReportQueryInput
from ..utils.errors import _err
from ..utils.formatting import _fmt



@mcp.tool(
    name="u9_query_report",
    annotations={"title": "财务报表/账表导出（U9C PDF）", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_report(params: ReportQueryInput) -> str:
    """通过 U9C OpenAPI 导出财务报表/账表 PDF。

    端点：``POST /webapi/Report/GetReportPdfFile``
    请求体 ``GetReportPdfFileReq``，二选一：
    - ``ReportCaseID``：报表用例 ID（推荐，先用本参数或 ``data`` 传入）
    - ``SubscirbeReportName``：U9 中订阅的报表名称（注意 U9C 原字段拼写为
      ``SubscirbeReportName``，不是 Subscribe）

    params.data 可显式指定上述字段：
      ``{"ReportCaseID": "..."}`` 或 ``{"SubscirbeReportName": "..."}``
    若 data 为空，则把 params.form_id 作为 ReportCaseID。

    返回：U9C 原始 JSON ``FileResult``，其中 ``FileName`` 为文件名、
    ``FileContentBase64`` 为 PDF 内容（Base64）。U9C 该接口**不返回结构化表格行**；
    如需明细数据，请用 u9_query_bills 查询业务单据，或在上游解码 PDF。

    Returns:
        str: JSON（含 FileName / FileContentBase64）；失败为错误 JSON
    """
    try:
        result = await _post("report", (params.form_id, params.data or {}))
        return _fmt(result)
    except Exception as e:
        return _err(e, op="report")
