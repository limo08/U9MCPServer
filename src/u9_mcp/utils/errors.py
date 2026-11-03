"""错误解析、中文提示、批量结果对账等通用工具。"""

import re
from typing import Any, List, Optional
import httpx

from ..utils.formatting import _fmt


# ─────────────────────────────────────────────
# 已知错误模式库（记忆层）
# 每次遇到新错误模式后追加，格式：("错误关键词", "原因说明", "建议操作")
# ─────────────────────────────────────────────
KNOWN_ERROR_PATTERNS: List[tuple[str, str, str]] = [
    # HTTP 层
    ("502",        "用友不支持 HTTP/2，需显式传 http1=True",         "确保 httpx AsyncHTTPTransport(http1=True)"),
    ("Bad Gateway","同上，用友服务器不支持 HTTP/2",                   "同上"),
    ("会话",       "Session 过期或未登录",                            "调用 _login() 重新登录"),
    ("session",    "Session 过期（英文原文）",                         "调用 _login() 重新登录"),
    ("ctx == null", "Session 过期（用友官方标志：ctx==null=未登录或会话失效）", "调用 _login() 重新登录"),
    ("未登录",       "Session 过期/未登录",                            "调用 _login() 重新登录"),
    ("-10001",      "登录失效错误码",                                 "调用 _login() 重新登录"),
    # 业务层（常见单据操作错误）
    ("关联数量",   "累计关联数量已达订单数量，无法下推",               "检查 FReceiveQty+FStockInQty 是否已满"),
    ("业务关闭",   "该行已业务关闭，不允许操作",                       "检查 FBusinessClose 状态或联系管理员反关闭"),
    ("冻结",       "分录行已冻结，不允许编辑和关联操作",               "联系管理员解冻后重试"),
    ("终止",       "分录行已终止，不允许关联操作",                     "检查 FTerminateStatus 状态"),
    ("交货数量",   "超过交货数量控制范围",                             "检查 FDlyCntl_Low/High 配置"),
    ("权限",       "集成用户没有对应单据的操作权限",                   "联系用友管理员开通权限"),
    ("字段不存在", "字段在当前账套/模块中未启用",                      "用 u9_get_fields 确认可用字段，或改用替代字段"),
    ("保存失败",   "下推或保存失败，详情见 ConvertResponseStatus",     "检查 ConvertResponseStatus 每行错误原因"),
    # 状态/并发/校验类（高频）
    ("已被其他用户修改", "乐观锁冲突，单据被并发修改",                "重新调用 u9_view_bill 拉最新数据再 Save"),
    ("已存在",     "唯一键冲突 (FBillNo / FNumber 重复)",              "检查是否重复 Save，或换一个编码"),
    ("不能为空",   "必录字段缺失",                                     "用 u9_get_fields 查必录项后补齐 model"),
    ("已审核",     "单据已审核，不允许再次提交/审核",                 "用 u9_unaudit_bills 反审核后再操作"),
    ("非草稿",     "单据非草稿状态，不允许 Submit",                   "确认单据状态后再决定下一步"),
    ("基础资料",   "外键引用不存在 (物料/客户/供应商/部门)",          "用 u9_query_materials / u9_query_partners 验证 FNumber"),
]


def _is_session_expired(resp: "httpx.Response") -> bool:
    """判断用友 WebAPI 响应是否表示会话过期/未登录，需要重新登录后重试。

    用友官方认定的会话失效标志（vip.u9.com 二开案例：``ctx == null`` =
    用户未登录或会话已失效）：
      - HTTP 401
      - 响应体含 ``ctx == null``（官方原生表达，最可靠）
      - 响应体含 ``未登录``
      - 错误码 ``-10001``（登录失效）

    关键约束：必须要求响应本身「是失败响应」才判过期。否则 200 成功响应里
    若业务字段恰好带 ``session`` 字样（如某些表单字段名），会被误判为过期并触发
    重发——对 Save/Submit/Audit 等写操作意味着重复提交，是真实风险。

    2026-08-09 修复（issue #7）：原逻辑只认 ``"会话"`` / ``"session"`` 字样，
    当用友返回官方的 ``ctx == null`` / ``未登录`` / ``-10001`` 时不会重登，
    复现用户原报的 ``ctx == null`` 症状；且 200 成功响应里碰巧带 session 字样会
    触发重发（写操作重复提交）。本函数一次性补齐上述官方标志并约束失败响应。
    """
    # 1) 显式未授权
    if resp.status_code == 401:
        return True
    # 2) 仅当响应本身是失败响应时才继续判定，避免成功响应误判
    body = resp.text or ""
    low = body.lower()
    is_failed = (
        resp.status_code != 200
        or '"result":false' in low
        or '"issuccess":false' in low
        or "-10001" in low
    )
    if not is_failed:
        return False
    # 3) 失败响应里出现任一过期标志
    return (
        "ctx == null" in low
        or "未登录" in body
        or "session" in low
        or "会话" in body
        or "-10001" in low
    )


