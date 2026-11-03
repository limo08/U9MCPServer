"""api.logs"""


from ._delegates import _post, _query_payload
from . import mcp
from ..models.system import ApprovalFlowInput, AuditLogInput, ChangeLogInput, DataBackupInput, OperationLogInput, PermissionChangeInput
from ..utils.errors import _err
from ..utils.formatting import _escape_sql_like, _fmt, _rows



@mcp.tool(
    name="u9_query_audit_log",
    annotations={"title": "查询审计日志", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_audit_log(params: AuditLogInput) -> str:
    """查询用友U9的审计日志（BOS_AuditLog）。

    ⚠️ U9C OpenAPI 未开放该日志的 Service/实体；默认会返回明确的“无法解析实体”错误。
    可通过 ``U9_API_ENTITY_MAP`` 指向账套中实际存在的实体，或改用数据库只读查询
    （``u9_query_table`` / ``u9_execute_sql``）。

    记录单据的审核操作：谁在什么时候审核了哪张单据、审核结果是什么。
    用于合规审计、审批追溯、反舞弊检查。

    推荐场景：
    - 合规要求：保留所有审核操作的审计轨迹
    - 问题排查：某张单据的审核历史
    - 责任追溯：谁在什么时间通过了/驳回了审批

    返回字段说明：
    - FCREATEDATE: 审核时间
    - FCREATORID: 审核人
    - FOBJECTID: 单据内码
    - FFORMID: 单据类型
    - FAUDITRESULT: 审核结果（通过/驳回/取消）
    - FMEMO: 审核意见

    Returns:
        str: JSON 格式的审计日志列表
    """
    try:
        conditions = []
        if params.form_id:
            conditions.append(f"FFORMID = '{params.form_id}'")
        if params.bill_id:
            conditions.append(f"FOBJECTID = '{params.bill_id}'")
        if params.bill_no:
            conditions.append(f"FOBJECTNO like '%{_escape_sql_like(params.bill_no)}%'")
        if params.user_name:
            conditions.append(f"FCREATORID like '%{_escape_sql_like(params.user_name)}%'")
        if params.start_date:
            conditions.append(f"FCREATEDATE > '{params.start_date} 00:00:00'")
        if params.end_date:
            conditions.append(f"FCREATEDATE < '{params.end_date} 23:59:59'")
        if params.result and params.result != "all":
            result_map = {"pass": "通过", "reject": "驳回", "cancel": "取消"}
            result_val = result_map.get(params.result, params.result)
            conditions.append(f"FAUDITRESULT like '%{result_val}%'")
        if params.filter_string:
            conditions.append(params.filter_string)

        filter_str = " and ".join(conditions) if conditions else ""

        result = await _post("query", _query_payload(
            "BOS_AuditLog",
            "FID,FCREATEDATE,FCREATORID,FOBJECTID,FFORMID,FOBJECTNO,FAUDITRESULT,FMEMO",
            filter_str,
            params.order_string,
            params.start_row,
            params.limit
        ))
        rows = _rows(result)

        return _fmt({
            "form_id": "BOS_AuditLog",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "filter_summary": {
                "form_id": params.form_id or "全部",
                "bill_id": params.bill_id,
                "bill_no": params.bill_no,
                "user_name": params.user_name,
                "date_range": f"{params.start_date or '~'} ~ {params.end_date or '至今'}",
                "result": params.result or "全部",
            },
            "data": rows,
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_operation_logs",
    annotations={"title": "查询操作日志", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_operation_logs(params: OperationLogInput) -> str:
    """查询用友U9的上机操作日志（BOS_OperateLog）。

    ⚠️ U9C OpenAPI 未开放该日志的 Service/实体；默认会返回明确的“无法解析实体”错误。
    可通过 ``U9_API_ENTITY_MAP`` 指向账套中实际存在的实体，或改用数据库只读查询
    （``u9_query_table`` / ``u9_execute_sql``）。

    记录用户在系统中的所有操作：登录、登出、进入业务对象、业务操作等。
    用于安全审计、故障排查、操作追溯。

    推荐场景：
    - 排查某张单据是谁在什么时候操作的
    - 安全审计：检查异常登录或批量操作
    - 合规要求：追溯敏感操作记录

    返回字段说明：
    - FDATETIME: 操作时间
    - FUSERID: 操作用户
    - FCOMPUTERNAME: 机器名称
    - FCLIENTIP: 客户端IP
    - FENVIRONMENT: 操作场景（0=登入系统, 1=进入业务对象, 3=业务操作, 4=登出系统）
    - FOPERATENAME: 操作名称（登录/单据查询/批量保存等）
    - FDESCRIPTION: 操作描述
    - FInterId: 对象内码（关联单据号）
    - FTimeConsuming: 耗时(毫秒)
    - FClientType: 客户端类型

    Returns:
        str: JSON 格式的操作日志列表
    """
    try:
        conditions = []
        if params.user_name:
            conditions.append(f"FUSERID like '%{_escape_sql_like(params.user_name)}%'")
        if params.start_date:
            conditions.append(f"FDATETIME > '{params.start_date} 00:00:00'")
        if params.end_date:
            conditions.append(f"FDATETIME < '{params.end_date} 23:59:59'")
        if params.operate_type:
            conditions.append(f"FOPERATENAME like '%{_escape_sql_like(params.operate_type)}%'")
        if params.bill_no:
            conditions.append(f"FInterId like '%{_escape_sql_like(params.bill_no)}%'")
        if params.form_name:
            conditions.append(f"FDESCRIPTION like '%{_escape_sql_like(params.form_name)}%'")
        if params.filter_string:
            conditions.append(params.filter_string)

        filter_str = " and ".join(conditions) if conditions else ""

        result = await _post("query", _query_payload(
            "BOS_OperateLog",
            "FID,FDATETIME,FUSERID,FCOMPUTERNAME,FCLIENTIP,FENVIRONMENT,FOPERATENAME,FDESCRIPTION,FInterId,FTimeConsuming,FClientType",
            filter_str,
            params.order_string,
            params.start_row,
            params.limit
        ))
        rows = _rows(result)

        date_range = f"{params.start_date or '~'} ~ {params.end_date or '至今'}" if params.start_date or params.end_date else "全部"

        return _fmt({
            "form_id": "BOS_OperateLog",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "filter_summary": {
                "user_name": params.user_name,
                "date_range": date_range,
                "operate_type": params.operate_type or "全部",
                "bill_no": params.bill_no,
            },
            "data": rows,
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_change_log",
    annotations={"title": "查询变更记录", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_change_log(params: ChangeLogInput) -> str:
    """查询用友U9的单据变更记录（BOS_ModifyLog）。

    ⚠️ U9C OpenAPI 未开放该日志的 Service/实体；默认会返回明确的“无法解析实体”错误。
    可通过 ``U9_API_ENTITY_MAP`` 指向账套中实际存在的实体，或改用数据库只读查询
    （``u9_query_table`` / ``u9_execute_sql``）。

    记录单据字段的修改历史：谁在什么时候修改了什么字段、从什么值改成了什么值。
    用于数据变更追溯、合规审计、问题排查。

    推荐场景：
    - 数据治理：追踪关键字段的变更历史
    - 问题排查：某张单据的修改记录
    - 合规要求：保留重要数据的修改轨迹

    返回字段说明：
    - FCREATEDATE: 修改时间
    - FCREATORID: 修改人
    - FOBJECTID: 单据内码
    - FFIELDNAME: 字段名称
    - FOLDVALUE: 修改前的值
    - FNEWVALUE: 修改后的值

    Returns:
        str: JSON 格式的变更记录列表
    """
    try:
        conditions = []
        if params.form_id:
            conditions.append(f"FFORMID = '{params.form_id}'")
        if params.bill_id:
            conditions.append(f"FOBJECTID = '{params.bill_id}'")
        if params.bill_no:
            conditions.append(f"FOBJECTNO like '%{_escape_sql_like(params.bill_no)}%'")
        if params.user_name:
            conditions.append(f"FCREATORID like '%{_escape_sql_like(params.user_name)}%'")
        if params.start_date:
            conditions.append(f"FCREATEDATE > '{params.start_date} 00:00:00'")
        if params.end_date:
            conditions.append(f"FCREATEDATE < '{params.end_date} 23:59:59'")
        if params.field_name:
            conditions.append(f"FFIELDNAME like '%{_escape_sql_like(params.field_name)}%'")
        if params.filter_string:
            conditions.append(params.filter_string)

        filter_str = " and ".join(conditions) if conditions else ""

        result = await _post("query", _query_payload(
            "BOS_ModifyLog",
            "FID,FCREATEDATE,FCREATORID,FOBJECTID,FFORMID,FOBJECTNO,FFIELDNAME,FOLDVALUE,FNEWVALUE",
            filter_str,
            params.order_string,
            params.start_row,
            params.limit
        ))
        rows = _rows(result)

        return _fmt({
            "form_id": "BOS_ModifyLog",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "filter_summary": {
                "form_id": params.form_id or "全部",
                "bill_id": params.bill_id,
                "bill_no": params.bill_no,
                "user_name": params.user_name,
                "field_name": params.field_name,
                "date_range": f"{params.start_date or '~'} ~ {params.end_date or '至今'}",
            },
            "data": rows,
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_approval_flow",
    annotations={"title": "查询审批流程", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_approval_flow(params: ApprovalFlowInput) -> str:
    """查询用友U9的审批流程记录。

    ⚠️ U9C OpenAPI 未开放该日志的 Service/实体；默认会返回明确的“无法解析实体”错误。
    可通过 ``U9_API_ENTITY_MAP`` 指向账套中实际存在的实体，或改用数据库只读查询
    （``u9_query_table`` / ``u9_execute_sql``）。

    记录单据从提交到最终审核的完整审批轨迹，包括每个节点的审批人、时间、结果和意见。
    用于审批追溯、流程优化、合规检查。

    推荐场景：
    - 审批追溯：某张单据走过了哪些审批节点
    - 流程优化：分析审批时长和瓶颈
    - 合规检查：确认关键单据是否按流程审批

    注意：用友审批流程数据可能存储在多个表单中，
    如 V_SFA_ApprovalRecord（审批记录）、Workflow_Instance（流程实例）等。
    如查询无结果，请用 u9_get_fields 查看实际可用字段。

    Returns:
        str: JSON 格式的审批流程列表
    """
    try:
        conditions = []
        conditions.append(f"FFORMID = '{params.form_id}'")
        if params.bill_id:
            conditions.append(f"FOBJECTID = '{params.bill_id}'")
        if params.bill_no:
            conditions.append(f"FOBJECTNO like '%{_escape_sql_like(params.bill_no)}%'")
        if params.start_date:
            conditions.append(f"FCREATEDATE > '{params.start_date} 00:00:00'")
        if params.end_date:
            conditions.append(f"FCREATEDATE < '{params.end_date} 23:59:59'")
        if params.status and params.status != "all":
            status_map = {
                "pending": "审批中",
                "approved": "已通过",
                "rejected": "已驳回",
            }
            status_val = status_map.get(params.status, params.status)
            conditions.append(f"FRESULT like '%{status_val}%'")
        if params.filter_string:
            conditions.append(params.filter_string)

        filter_str = " and ".join(conditions) if conditions else ""

        result = await _post("query", _query_payload(
            "V_SFA_ApprovalRecord",
            "FID,FCREATEDATE,FCREATORID,FOBJECTID,FFORMID,FOBJECTNO,FNODEID,FNODENAME,FAPPROVERID,"
            "FAPPROVERNAME,FAPPROVEDATE,FRESULT,FOPINION,FREMARK",
            filter_str,
            params.order_string,
            params.start_row,
            params.limit
        ))
        rows = _rows(result)

        if not rows:
            result = await _post("query", _query_payload(
                "Workflow_Instance",
                "FID,FCREATEDATE,FUSERID,FFORMID,FObjectId,FObjectNo,FWorkflowId,FWorkflowName,"
                "FNodeId,FNodeName,FApproverId,FApproverName,FApproveDate,FResult,FOpinion",
                filter_str,
                params.order_string,
                params.start_row,
                params.limit
            ))
            rows = _rows(result)

        return _fmt({
            "form_id": "V_SFA_ApprovalRecord / Workflow_Instance",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "filter_summary": {
                "form_id": params.form_id,
                "bill_id": params.bill_id,
                "bill_no": params.bill_no,
                "status": params.status,
                "date_range": f"{params.start_date or '~'} ~ {params.end_date or '至今'}",
            },
            "data": rows,
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_permission_changes",
    annotations={"title": "查询权限变更", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_permission_changes(params: PermissionChangeInput) -> str:
    """查询用友U9的权限变更记录。

    ⚠️ U9C OpenAPI 未开放该日志的 Service/实体；默认会返回明确的“无法解析实体”错误。
    可通过 ``U9_API_ENTITY_MAP`` 指向账套中实际存在的实体，或改用数据库只读查询
    （``u9_query_table`` / ``u9_execute_sql``）。

    记录用户权限的授予、撤销、修改操作。
    用于安全审计、合规检查、权限追溯。

    推荐场景：
    - 安全审计：谁在什么时候被授予/撤销了什么权限
    - 合规要求：保留权限变更的审计轨迹
    - 问题排查：某用户无法访问某功能的原因

    注意：用友权限数据可能存储在多个表单中，
    如 SEC_Permission（权限记录）、SEC_UserRole（用户角色关系）等。
    如查询无结果，请用 u9_get_fields 查看实际可用字段。

    Returns:
        str: JSON 格式的权限变更列表
    """
    try:
        conditions = []
        if params.user_name:
            conditions.append(f"FUSERNAME like '%{_escape_sql_like(params.user_name)}%'")
        if params.target_type:
            conditions.append(f"FTARGETTYPE like '%{_escape_sql_like(params.target_type)}%'")
        if params.object_type:
            conditions.append(f"FOBJECTTYPE like '%{_escape_sql_like(params.object_type)}%'")
        if params.object_name:
            conditions.append(f"FOBJECTNAME like '%{_escape_sql_like(params.object_name)}%'")
        if params.action:
            conditions.append(f"FACTION like '%{_escape_sql_like(params.action)}%'")
        if params.start_date:
            conditions.append(f"FCREATEDATE > '{params.start_date} 00:00:00'")
        if params.end_date:
            conditions.append(f"FCREATEDATE < '{params.end_date} 23:59:59'")
        if params.filter_string:
            conditions.append(params.filter_string)

        filter_str = " and ".join(conditions) if conditions else ""

        result = await _post("query", _query_payload(
            "SEC_Permission",
            "FID,FCREATEDATE,FCREATORID,FUSERNAME,FTARGETTYPE,FOBJECTTYPE,FOBJECTID,FOBJECTNAME,FACTION,FPRIVILEGE",
            filter_str,
            params.order_string,
            params.start_row,
            params.limit
        ))
        rows = _rows(result)

        if not rows:
            result = await _post("query", _query_payload(
                "SEC_UserRole",
                "FID,FCREATEDATE,FCREATORID,FUSERID,FUSERNAME,FROLEID,FROLENAME,FACTION",
                filter_str,
                params.order_string,
                params.start_row,
                params.limit
            ))
            rows = _rows(result)

        return _fmt({
            "form_id": "SEC_Permission / SEC_UserRole",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "filter_summary": {
                "user_name": params.user_name,
                "target_type": params.target_type,
                "object_type": params.object_type,
                "object_name": params.object_name,
                "action": params.action,
                "date_range": f"{params.start_date or '~'} ~ {params.end_date or '至今'}",
            },
            "data": rows,
        })
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_data_backup",
    annotations={"title": "查询数据备份记录", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_data_backup(params: DataBackupInput) -> str:
    """查询用友U9的数据备份记录。

    ⚠️ U9C OpenAPI 未开放该日志的 Service/实体；默认会返回明确的“无法解析实体”错误。
    可通过 ``U9_API_ENTITY_MAP`` 指向账套中实际存在的实体，或改用数据库只读查询
    （``u9_query_table`` / ``u9_execute_sql``）。

    记录系统的数据备份和恢复操作。
    用于灾备验证、合规检查、恢复演练。

    推荐场景：
    - 灾备验证：确认备份是否按计划执行
    - 合规要求：保留备份操作的审计轨迹
    - 恢复演练：查找可用的备份点

    注意：用友备份数据可能存储在系统配置表或其他后台表单中，
    如需访问请确认当前用户有系统管理权限。
    如查询无结果，请用 u9_get_fields 查看实际可用字段。

    Returns:
        str: JSON 格式的数据备份记录列表
    """
    try:
        conditions = []
        if params.backup_type:
            conditions.append(f"FBACKUPTYPE like '%{_escape_sql_like(params.backup_type)}%'")
        if params.status:
            conditions.append(f"FSTATUS like '%{_escape_sql_like(params.status)}%'")
        if params.operator:
            conditions.append(f"FOPERATOR like '%{_escape_sql_like(params.operator)}%'")
        if params.start_date:
            conditions.append(f"FBACKUPDATE > '{params.start_date} 00:00:00'")
        if params.end_date:
            conditions.append(f"FBACKUPDATE < '{params.end_date} 23:59:59'")
        if params.filter_string:
            conditions.append(params.filter_string)

        filter_str = " and ".join(conditions) if conditions else ""

        result = await _post("query", _query_payload(
            "DB_BackupRecord",
            "FID,FBACKUPDATE,FOPERATOR,FBACKUPTYPE,FSTATUS,FBACKUPFILE,FBACKUPSIZE,FREMARK",
            filter_str,
            params.order_string,
            params.start_row,
            params.limit
        ))
        rows = _rows(result)

        if not rows:
            result = await _post("query", _query_payload(
                "T_BAS_BackupRecord",
                "FID,FCREATEDATE,FCREATORID,FOPERATOR,FBACKUPTYPE,FSTATUS,FPATH,FSIZE",
                filter_str,
                params.order_string,
                params.start_row,
                params.limit
            ))
            rows = _rows(result)

        return _fmt({
            "form_id": "DB_BackupRecord / T_BAS_BackupRecord",
            "count": len(rows),
            "has_more": len(rows) == params.limit,
            "filter_summary": {
                "backup_type": params.backup_type or "全部",
                "status": params.status or "全部",
                "operator": params.operator,
                "date_range": f"{params.start_date or '~'} ~ {params.end_date or '至今'}",
            },
            "data": rows,
        })
    except Exception as e:
        return _err(e)
