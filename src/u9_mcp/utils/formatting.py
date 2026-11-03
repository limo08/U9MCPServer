"""JSON/行数据格式化与 ID 规整工具。"""

import json
from typing import Any



def _normalize_ids(ids: Any, ep_key: str = "") -> str:
    """把 Submit/Audit/Unaudit/Delete 的 Ids 规整成用友 WebAPI 要求的字符串形式。

    用友U9 Submit/Audit/Unaudit/Delete 接口的 data.Ids 必须是字符串：
    单个 ``"100"``，多个用英文逗号拼接 ``"100,101,102"``（与 CancelAssign /
    ExecuteOperation 同一约定，见本文件 ``business["Ids"] = ",".join(...)``）。

    历史坑（issue #8）：旧实现遇到 list 时取 ``ids[0]``，把其余 ID **静默丢弃**，
    接口仍返回 ``success: true``，调用方完全无感 —— 用户批量反审核 11 张单据，
    实际只有 1 张生效，另外 10 张原封不动。这类"假成功"比直接报错危险得多。

    Args:
        ids: 单个 ID（str/int）或 ID 列表/元组。
        ep_key: 端点名，仅用于报错信息。

    Returns:
        str: 逗号拼接后的 ID 字符串。

    Raises:
        ValueError: ID 为空（空列表 / 空字符串 / 全是空白），属调用方参数错误，
            必须显式失败，不能悄悄发一个空 Ids 上去。
    """
    if isinstance(ids, (list, tuple, set)):
        parts = [str(x).strip() for x in ids]
    else:
        parts = [str(ids).strip()]

    parts = [p for p in parts if p]
    if not parts:
        raise ValueError(f"{ep_key or '该操作'} 缺少有效的单据 ID（Ids 为空）")

    # 去重但保持原顺序：用友对重复 ID 会报错，且调用方通常无意重复提交
    seen, uniq = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)

    return ",".join(uniq)


def _rows(result: Any) -> list:
    """从 API 返回中提取数据行（兼容旧版与 U9C 两种响应形状）。

    U9C 的查询结果通常位于 ``Data.RecordList`` / ``Data.Rows`` / ``Data.Records``；
    标准动作返回 ``Data`` 为单据结果数组；部分接口直接返回数组。
    """
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []
    for key in ("Result", "Data", "data"):
        if key not in result:
            continue
        value = result[key]
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for inner in ("RecordList", "Rows", "Records", "Items", "List", "Data", "data"):
                rows = value.get(inner)
                if isinstance(rows, list):
                    return rows
            return [value]
    return []


# SQL LIKE 模式转义，防止通配符注入
def _escape_sql_like(value: str) -> str:
    return value.replace("'", "''").replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")


def _safe_json(resp) -> Any:
    """安全解析用友 WebAPI 返回。

    用友在业务异常（如报表过滤参数为空导致未处理异常）时，HTTP 状态码仍为 200，
    但响应正文是纯文本（形如 ``response_error: 发生时间... 错误信息...``），并非 JSON。
    若直接 ``resp.json()`` 会抛 ``JSONDecodeError``，把真实报错掩盖成误导性信息。
    这里兜底：解析失败则包成错误结构原样返回，便于上层/调用方排查真实原因。
    """
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        return {
            "kd_error": True,
            "http_status": getattr(resp, "status_code", 0),
            "message": (resp.text or "").strip()[:2000],
        }


def _fmt(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