# next-action 元数据：与 KNOWN_ERROR_PATTERNS 平行，命中 pattern 时给出建议工具
# 不并入 tuple 是为了保持 add_known_pattern() 三参公共签名向后兼容
KNOWN_ERROR_NEXT_ACTIONS: dict[str, dict] = {
    "字段不存在":       {"tool": "u9_get_fields",                          "args_hint": "form_id"},
    "不能为空":         {"tool": "u9_get_fields",                          "args_hint": "form_id"},
    "已被其他用户修改": {"tool": "u9_view_bill",                           "args_hint": "form_id, bill_id"},
    "关联数量":         {"tool": "u9_query_purchase_order_progress",       "args_hint": "源单 FBillNo"},
    "基础资料":         {"tool": "u9_query_materials | u9_query_partners", "args_hint": "FNumber"},
    "已审核":           {"tool": "u9_unaudit_bills",                       "args_hint": "form_id, bill_ids"},
    "已存在":           {"tool": "u9_query_bills",                         "args_hint": "form_id, FBillNo / FNumber"},
}

# 单据操作生命周期状态机（约束层）
# 状态流转: 创建 → 提交 → 审核 → ... → 反审核(撤销)
# 目标漂移根源：AI 以为 Save=结束，实际上 Save 只到草稿状态
DOC_LIFECYCLE: dict[str, dict] = {
    # 通用写操作后的 next_action 建议
    "save":    {"from": "草稿",   "to": "草稿",   "success": True,  "next_action": "submit",  "next_action_desc": "建议调用 u9_submit_bills 提交单据至审核队列"},
    "submit":  {"from": "草稿",   "to": "待审核", "success": True,  "next_action": "audit",   "next_action_desc": "建议调用 u9_audit_bills 审核单据"},
    "audit":   {"from": "待审核", "to": "已审核", "success": True,  "next_action": None,      "next_action_desc": "操作完成，单据已生效"},
    "unaudit": {"from": "已审核", "to": "待审核", "success": True,  "next_action": None,      "next_action_desc": "已反审核，可修改后重新提交"},
    "delete":  {"from": "草稿",   "to": "已删除", "success": True,  "next_action": None,      "next_action_desc": "单据已删除"},
    "push":    {"from": "源单",   "to": "目标单草稿", "success": True, "next_action": "submit+audit", "next_action_desc": "目标单已生成，请依次调用 u9_submit_bills + u9_audit_bills"},
}

def _match_known_pattern(message: str) -> Optional[dict]:
    """对单条错误消息做 KNOWN_ERROR_PATTERNS 匹配，命中则返回结构化建议。

    返回形如 {"reason", "suggestion", "next_action_tool"?, "next_action_args_hint"?}。
    未命中返回 None。
    """
    if not message:
        return None
    msg_lower = message.lower()
    for pattern, reason, suggestion in KNOWN_ERROR_PATTERNS:
        if pattern.lower() in msg_lower:
            matched: dict = {"reason": reason, "suggestion": suggestion}
            na = KNOWN_ERROR_NEXT_ACTIONS.get(pattern)
            if na:
                matched["next_action_tool"] = na["tool"]
                matched["next_action_args_hint"] = na["args_hint"]
            return matched
    return None


