"""ResultGrader —— 结果层判分（最重要）。

任务做完后查用友 API，逐条执行 expected_result.assertions，比对账套实际状态。

每条断言支持两种写法，ResultGrader 优先用 raw：

  raw（可靠，直接用用友语法）：
    {
      "desc": "采购订单已保存且数量正确",
      "form_id": "PUR_PurchaseOrder",
      "filter_string": "FBillNo='PO-EVAL-001'",   # 可选
      "min_count": 1,                               # 可选；exact_count 同理
      "field_checks": {"FDocumentStatus": "A", "FQty": 1000}
    }

  semantic（贴近自然语言，靠 config 的 doc_type_map/field_map/status_map 翻译）：
    {
      "desc": "采购订单存在且字段正确",
      "doc_type": "采购订单",
      "filter": {"供应商": "A"},
      "field_checks": {"数量": 1000, "单据状态": "已保存"}
    }
"""
from __future__ import annotations

from typing import Any

from ..agent.base import Trajectory
from ..sandbox.u9_client import U9StateClient
from .base import GradeResult

_NUM_TOL = 1e-6


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


class ResultGrader:
    layer = "result"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.doc_type_map: dict[str, str] = config.get("doc_type_map", {})
        self.field_map: dict[str, dict[str, str]] = config.get("field_map", {})
        self.status_map: dict[str, str] = config.get("status_map", {})

    # ── 语义翻译 ──────────────────────────────────────────────
    def _resolve_form_id(self, doc_type: str) -> str:
        return self.doc_type_map.get(doc_type, doc_type)  # 已是 form_id 时原样返回

    def _resolve_field(self, form_id: str, name: str) -> str:
        per_form = self.field_map.get(form_id, {})
        if name in per_form:
            return per_form[name]
        star = self.field_map.get("*", {})
        return star.get(name, name)  # 找不到映射时按原样当作字段 key

    def _resolve_value(self, field_key: str, value: Any) -> Any:
        # 单据状态：把中文状态翻译成用友状态码
        if field_key.upper().endswith("FDOCUMENTSTATUS") and isinstance(value, str):
            return self.status_map.get(value, value)
        return value

    def _build_filter(self, form_id: str, filter_dict: dict[str, Any]) -> str:
        parts: list[str] = []
        for name, value in filter_dict.items():
            key = self._resolve_field(form_id, name)
            val = self._resolve_value(key, value)
            if _is_number(val):
                parts.append(f"{key}={val}")
            else:
                safe = str(val).replace("'", "''")
                parts.append(f"{key}='{safe}'")
        return " and ".join(parts)

    # ── 值比对 ───────────────────────────────────────────────
    @staticmethod
    def _values_equal(actual: Any, expected: Any) -> bool:
        if _is_number(expected) and _is_number(actual):
            return abs(float(actual) - float(expected)) <= _NUM_TOL
        return str(actual).strip() == str(expected).strip()

    # ── 单条断言 ─────────────────────────────────────────────
    async def _check_assertion(
        self, assertion: dict[str, Any], client: U9StateClient
    ) -> tuple[bool, str | None, dict]:
        desc = assertion.get("desc", "")

        # form_id：raw 优先，否则从 doc_type 翻译
        form_id = assertion.get("form_id")
        if not form_id:
            doc_type = assertion.get("doc_type")
            if not doc_type:
                return False, f"断言缺少 form_id/doc_type: {desc}", {}
            form_id = self._resolve_form_id(doc_type)

        # filter：raw filter_string 优先，否则从 filter dict 翻译
        filter_string = assertion.get("filter_string")
        if filter_string is None:
            filter_string = self._build_filter(form_id, assertion.get("filter", {}))

        # field_checks：把字段名与值都翻译成用友形式
        raw_checks: dict[str, Any] = assertion.get("field_checks", {})
        checks: dict[str, Any] = {}
        for name, val in raw_checks.items():
            key = self._resolve_field(form_id, name)
            checks[key] = self._resolve_value(key, val)

        query_keys = list({"FID", "FBillNo", *checks.keys()})
        rows = await client.query(form_id, query_keys, filter_string, limit=100)

        details = {
            "form_id": form_id,
            "filter_string": filter_string,
            "matched": len(rows),
        }

        # 数量断言
        if "exact_count" in assertion and len(rows) != assertion["exact_count"]:
            return False, f"{desc}: 期望 {assertion['exact_count']} 条，实际 {len(rows)} 条", details
        min_count = assertion.get("min_count", 1 if checks else 0)
        if len(rows) < min_count:
            return False, f"{desc}: 期望至少 {min_count} 条，实际 {len(rows)} 条", details

        # 字段断言（对第一条匹配单据）
        if checks:
            if not rows:
                return False, f"{desc}: 未查到符合条件的单据，无法校验字段", details
            row = rows[0]
            details["checked_row"] = {k: row.get(k) for k in checks}
            bad: list[str] = []
            for key, expected in checks.items():
                actual = row.get(key)
                if not self._values_equal(actual, expected):
                    bad.append(f"{key} 期望={expected!r} 实际={actual!r}")
            if bad:
                return False, f"{desc}: 字段不符 [{'; '.join(bad)}]", details

        return True, None, details

    # ── 入口 ─────────────────────────────────────────────────
    async def grade(
        self, case: dict[str, Any], trajectory: Trajectory, final_state_client: U9StateClient
    ) -> GradeResult:
        assertions = (case.get("expected_result") or {}).get("assertions", [])
        if not assertions:
            return GradeResult(
                layer=self.layer, passed=True, score=1.0,
                details={"note": "用例无结果层断言，结果层默认通过"},
            )

        failures: list[str] = []
        passed_count = 0
        per_assertion: list[dict] = []
        for a in assertions:
            try:
                ok, msg, details = await self._check_assertion(a, final_state_client)
            except Exception as e:  # 查询/网络异常算断言失败，并记录原因
                ok, msg, details = False, f"{a.get('desc','')}: 断言执行异常 {type(e).__name__}: {e}", {}
            if ok:
                passed_count += 1
            elif msg:
                failures.append(msg)
            per_assertion.append({"desc": a.get("desc", ""), "passed": ok, **details})

        total = len(assertions)
        return GradeResult(
            layer=self.layer,
            passed=passed_count == total,
            score=passed_count / total if total else 1.0,
            failures=failures,
            details={"passed": passed_count, "total": total, "assertions": per_assertion},
        )
