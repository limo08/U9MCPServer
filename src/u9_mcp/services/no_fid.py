"""无 FID 查询视图兼容层。"""

import json
from typing import Any



# ─────────────────────────────────────────────
# 「无 FID 视图」基础资料兼容层（closes #28）
# ─────────────────────────────────────────────
# 现象：查 BD_Currency / BD_AccountBook / BD_VOUCHERGROUP / BD_RateType 等基础资料时，
#       服务端返回「列名 'FID' 无效。」，即使 FieldKeys 里没写 FID 也报。
# 根因：这些基础资料的查询视图（如 V_BD_CURRENCY）没有 FID 列（主键是 FCURRENCYID 之类），
#       而 ExecuteBillQuery 会把 FieldKeys / **OrderString** 原样拼进 SQL。
#       QueryInput.order_string 默认值是 "FID DESC" —— 用户没传排序时它照样注入 FID，
#       所以「不含 FID 的 field_keys 仍然报错」。这是本包的默认值问题，不是用友硬限制。
# 策略：① 已知名单先降级（不发 FID）；② 未知表单撞上该错误则自动去 FID 重试一次，
#       并把它记进运行时名单，同一进程后续直接走降级路径；③ 仍失败则给人话提示。

NO_FID_FORMS: frozenset = frozenset({
    "BD_CURRENCY",        # 币别
    "BD_ACCOUNTBOOK",     # 账簿
    "BD_VOUCHERGROUP",    # 凭证字
    "BD_RATETYPE",        # 汇率类型
    "BD_PERIOD",          # 会计期间
    "BD_ACCOUNTTABLE",    # 科目表
    "BD_SETTLETYPE",      # 结算方式
    "BD_TAXRATE",         # 税率（部分版本视图无 FID）
})

# 运行时学到的无 FID 表单（撞过一次错就记住，避免每次都白跑一趟）
_LEARNED_NO_FID_FORMS: set = set()

_NO_FID_ERR_PATTERNS = ("列名 'FID' 无效", "列名\"FID\"无效", "invalid column name 'fid'")


def _form_lacks_fid(form_id: str) -> bool:
    key = (form_id or "").strip().upper()
    return key in NO_FID_FORMS or key in _LEARNED_NO_FID_FORMS


def _strip_fid(field_keys: str, order_string: str) -> tuple:
    """把 FieldKeys / OrderString 里的裸 FID 去掉。

    只去裸 FID，`FSupplierId.FNumber`、`FIDX` 这类带前后缀的字段保持原样。
    OrderString 去空后回退 FNumber ASC（基础资料一定有 FNumber），空排序部分环境会报错。
    """
    fk = ",".join(
        f for f in (p.strip() for p in (field_keys or "").split(","))
        if f and f.upper() != "FID"
    )
    od_parts = []
    for seg in (order_string or "").split(","):
        seg = seg.strip()
        if not seg:
            continue
        if seg.split()[0].upper() == "FID":
            continue
        od_parts.append(seg)
    od = ", ".join(od_parts)
    return (fk or "FNumber,FName"), (od or "FNumber ASC")


def _is_no_fid_error(result: Any) -> bool:
    """判断查询响应是不是「列名 FID 无效」这一类错误。

    用友查询接口出错时既可能返回 dict（Result.ResponseStatus.Errors），
    也可能返回 list 包一层，所以文本兜底匹配，避免结构变动漏判。
    但正常查询返回的是几十行业务数据，全量序列化去搜字符串太浪费 ——
    先用 `_looks_like_error` 便宜地筛一遍，只有像错误的响应才进文本匹配。
    """
    if not _looks_like_error(result):
        return False
    try:
        blob = json.dumps(result, ensure_ascii=False).lower()
    except Exception:
        blob = str(result).lower()
    return any(p.lower() in blob for p in _NO_FID_ERR_PATTERNS)


def _looks_like_error(result: Any) -> bool:
    """便宜的预筛：正常查询返回行数组，出错才带 ResponseStatus / Errors。"""
    if isinstance(result, dict):
        rs = result.get("Result", result)
        if isinstance(rs, dict):
            return bool(rs.get("ResponseStatus") or rs.get("Errors")) \
                or not rs.get("IsSuccess", True)
        return False
    if isinstance(result, list) and result and isinstance(result[0], dict):
        # 用友偶尔把错误包成 [{"Result": {"ResponseStatus": ...}}]
        return any(k in result[0] for k in ("Result", "ResponseStatus", "Errors"))
    return False