# ─────────────────────────────────────────────
# 字段名中文对照（高频基础字段）
#
# 为什么需要：报错的原始信息里只有英文字段名（FCustId / FMaterialId…），
# 新手根本看不懂「FCustId」是什么。这一层把高频字段翻成中文，
# 让错误信息直接说人话。表内实际字段仍以 u9_get_fields 为准。
# ─────────────────────────────────────────────
FIELD_LABELS: dict[str, str] = {
    # 客户 / 供应商
    "FCustId": "客户", "FCUSTID": "客户", "FCustomerId": "客户",
    "FSupplierId": "供应商", "FSupplierId.FNumber": "供应商编码",
    # 物料 / 单位
    "FMaterialId": "物料", "FMaterialId.FNumber": "物料编码",
    "FUnitID": "单位", "FUnitId": "单位", "FUnitID.FName": "单位名称",
    # 组织 / 部门
    "FSaleOrgId": "销售组织", "FSalesOrgId": "销售组织",
    "FPurchaseOrgId": "采购组织", "FDeptId": "部门",
    "FPurchaseDeptId": "采购部门", "FSaleDeptId": "销售部门",
    "FStockOrgId": "库存组织", "FManufactureOrgId": "生产组织",
    # 金额 / 数量 / 单价
    "FQty": "数量", "FPrice": "单价", "FTaxPrice": "含税单价",
    "FAmount": "金额", "FTaxAmount": "含税金额",
    "FAllAmount": "价税合计", "FAuxPrice": "辅助单价",
    "FExchangeRate": "汇率", "FFCurrencyId": "结算币别",
    "FSettleCurrId": "结算币别", "FPayCurrencyId": "付款币别",
    # 日期
    "FDate": "单据日期", "FCreateDate": "创建日期",
    "FPlanStartDate": "计划开工日期", "FPlanFinishDate": "计划完工日期",
    "FDeliveryDate": "交货日期", "FFinishDate": "完工日期",
    # 单据标识
    "FBillNo": "单据编号", "FID": "内码", "FNumber": "编码",
    "FDocumentStatus": "单据状态", "FBillTypeID": "单据类型",
    # 库存
    "FStockId": "仓库", "FStockName": "仓库名称",
    "FRealQty": "实际数量", "FSourceQty": "来源数量",
}


# 字段名替换用的编译正则：一次扫描完成，且长名优先。
#
# 为什么不用逐个 str.replace：旧实现按长度倒序逐个替换，先替换长名、
# 后替换短名，短名会命中长名替换后残留在括号里的文本，于是
#   "FMaterialId.FNumber" → "物料编码(物料(FMaterialId).编码(FNumber))"
# 这种嵌套垃圾。单次扫描 + 长名优先可根治。
#
# wrapped 分支识别「中文(字段名)」这种已翻译形态并原样保留，
# 使 _humanize_error_message 具备幂等性（重复调用不会二次包装）。
_FIELD_LABELS_RE = re.compile(
    "(?P<wrapped>"
    + "|".join(
        re.escape(f"{zh}({en})")
        for en, zh in sorted(
            FIELD_LABELS.items(), key=lambda kv: len(kv[1]) + len(kv[0]), reverse=True
        )
    )
    + ")|(?P<bare>"
    + "|".join(re.escape(en) for en in sorted(FIELD_LABELS, key=len, reverse=True))
    + ")"
)


def _zh_field(field_name: str) -> str:
    """把英文字段名翻成中文说明（找不到就原样返回）。"""
    if not field_name:
        return ""
    if field_name in FIELD_LABELS:
        return FIELD_LABELS[field_name]
    # 处理带 .FNumber / .FName 后缀的写法
    if "." in field_name:
        base, suffix = field_name.split(".", 1)
        if base in FIELD_LABELS:
            tail = {"FNumber": "编码", "FName": "名称", "FId": "内码"}.get(suffix, suffix)
            return f"{FIELD_LABELS[base]}{tail}"
    # 去掉 F 前缀做一次宽松匹配（FOldQty → 数量）
    stripped = field_name[1:] if field_name.startswith("F") else field_name
    for k, v in FIELD_LABELS.items():
        if k.lower() == stripped.lower():
            return v
    return ""


