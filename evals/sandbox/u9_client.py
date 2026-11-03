"""U9StateClient —— 封装"查询账套最终状态"的 API 调用。

复用 server.py 已经调通的 U9C OAuth2 / CommonEntity.Query 逻辑（含自动续期），
把 U9C 返回的行数据映射成"字段名 -> 值"的 dict，供 ResultGrader 做断言。

只读：这个客户端只查询，不写任何数据。
"""
from __future__ import annotations

import re
from typing import Any

# 复用 server 已实现的底层能力（不重复造轮子，也保证与线上行为一致）
from u9_mcp.server import _post, _query_payload, _rows


class U9StateClient:
    async def query(
        self,
        form_id: str,
        field_keys: list[str] | str,
        filter_string: str = "",
        order_string: str = "ID DESC",
        limit: int = 100,
        start_row: int = 0,
    ) -> list[dict[str, Any]]:
        """查询单据，返回 list[dict]（按 field_keys 命名）。

        U9C 通常返回对象行；兼容旧列数组时按 FieldKeys 顺序映射回字段名。
        """
        keys = [k.strip() for k in field_keys.split(",")] if isinstance(field_keys, str) else list(field_keys)
        fk = ",".join(keys)
        result = await _post(
            "query",
            _query_payload(form_id, fk, filter_string, order_string, start_row, limit),
        )
        rows = _rows(result)
        out: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
            elif isinstance(row, (list, tuple)):
                out.append({keys[i]: row[i] for i in range(min(len(keys), len(row)))})
            else:
                out.append({keys[0]: row} if keys else {"value": row})
        return out

    async def count(self, form_id: str, filter_string: str = "") -> int:
        """满足条件的单据条数（上限 100，足够断言用）。"""
        rows = await self.query(form_id, ["ID"], filter_string, limit=100)
        return len(rows)

    async def get_bill_by_no(
        self, form_id: str, bill_no: str, field_keys: list[str] | str
    ) -> dict[str, Any] | None:
        """按单据编号取一条单据。"""
        safe = bill_no.replace("'", "''")
        rows = await self.query(form_id, field_keys, f"DocNo='{safe}'", limit=1)
        return rows[0] if rows else None


class MockStateClient:
    """离线 mock 状态客户端，用于在没有用友环境时自检评估管线。

    数据来源：用例的 `mock_state` 字段 —— {form_id: [ {字段: 值}, ... ]}。
    query() 会对 filter_string 做"尽力而为"的过滤（支持 =、>=、<=、like），
    无法解析的条件项直接忽略（不过滤）。仅用于管线自检，不追求用友语义完备。
    """

    _TERM = re.compile(
        r"^\s*([\w.]+)\s*(>=|<=|=|like)\s*(.+?)\s*$", re.IGNORECASE
    )

    def __init__(self, seed: dict[str, list[dict[str, Any]]] | None = None):
        self.seed = seed or {}

    @staticmethod
    def _unquote(v: str) -> str:
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] == "'":
            return v[1:-1].replace("''", "'")
        return v

    def _match(self, row: dict[str, Any], filter_string: str) -> bool:
        if not filter_string:
            return True
        for term in re.split(r"\s+and\s+", filter_string, flags=re.IGNORECASE):
            m = self._TERM.match(term)
            if not m:
                continue  # 解析不了就不约束
            key, op, raw = m.group(1), m.group(2).lower(), self._unquote(m.group(3))
            actual = row.get(key)
            if actual is None:
                return False
            try:
                if op == "=":
                    if not (str(actual).strip() == raw or float(actual) == float(raw)):
                        return False
                elif op == ">=":
                    if float(actual) < float(raw):
                        return False
                elif op == "<=":
                    if float(actual) > float(raw):
                        return False
                elif op == "like":
                    if raw.strip("%") not in str(actual):
                        return False
            except (ValueError, TypeError):
                if op == "=" and str(actual).strip() != raw:
                    return False
        return True

    async def query(
        self,
        form_id: str,
        field_keys: list[str] | str,
        filter_string: str = "",
        order_string: str = "ID DESC",
        limit: int = 100,
        start_row: int = 0,
    ) -> list[dict[str, Any]]:
        rows = [r for r in self.seed.get(form_id, []) if self._match(r, filter_string)]
        return rows[start_row : start_row + limit]

    async def count(self, form_id: str, filter_string: str = "") -> int:
        return len(await self.query(form_id, ["FID"], filter_string))

    async def get_bill_by_no(self, form_id, bill_no, field_keys):
        rows = await self.query(form_id, field_keys, f"FBillNo='{bill_no}'", limit=1)
        return rows[0] if rows else None
