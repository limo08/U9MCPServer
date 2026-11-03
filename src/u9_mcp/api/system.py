"""api.system"""

from typing import Any, List

from ._delegates import _get_metadata_validator, _post_system
from . import mcp
from ..config import u9c_catalog
from ..config.form_catalog import FORM_CATALOG
from ..models.system import FieldQueryInput, FormOperationListInput, FormSearchInput, NumberRuleQueryInput, PermissionQueryInput, RoleQueryInput, SequenceQueryInput, SystemConfigInput, UserQueryInput
from ..services.bill_ops import _list_form_operations
from ..services.metadata import FieldDef
from ..utils.errors import _err
from ..utils.formatting import _fmt, _rows



@mcp.tool(
    name="u9_query_user",
    annotations={"title": "查询用户", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_user(params: UserQueryInput) -> str:
    """查询 U9C 用户列表。

    对应 U9C Service：``UserInfo`` / 实体 ``UFIDA.U9.CBO.Sys.UserInfo``。

    常用 filter_string（U9C 字段名）：
    - 指定账号: "Code='user001'"
    - 姓名: "Name like '%张%'"
    - 有效状态: "Effective=true"

    推荐 field_keys：
    ID,Code,Name,DisplayName,Contact,UserGroup,IsAlive,Effective

    Returns:
        str: JSON 格式的用户列表
    """
    try:
        result = await _post_system("user", "BD_User", params.field_keys, params.filter_string, params.start_row, params.limit)
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_role",
    annotations={"title": "查询角色", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_role(params: RoleQueryInput) -> str:
    """查询角色列表（U9C OpenAPI 未开放独立角色 Service）。

    U9C 规范没有 ``BD_Role`` 或对应的 CommonEntity 实体，因此默认会返回明确的
    不支持错误；如账套已通过 ``U9_API_ENTITY_MAP`` 配置角色实体，则可查询。

    Returns:
        str: JSON；未配置实体时为错误说明
    """
    try:
        result = await _post_system("role", "BD_Role", params.field_keys, params.filter_string, params.start_row, params.limit)
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_permission",
    annotations={"title": "查询权限", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_permission(params: PermissionQueryInput) -> str:
    """查询权限列表（U9C OpenAPI 未开放独立权限 Service）。

    U9C 的权限授权在管理端维护，OpenAPI 没有 ``SYS_Permission`` 等价实体；
    默认返回明确的不支持错误。可通过 ``U9_API_ENTITY_MAP`` 配置实际实体后重试。

    Returns:
        str: JSON；未配置实体时为错误说明
    """
    try:
        result = await _post_system("permission", "SYS_Permission", params.field_keys, params.filter_string, params.start_row, params.limit)
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_sequence",
    annotations={"title": "查询编码规则", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_sequence(params: SequenceQueryInput) -> str:
    """查询编码规则（U9C OpenAPI 未开放独立 SequenceRule Service）。

    U9C 的编号规则由服务端业务/管理端维护，OpenAPI 没有 ``SYS_SequenceRule``
    等价实体；默认返回明确的不支持错误。可通过 ``U9_API_ENTITY_MAP`` 配置
    实际实体后重试。

    Returns:
        str: JSON；未配置实体时为错误说明
    """
    try:
        result = await _post_system("sequence", "SYS_SequenceRule", params.field_keys, params.filter_string, params.start_row, params.limit)
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_number_rule",
    annotations={"title": "查询单据编号规则", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_number_rule(params: NumberRuleQueryInput) -> str:
    """查询单据编号规则（U9C OpenAPI 未开放独立 NumberRule Service）。

    U9C 的单据编号由服务端在保存时生成，OpenAPI 没有 ``SYS_NumberRule``
    等价实体；默认返回明确的不支持错误。可通过 ``U9_API_ENTITY_MAP`` 配置
    实际实体后重试。

    Returns:
        str: JSON；未配置实体时为错误说明
    """
    try:
        result = await _post_system("number_rule", "SYS_NumberRule", params.field_keys, params.filter_string, params.start_row, params.limit)
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_query_system_config",
    annotations={"title": "查询系统配置", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_query_system_config(params: SystemConfigInput) -> str:
    """查询系统配置（U9C OpenAPI 未开放独立 SystemConfig Service）。

    U9C 的系统参数在管理端维护，OpenAPI 没有 ``SYS_SystemConfig`` 等价实体；
    默认返回明确的不支持错误。可通过 ``U9_API_ENTITY_MAP`` 配置实际实体后重试。

    Returns:
        str: JSON；未配置实体时为错误说明
    """
    try:
        result = await _post_system("sysconfig", "SYS_SystemConfig", params.field_keys, params.filter_string, params.start_row, params.limit)
        rows = _rows(result)
        return _fmt({"count": len(rows), "has_more": len(rows) == params.limit, "data": rows})
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="u9_list_forms",
    annotations={"title": "查询可用表单", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_list_forms(params: FormSearchInput) -> str:
    """搜索可用表单（form_id）或 U9C Service。

    - 中文关键字搜索本地业务目录（采购、销售、物料…）
    - 英文关键字同时搜索 U9C OpenAPI 的 157 个 Service（如 PurchaseOrder、SO）
    - 留空返回常用业务表单及对应 U9C Service/Entity

    返回字段：form_id、name、alias、desc、recommended_fields、db_tables、
    u9c_service、u9c_entity、u9c_actions、has_business_rules。
    """
    keyword = (params.keyword or "").strip().lower()
    results = []
    seen: set[str] = set()

    for form_id, info in FORM_CATALOG.items():
        if not keyword or (
            keyword in info["name"].lower()
            or any(keyword in alias.lower() for alias in info["alias"])
            or info.get("desc", "").startswith(keyword)
        ):
            service = u9c_catalog.resolve_service(form_id)
            fields = u9c_catalog.default_return_fields(form_id) or []
            results.append({
                "form_id": form_id,
                "name": info["name"],
                "alias": info["alias"],
                "desc": info.get("desc", ""),
                "recommended_fields": ",".join(fields) if fields else info["fields"],
                "db_tables": info.get("db_tables", ()),
                "u9c_service": service,
                "u9c_entity": u9c_catalog.resolve_entity(form_id),
                "u9c_actions": sorted(u9c_catalog.service_actions(service or ""))[:30],
                "has_business_rules": bool(info.get("business_rules")),
            })
            seen.add(form_id.upper())

    # 英文搜索时补充 U9C Service（避免空关键字返回大量技术端点）。
    if keyword:
        for service in u9c_catalog.services():
            if keyword not in service.lower() or service.upper() in seen:
                continue
            actions = u9c_catalog.service_actions(service)
            fields = u9c_catalog.default_return_fields(service) or []
            results.append({
                "form_id": service,
                "name": service,
                "alias": [],
                "desc": "U9C OpenAPI Service",
                "recommended_fields": ",".join(fields),
                "db_tables": (),
                "u9c_service": service,
                "u9c_entity": u9c_catalog.resolve_entity(service),
                "u9c_actions": sorted(actions)[:30],
                "has_business_rules": False,
            })

    return _fmt({
        "count": len(results),
        "tip": (
            "使用 form_id（或 U9C Service）调用 u9_query_bills；"
            "调用 u9_get_fields 获取 U9C 字段、分录与真实 Action。"
        ),
        "forms": results
    })


@mcp.tool(
    name="u9_get_fields",
    annotations={"title": "获取表单字段及业务规则", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_get_fields(params: FieldQueryInput) -> str:
    """获取指定表单的 U9C 字段、分录与真实 Action。

    元数据来自随包发布的 U9C OpenAPI 规范（离线、带缓存），不调用
    外部元数据接口。旧 F* 字段仍可传入，服务会尝试翻译。

    返回内容：
    - u9c_service / u9c_entity / u9c_actions
    - recommended_fields: U9C 字段名
    - metadata.main_fields: 主表字段（name/caption/type/must）
    - metadata.entries: 分录及字段
    - save_template: 最小可保存 model 骨架（按 U9C 字段名）

    Returns:
        str: JSON 格式的字段信息
    """
    form_id = params.form_id
    info = FORM_CATALOG.get(form_id) or {}

    service = u9c_catalog.resolve_service(form_id)
    u9c_fields = u9c_catalog.default_return_fields(form_id) or []
    result: dict[str, Any] = {
        "form_id": form_id,
        "name": info.get("name", "未知表单"),
        "desc": info.get("desc", ""),
        "u9c_service": service,
        "u9c_entity": u9c_catalog.resolve_entity(form_id),
        "u9c_actions": sorted(u9c_catalog.service_actions(service or "")),
        "recommended_fields": ",".join(u9c_fields) if u9c_fields else info.get(
            "fields", "ID,DocNo,BusinessDate,DocStatus",
        ),
        "db_tables": info.get("db_tables", ()),
        "business_rules": info.get("business_rules", {}),
        "status_note": (
            "U9C 的状态字段与枚举随单据类型而异（如 DocStatus / DocumentStatus），"
            "请以本工具返回的 DTO 字段或 U9C 界面为准。"
        ),
    }

    # 从 U9C 离线目录生成统一元数据（内部仍兼容旧的 validator 结构）。
    try:
        validator = await _get_metadata_validator(form_id)
    except Exception:
        validator = None

    if not (validator and validator.fields):
        result["metadata_tip"] = (
            "未找到该 form_id 的 U9C Service/实体，已退回本地目录字段。"
            "请用 u9_list_forms 搜索正确的 form_id 或 U9C Service。"
        )
        return _fmt(result)

    # 分离主表字段 vs 分录
    main_fields = []
    entries: dict[str, FieldDef] = {}
    required_main: List[str] = []
    for name, fd in validator.fields.items():
        if fd.is_entry:
            entries[name] = fd
        else:
            main_fields.append(fd)
            if fd.must_input:
                required_main.append(fd.name)

    def _slim(fd: FieldDef) -> dict:
        d = {"name": fd.name, "caption": fd.caption}
        if fd.must_input:
            d["must"] = True
        if fd.field_type and fd.field_type.startswith("BaseField->"):
            d["lookup"] = fd.field_type.split("->", 1)[1]
        return d

    # 模式 1: 钻取指定分录
    if params.entry_key:
        ent = entries.get(params.entry_key)
        if ent is None:
            # 也可能是用户传了主表名
            result["error"] = f"entry_key '{params.entry_key}' 不存在，可用 entry_key: {list(entries.keys())}"
            return _fmt(result)
        result["entry"] = {
            "key": ent.name,
            "caption": ent.caption,
            "field_count": len(ent.children),
            "required": [c.name for c in ent.children if c.must_input],
            "fields": [_slim(c) for c in ent.children],
        }
        return _fmt(result)

    # 模式 2: 概览（默认）
    # 主表：默认仅返回必填 + 关联基础资料字段；verbose=True 返回全部
    if params.verbose:
        main_returned = [_slim(fd) for fd in main_fields]
        omitted = 0
    else:
        important = [
            fd for fd in main_fields
            if fd.must_input or (fd.field_type or "").startswith("BaseField->")
        ]
        main_returned = [_slim(fd) for fd in important]
        omitted = len(main_fields) - len(important)

    entries_summary = {}
    for name, ent in entries.items():
        entries_summary[name] = {
            "caption": ent.caption,
            "field_count": len(ent.children),
            "required": [c.name for c in ent.children if c.must_input],
        }

    result["metadata"] = {
        "source": "U9C OpenAPI catalog",
        "main_field_count": len(main_fields),
        "main_required_count": len(required_main),
        "main_required_fields": required_main,
        "main_fields_returned": len(main_returned),
        "main_fields_omitted_non_required": omitted,
        "main_fields": main_returned,
        "entry_count": len(entries),
        "entries": entries_summary,
        "tip": (
            "传 entry_key='<分录Key>' 钻取分录字段；"
            "传 verbose=true 返回所有主表字段"
        ),
    }

    # 生成 save 模板骨架
    def _placeholder(fd: FieldDef) -> Any:
        ftype = (fd.field_type or "").lower()
        if ftype.startswith("basefield->"):
            return {"FNumber": ""}
        # FieldType 数字编码常见映射（来自 ElementType 经验值）
        ftk = fd.field_type_key or ""
        if any(x in ftype or x in fd.name.lower() for x in ("date",)):
            return "YYYY-MM-DD"
        if any(x in fd.name.lower() for x in ("qty", "price", "amount", "rate")):
            return 0
        if ftk in ("232", "233"):  # decimal
            return 0
        return ""

    template: dict[str, Any] = {}
    for fd in main_fields:
        if fd.must_input:
            template[fd.name] = _placeholder(fd)
    for name, ent in entries.items():
        required_children = [c for c in ent.children if c.must_input]
        if required_children:
            row = {c.name: _placeholder(c) for c in required_children}
            template[name] = [row]
    if template:
        result["save_template"] = template

    return _fmt(result)


@mcp.tool(
    name="u9_list_form_operations",
    annotations={"title": "查询表单标准动作", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_list_form_operations(params: FormOperationListInput) -> str:
    """查询指定表单对应 U9C Service 支持的真实 Action。

    用途：
    - 不确定某个 Service 支持哪些动作时，先查这里，再调用 u9_execute_operation
    - 作废/关闭/挂起等语义在不同 Service 中动作名不同（例如 PurchaseOrder
      的 Release 表示挂起、Hold 表示解除挂起），必须按本工具结果调用
    - 专用动作工具解析失败时，用这里返回的 number 作为 operation 参数显式传入

    数据来源：打包的 U9C OpenAPI 规范（离线目录，有内存/磁盘缓存）。
    refresh_metadata=true 会先强制刷新该表单缓存。
    返回的 number 是该 Service 的真实 U9C Action（如 Submit/Approve/Release）。

    Returns:
        str: form_id / count / operations=[{number, name, names:[{locale,name}]}]
    """
    try:
        info = await _list_form_operations(params.form_id, refresh=params.refresh_metadata)
        if info is None:
            return _fmt({
                "ok": False,
                "form_id": params.form_id,
                "error": "元数据拉取失败或该表单不存在",
                "hint": (
                    "检查 form_id 是否正确（可用 u9_list_forms 搜索）；"
                    "若表单存在但元数据不可用，可先调用 u9_refresh_metadata。"
                ),
            })
        info["ok"] = True
        info["tip"] = (
            "operations[].number 可直接作为 u9_execute_operation 的 operation 参数；"
            "U9C 每个 Service 的 Action 不同，未列出的动作不要猜测调用。"
        )
        return _fmt(info)
    except Exception as e:
        return _err(e, op="list_form_operations")