def _humanize_error_message(message: str, field_name: str = "") -> str:
    """把用友原始错误消息改写成中文人话。

    做法：把消息里出现的英文字段名替换成「中文名(字段名)」，
    并在有对应字段时追加一句建议。原始消息保留在 raw_message 里。

    幂等：已翻译的「中文(字段名)」片段会原样保留，重复调用不会二次包装。
    """
    if not message:
        return message

    def _replace(m: re.Match) -> str:
        if m.group("wrapped"):
            return m.group(0)
        en = m.group("bare")
        return f"{FIELD_LABELS[en]}({en})"

    text = _FIELD_LABELS_RE.sub(_replace, message)
    # 消息里没出现词典里的字段，但错误本身指定了字段
    if field_name and field_name not in text:
        zh = _zh_field(field_name)
        if zh:
            text = f"{text}（涉及字段：{zh}({field_name})）"
    return text


def _is_u9c_result(result: Any) -> bool:
    """是否为 U9C OpenAPI 的统一响应（ResCode/Success/ResMsg/Data）。"""
    return (
        isinstance(result, dict)
        and "ResponseStatus" not in result
        and any(k in result for k in ("ResCode", "Success", "ResMsg", "Exception"))
    )


def _u9c_error_rows(data: Any) -> list:
    rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ok = row.get("IsSucess", row.get("IsSuccess", row.get("Success", True)))
        if ok is False:
            out.append(row)
    return out


def _parse_u9_errors(result: Any) -> list:
    """从 U9 API 响应中提取业务错误（反馈层核心函数）。

    返回 errors 列表，每项含 message/detail/field/matched；
    同时兼容旧版 ResponseStatus 与 U9C ``ResCode/Success/ResMsg/Data``。
    """
    errors = []
    seen: set = set()  # dedup key: (row|None, message)
    try:
        if _is_u9c_result(result):
            ok = bool(result.get("Success")) and int(result.get("ResCode") or 0) == 0
            if ok:
                return []
            for key in ("ResMsg", "Exception"):
                raw_msg = str(result.get(key) or "").strip()
                if not raw_msg:
                    continue
                key2 = (None, raw_msg)
                if key2 in seen:
                    continue
                seen.add(key2)
                errors.append({
                    "message": _humanize_error_message(raw_msg),
                    "raw_message": raw_msg,
                    "detail": "",
                    "field": "",
                    "field_zh": "",
                    "matched": _match_known_pattern(raw_msg),
                })
            for i, row in enumerate(_u9c_error_rows(result.get("Data"))):
                raw_msg = str(
                    row.get("ErrorMsg") or row.get("Message") or row.get("ResMsg")
                    or row.get("Exception") or "操作失败"
                ).strip()
                key2 = (i, raw_msg)
                if key2 in seen:
                    continue
                seen.add(key2)
                field_name = str(row.get("FieldName") or row.get("Field") or "")
                errors.append({
                    "type": "u9c",
                    "row": i,
                    "message": _humanize_error_message(raw_msg, field_name),
                    "raw_message": raw_msg,
                    "detail": str(row.get("Detail") or row.get("Description") or ""),
                    "field": field_name,
                    "field_zh": _zh_field(field_name),
                    "matched": _match_known_pattern(raw_msg),
                })
            return errors

        rs = result.get("Result", result) if isinstance(result, dict) else {}
        status = rs.get("ResponseStatus", {})
        if isinstance(status, dict) and not status.get("IsSuccess", True):
            for err in status.get("Errors", []):
                msg = err.get("Message", "")
                key = (None, msg)
                if key in seen:
                    continue
                seen.add(key)
                raw_msg = msg
                field_name = err.get("FieldName", "")
                errors.append({
                    "message": _humanize_error_message(raw_msg, field_name),
                    "raw_message": raw_msg,
                    "detail": err.get("Dsc", ""),
                    "field": field_name,
                    "field_zh": _zh_field(field_name),
                    "matched": _match_known_pattern(raw_msg),
                })
        # Push 操作特有的 ConvertResponseStatus —— 逐行也走 pattern 匹配
        conv = rs.get("ConvertResponseStatus", [])
        if conv:
            for i, c in enumerate(conv):
                if not c.get("IsSuccess", True):
                    raw_msg = c.get("Message", "转换失败")
                    key = (i, raw_msg)
                    if key in seen:
                        continue
                    seen.add(key)
                    errors.append({
                        "type": "convert",
                        "row": i,
                        "message": _humanize_error_message(raw_msg),
                        "raw_message": raw_msg,
                        "detail": c.get("Description", ""),
                        "matched": _match_known_pattern(raw_msg),
                    })
    except Exception:
        pass
    return errors


