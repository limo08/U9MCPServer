"""系统服务查询业务逻辑（U9C）。

U9C OpenAPI 只公开了少量系统对象（如用户 ``UserInfo``），没有
``BD_User`` / ``BD_Role`` / ``SYS_Permission`` / ``SYS_SequenceRule`` /
``SYS_NumberRule`` / ``SYS_SystemConfig`` 这些专用端点。这里对能确认的对象
走 ``CommonEntity/Query``，其余返回明确的“U9C 未开放该接口”错误，绝不猜测
端点或伪造结果。
"""

from typing import Any

from . import client, u9c_client, u9c_mapping
from ..config import u9c_catalog


def _system_query_payload(form_id: str, field_keys: str, filter_string: str, start_row: int, limit: int) -> list:
    """旧参数结构，保留给兼容测试与调用方。"""
    return [form_id, {"FieldKeys": field_keys, "FilterString": filter_string, "StartRow": start_row, "Limit": limit}]


_U9C_SYSTEM_FORMS = {
    "user": ("BD_User", "用户"),
    "role": ("BD_Role", "角色"),
    "permission": ("SYS_Permission", "权限"),
    "sequence": ("SYS_SequenceRule", "编码规则"),
    "number_rule": ("SYS_NumberRule", "单据编号规则"),
    "sysconfig": ("SYS_SystemConfig", "系统配置"),
}


async def _post_system(ep_key: str, form_id: str, field_keys: str, filter_string: str, start_row: int, limit: int) -> Any:
    key = (ep_key or "").strip().lower()
    label = _U9C_SYSTEM_FORMS.get(key, (form_id, ep_key))[1]
    service = u9c_catalog.resolve_service(form_id)
    entity = u9c_mapping.entity_for_form(form_id)
    if not service or not entity:
        raise u9c_client.U9CError(
            f"U9C OpenAPI 未开放「{label}」查询接口（本地旧 form_id：{form_id}）。"
            "BD_Role / SYS_Permission / SYS_SequenceRule / SYS_NumberRule / "
            "SYS_SystemConfig 在 U9C 规范中没有对应 Service/CommonEntity 实体。"
            "如需查询，请使用 U9 管理端、数据库只读查询（u9_query_table / u9_execute_sql），"
            "或在 U9_API_ENTITY_MAP 中配置实际实体后重试。"
        )
    query = await u9c_client.common_query_form(
        form_id, field_keys, filter_string, "", start_row, limit
    )
    return {
        "ResCode": 0,
        "Success": True,
        "Data": query.get("rows") or [],
        "Result": query.get("rows") or [],
        "_u9c": query.get("result"),
        "_notice": query.get("notice") or "",
    }
