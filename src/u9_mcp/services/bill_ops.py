"""单据操作（执行动作、下推、视图精简）共用业务逻辑。"""

from typing import Any, List, Optional

from ..models.system import ExecuteActionInput
from . import client, metadata
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt



def _simplify_view_result(data: Any) -> Any:
    """
    精简 view 返回：关联字段对象只保留 Id/Number/Name，去除 MultiLanguageText 等冗余。
    用于 view_bill summary 模式。
    """
    if isinstance(data, dict):
        # 关联基础资料对象的特征：含 Id 且含 Number 或 MultiLanguageText
        has_id = "Id" in data or "FID" in data
        has_number = "Number" in data
        has_mlt = "MultiLanguageText" in data
        if has_id and (has_number or has_mlt):
            slim: dict = {}
            if "Id" in data:
                slim["Id"] = data["Id"]
            if "FID" in data and "Id" not in slim:
                slim["Id"] = data["FID"]
            if "Number" in data:
                slim["Number"] = data["Number"]
            # 提取中文名
            if has_mlt:
                for item in data.get("MultiLanguageText", []):
                    if item.get("LocaleId") == 2052 and item.get("Name", "").strip():
                        slim["Name"] = item["Name"]
                        break
            return slim
        # 普通字典递归
        return {k: _simplify_view_result(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_simplify_view_result(item) for item in data]
    return data


async def _resolve_execute_operation(form_id: str, operation_hint: Optional[str],
                                     match_names: List[str],
                                     exclude_names: Optional[List[str]] = None):
    """从 U9C 动作摘要解析真实 Action 名。

    优先级：显式 operation 参数 > 该 form_id 对应 Service 的动作中文摘要匹配。

    Returns:
        (op_number, source, matched_name, available_ops):
          - op_number: 解析出的 U9C Action（如 Close / Open / Release）；None 表示无法确定
          - source: "explicit"（用户显式传 operation）| "metadata"（动作摘要匹配）| None
          - matched_name: 命中的动作摘要（source="metadata" 时有值）
          - available_ops: 该 Service 全部动作 [{number, name}]（用于错误提示）
    """
    if operation_hint:
        return operation_hint, "explicit", "", []

    available: List[dict] = []
    meta = await metadata._query_metadata(form_id)
    if meta:
        try:
            ops = meta.get("Result", {}).get("NeedReturnData", {}).get("Operations") or []
        except Exception:
            ops = []
        for op in ops:
            num = op.get("OperationNumber") or ""
            if not num:
                continue
            zh = ""
            for n in op.get("OperationName") or []:
                if isinstance(n, dict) and n.get("Key") == 2052 and n.get("Value"):
                    zh = n["Value"]
                    break
            if not zh:
                for n in op.get("OperationName") or []:
                    if isinstance(n, dict) and n.get("Value"):
                        zh = n["Value"]
                        break
            available.append({"number": num, "name": zh})

    excludes = set(exclude_names or [])
    # 1) 精确中文名匹配（无歧义，最优先）
    for kw in match_names:
        for a in available:
            if a["name"] == kw:
                return a["number"], "metadata", a["name"], available
    # 2) 包含匹配（排除 反/业务/行/应付/终止/冻结 等干扰词，避免误匹配 反关闭/业务关闭/行关闭）
    for a in available:
        name = a["name"]
        if not name:
            continue
        if any(x in name for x in excludes):
            continue
        if any(kw in name for kw in match_names):
            return a["number"], "metadata", name, available
    return None, None, "", available


def _operation_resolve_error(form_id: str, action_desc: str, available: List[dict]) -> str:
    """构造“无法自动解析 U9C Action”的明确中文错误，提示显式传 operation。"""
    if available:
        named = [f"{a['name']}({a['number']})" for a in available if a["name"]]
        ops_desc = "、".join(named) if named else "、".join(a["number"] for a in available)
        avail_tip = f"该表单元数据可用的操作：{ops_desc}"
    else:
        avail_tip = "未能读取该表单元数据（可先调用 u9_refresh_metadata 刷新缓存后重试）"
    return (
        f"无法自动确定 {form_id} 的『{action_desc}』U9C Action。"
        f"不同 Service 的动作名与语义不同，无法静态推断。请在调用时显式传 "
        f"operation 参数，或先用 u9_list_form_operations 查看真实 Action。{avail_tip}"
    )


async def _run_execute_action(params: ExecuteActionInput, action: str,
                              op_label: str, source: str = "fixed",
                              matched_name: str = "",
                              endpoint: str = "execute") -> str:
    """U9C 标准动作的共用实现。

    - endpoint="execute"（默认）：走 ``POST /webapi/{Service}/{Action}``，
      action 必须是该 Service 的真实 Action；
    - endpoint="cancel_assign"：按 cancel_assign 别名解析（CancelReleaseSO /
      CancelAssign），用于取消下达/撤销。
    构造业务参数（ID 或 Code）→ _post_raw → 结构化返回。
    """
    try:
        business: dict[str, Any] = {}
        if params.bill_ids:
            business["Ids"] = ",".join(params.bill_ids)
        else:
            business["Numbers"] = params.bill_nos

        if endpoint == "cancel_assign":
            result = await client._post_raw("cancel_assign", params.form_id, business)
        else:
            result = await client._post_raw("execute", params.form_id, business, op_number=action)

        status_data = _result_status(result, op_label)
        status_data["form_id"] = params.form_id
        status_data["action"] = action
        status_data["action_source"] = source
        status_data["endpoint"] = endpoint
        if matched_name:
            status_data["matched_operation_name"] = matched_name
        # 💡 REMEMBER: _result_status 返回的是 fid/ids（不是 id），此处保持口径一致
        if status_data.get("success"):
            status_data["tip"] = (
                f"已在 {params.form_id} 上执行操作『{action}』（端点 {endpoint}）。"
                "注意：返回标识为 fid/ids（非 id），读取时请用 fid 或 ids 字段。"
            )
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op=op_label)


def _step_failed_status(result: Any, op: str) -> dict:
    """run a _post_raw 已返回 result 后，检查是否业务失败，构造步骤记录。"""
    return _result_status(result, op)


def _extract_operations(meta: Any) -> List[dict]:
    """从 U9C 目录元数据中提取动作列表（OperationNumber + 中文摘要 + 多语言名）。"""
    if not isinstance(meta, dict):
        return []
    try:
        ops = meta.get("Result", {}).get("NeedReturnData", {}).get("Operations") or []
    except Exception:
        ops = []
    if not isinstance(ops, list):
        return []

    result: List[dict] = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        number = op.get("OperationNumber") or ""
        if not number:
            continue
        names = []
        zh = ""
        for item in op.get("OperationName") or []:
            if isinstance(item, dict) and item.get("Value"):
                names.append({"locale": item.get("Key"), "name": item.get("Value")})
                if item.get("Key") == 2052:
                    zh = item["Value"]
        if not zh:
            zh = next((n["name"] for n in names), "")
        result.append({"number": number, "name": zh, "names": names})
    return result


async def _list_form_operations(form_id: str, refresh: bool = False) -> Optional[dict]:
    """读取 U9C Service 的动作列表；目录不可用时返回 None。"""
    meta = await metadata._query_metadata(form_id, force=refresh)
    if not meta:
        return None
    operations = _extract_operations(meta)
    return {
        "form_id": form_id,
        "count": len(operations),
        "operations": operations,
    }