def _reconcile_batch(status: Any, requested_ids: Any) -> dict:
    """核对「提交了几个」与「用友确认成功了几个」，把静默丢单变成显式失败。

    背景（issue #8）：批量 Submit/Audit/Unaudit/Delete 时，用友可能只处理了一部分
    单据却仍返回 ``IsSuccess: true``，``SuccessEntitys`` 里只有寥寥几条。调用方只看
    ``success`` 字段就会误以为全部生效 —— 这类"假成功"比直接报错危险得多。

    Args:
        status: 用友返回的 ResponseStatus 字典。
        requested_ids: 本次请求实际提交的 ID（列表或逗号拼接字符串）。

    Returns:
        dict: 含 requested_count / succeeded_count / missing_ids 的对账结果；
              无法对账（缺少任一侧数据）时返回空 dict，调用方按原逻辑处理。
    """
    if isinstance(requested_ids, str):
        requested = [x.strip() for x in requested_ids.split(",") if x.strip()]
    elif isinstance(requested_ids, (list, tuple, set)):
        requested = [str(x).strip() for x in requested_ids if str(x).strip()]
    else:
        return {}

    if not requested or not isinstance(status, dict):
        return {}

    # U9C：Data 数组里逐条返回 IsSucess/ID/Code；与旧 ResponseStatus.SuccessEntitys 对齐。
    if _is_u9c_result(status):
        rows = status.get("Data")
        if not isinstance(rows, list):
            return {}
        succeeded = {
            str(row.get("ID", row.get("Id", row.get("Code")))).strip()
            for row in rows
            if isinstance(row, dict)
            and row.get("ID", row.get("Id", row.get("Code"))) is not None
            and row.get("IsSucess", row.get("IsSuccess", True)) is not False
        }
    else:
        entities = status.get("SuccessEntitys")
        if not isinstance(entities, list):
            return {}

        succeeded = {
            str(e.get("Id")).strip()
            for e in entities
            if isinstance(e, dict) and e.get("Id") is not None
        }
    missing = [rid for rid in requested if rid not in succeeded]

    out = {
        "requested_count": len(requested),
        "succeeded_count": len(requested) - len(missing),
    }
    if missing:
        out["missing_ids"] = missing
        out["tip"] = (
            f"提交了 {len(requested)} 张单据，用友只确认成功 {len(requested) - len(missing)} 张，"
            f"其余 {len(missing)} 张未生效（见 missing_ids）。请逐张核对后重试，不要当作已完成。"
        )
    return out


def _result_status(result: Any, op: str, requested_ids: Any = None) -> dict:
    """构建结构化操作结果（约束层 + 反馈层）

    Args:
        result: 用友 WebAPI 原始返回。
        op: 操作名（submit/audit/...），用于查生命周期下一步。
        requested_ids: 可选，本次请求提交的单据 ID。传入后会做批量对账，
            发现用友少处理了单据时把 success 置为 False（见 issue #8）。
    """
    rs = result.get("Result", result) if isinstance(result, dict) else {}
    status = rs.get("ResponseStatus", {})
    data_rows: list = []

    if _is_u9c_result(result):
        ok = bool(result.get("Success")) and int(result.get("ResCode") or 0) == 0
        errors = _parse_u9_errors(result) if not ok else []
        data = result.get("Data")
        if isinstance(data, list):
            data_rows = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            data_rows = [data]
        status = {
            "IsSuccess": ok,
            "ResCode": result.get("ResCode"),
            "ResMsg": result.get("ResMsg") or "",
            "Exception": result.get("Exception") or "",
            "Data": data,
        }
    elif isinstance(status, dict):
        ok = status.get("IsSuccess", False)
        errors = _parse_u9_errors(result) if not ok else []
    else:
        ok = True
        errors = []

    lifecycle = DOC_LIFECYCLE.get(op, {})

    # 提取单据标识（U9C 标准动作为 Data[] 中的 ID/Code）
    fid = rs.get("FID") or rs.get("Id")
    bill_no = rs.get("FBillNo") or rs.get("Number")
    ids = rs.get("Ids") or (fid if fid else None)
    if data_rows and not fid:
        id_values = [r.get("ID", r.get("Id")) for r in data_rows if r.get("ID", r.get("Id")) is not None]
        if id_values:
            fid = id_values[0]
            ids = id_values
        if not bill_no:
            bill_no = next((r.get("Code") for r in data_rows if r.get("Code")), None)

    out: dict[str, Any] = {
        "op": op,
        "success": ok,
        "response_status": status,
    }
    if fid:
        out["fid"] = fid
    if bill_no:
        out["bill_no"] = bill_no
    if ids:
        out["ids"] = [ids] if isinstance(ids, str) or isinstance(ids, int) else list(ids)
    if errors:
        out["errors"] = errors
        out["tip"] = (
            "单据操作失败，请检查 errors 列表中的 reason 和 suggestion 字段。"
            "如需更多信息，调用 u9_view_bill 查看单据详情。"
        )

    # issue #8：批量操作对账 —— 用友少处理了单据却报 IsSuccess=true 时，必须显式失败
    if requested_ids is not None:
        recon = _reconcile_batch(result if _is_u9c_result(result) else status, requested_ids)
        if recon:
            out.update(recon)
            if recon.get("missing_ids"):
                ok = False
                out["success"] = False

    if ok:
        # next_action 始终返回（None 表示流程完成）
        out["next_action"] = lifecycle.get("next_action")
        if out["next_action"]:
            out["next_action_desc"] = lifecycle["next_action_desc"]

    return out


def add_known_pattern(
    pattern: str,
    reason: str,
    suggestion: str,
    next_action_tool: Optional[str] = None,
    next_action_args_hint: Optional[str] = None,
) -> None:
    """向已知错误模式库追加新模式（记忆层核心函数）。

    用法示例：
        add_known_pattern("特定错误关键词", "原因说明", "建议操作")
        add_known_pattern("字段A", "原因", "建议",
                          next_action_tool="u9_get_fields",
                          next_action_args_hint="form_id")

    next-action 元数据可选；若提供，命中此 pattern 的错误会在 matched 中携带
    next_action_tool / next_action_args_hint，方便 AI 自助恢复。
    """
    global KNOWN_ERROR_PATTERNS
    existing = [p[0] for p in KNOWN_ERROR_PATTERNS]
    if pattern not in existing:
        KNOWN_ERROR_PATTERNS.append((pattern, reason, suggestion))
    if next_action_tool:
        KNOWN_ERROR_NEXT_ACTIONS[pattern] = {
            "tool": next_action_tool,
            "args_hint": next_action_args_hint or "",
        }


def _err(e: Exception, extra_errors: list = None, op: str = "") -> str:
    """标准化错误返回（反馈层），整合 U9 业务错误 + HTTP 错误

    Args:
        e: 异常对象
        extra_errors: 额外的已解析错误列表
        op: 操作类型（用于失败日志记录），如 "save" / "push" / "submit"
    """
    # 先追加已解析的用友业务错误
    extra = extra_errors or []

    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        msgs = {
            401: "认证失败，请检查 U9_API_CLIENT_ID/U9_API_CLIENT_SECRET/U9_API_TOKEN 配置",
            403: "权限不足，请确认集成用户拥有对应单据权限",
            404: "接口地址不存在，请检查 U9_API_SERVER_URL（应为 U9C 服务根地址）",
            429: "请求过于频繁，请稍后重试",
        }
        raw = e.response.text[:300].strip()
        err_item = {"type": "http", "code": code, "message": msgs.get(code, f"HTTP {code}"), "raw": raw}
        matched = _match_known_pattern(raw)
        if matched:
            err_item["matched"] = matched
        extra.append(err_item)
    elif isinstance(e, httpx.TimeoutException):
        extra.append({"type": "timeout", "message": "请求超时，请检查服务器连通性"})
    elif isinstance(e, RuntimeError):
        extra.append({"type": "runtime", "message": str(e)})
    else:
        extra.append({"type": "unknown", "message": f"{type(e).__name__} - {e}"})

    result = {"error": True, "errors": extra}

    # 失败追溯：记录到 failure_log.jsonl（记忆层核心）
    if op and extra:
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log(op, result)
        except Exception:
            pass  # 不因日志记录失败影响正常返回

    return _fmt(result)
