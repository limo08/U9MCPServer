"""旧版 F* 风格 form_id/字段 → U9C Service/DTO 的映射层。

旧工具的参数命名沿用 ``FBillNo`` / ``FDate`` / ``FSupplierId`` 风格，
U9C 使用业务字段名（``DocNo`` / ``BusinessDate`` / ``Supplier``…）。这里集中
做转换，避免 107 个工具各自实现一套：

* ``service_for_form`` / ``entity_for_form``：form_id → /webapi/{Service} 与实体全名；
* ``return_fields``：字段列表翻译（含分录字段自动加 ``POLines.`` 前缀）；
* ``build_filters``：把 ``FDocumentStatus='C' and FDate>='...'`` 翻译为
  ``CompositeCriterion`` 结构；
* ``build_orders``：排序字段翻译；
* ``convert_model`` / ``convert_models``：保存/批量保存的 DTO 转换；
* ``resolve_action``：把 save/submit/audit/delete/close… 解析为该 Service
  真实存在的 Action（大小写与命名差异由规范兜底）。
"""

from __future__ import annotations

import copy
import re
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from ..config import u9c_catalog


class MappingError(ValueError):
    """无法把本地参数安全映射到 U9C 协议。"""


# ─────────────────────────────────────────────
# form_id → Service / Entity
# ─────────────────────────────────────────────
def service_for_form(form_id: str) -> Optional[str]:
    return u9c_catalog.resolve_service(form_id)


def entity_for_form(form_id: str) -> Optional[str]:
    return u9c_catalog.resolve_entity(form_id)


# ─────────────────────────────────────────────
# 字段名映射
# ─────────────────────────────────────────────
_GLOBAL_FIELD_ALIASES = {
    "FID": "ID",
    "FBillNo": "DocNo",
    "FDate": "BusinessDate",
    "FDocumentStatus": "DocStatus",
    "FSupplierId": "Supplier",
    "FSupplierId.FNumber": "Supplier.Code",
    "FSupplierId.FName": "Supplier.Name",
    "FCustomerId": "OrderBy",
    "FCustId": "OrderBy",
    "FCustomerId.FNumber": "OrderBy",
    "FMaterialId": "ItemInfo",
    "FMaterialId.FNumber": "ItemInfo.ItemCode",
    "FMaterialId.FName": "ItemInfo.ItemName",
    "FMaterialId.FSpecification": "ItemInfo.Specification",
    "FUnitId": "TU",
    "FUnitID": "TU",
    "FUnitId.FNumber": "TU",
    "FUnitId.FName": "TU",
    "FQty": "Qty",
    "FPrice": "FinallyPriceTC",
    "FTaxPrice": "FinallyPriceTC",
    "FAmount": "NetMoneyTC",
    "FAllAmount": "TotalMoneyTC",
    "FTaxAmount": "TaxMoneyTC",
    "FDeliveryDate": "DeliveryDate",
    "FPlanFinishDate": "DeliveryDate",
    "FMemo": "Memo",
    "FNote": "Memo",
    "FEntryID": "ID",
    "FLineNo": "DocLineNo",
    "FLot": "ItemLot",
    "FLot.FNumber": "ItemLot",
    "FStockId": "Wh",
    "FStockId.FNumber": "Wh.Code",
    "FStockId.FName": "Wh.Name",
    "FDeptId": "PurDept",
    "FPurchaseDeptId": "PurDept",
    "FSaleDeptId": "SaleDepartment",
    "FPurchaserId": "PurOper",
    "FSalerId": "Seller",
    "FNumber": "Code",
    "FName": "Name",
    "FShortName": "ShortName",
    "FSpecification": "Specification",
    "FContact": "Contact",
    "FPhone": "Phone",
}

_SERVICE_FIELD_ALIASES = {
    "PUR_PurchaseOrder": {
        "FQty": "ReqQtyTU",
        "FPurQty": "ReqQtyTU",
        "FPrice": "FinallyPriceTC",
        "FTaxPrice": "FinallyPriceTC",
        "FAmount": "TotalMnyTC",
        "FAllAmount": "TotalMnyTC",
        "FTaxAmount": "TotalTaxAC",
        "FDeliveryDate": "DeliveryDate",
        "FMaterialId": "ItemInfo",
        "FLot": "ItemLot",
    },
    "SAL_SaleOrder": {
        "FQty": "OrderByQtyTU",
        "FPrice": "FinallyPriceTC",
        "FTaxPrice": "FinallyPriceTC",
        "FAmount": "NetMoneyTC",
        "FAllAmount": "TotalMoneyTC",
        "FTaxAmount": "TaxMoneyTC",
        "FMaterialId": "ItemCode",
        "FUnitId": "TU",
        "FUnitID": "TU",
    },
    "STK_InStock": {
        "FQty": "Qty",
        "FMaterialId": "ItemMaster",
        "FStockId": "Wh",
    },
    "BD_Supplier": {
        "FID": "m_iD",
        "FNumber": "m_code",
        "FName": "Name",
        "FShortName": "m_shortName",
        "FIsActive": "m_effective",
        "FIsHoldRelease": "m_isHoldRelease",
        "FHoldDate": "m_holdDate",
        "FReleaseDate": "m_releaseDate",
    },
    "PRD_MO": {
        "FMaterialId": "ItemMaster",
        "FMaterialId.FNumber": "ItemMaster.Code",
        "FMaterialId.FName": "ItemMaster.Name",
        "FUnitId": "ProductUOM",
        "FQty": "ProductQty",
        "FPlanStartDate": "StartDate",
        "FPlanFinishDate": "CompleteDate",
        "FPrdOrgId": "Org",
        "FDeptId": "Department",
    },
    "PRD_PickMtrl": {
        "FMaterialId": "Item",
        "FMaterialId.FNumber": "Item.Code",
        "FMaterialId.FName": "Item.Name",
        "FQty": "IssueQty",
        "FPickQty": "IssueQty",
        "FStockId": "IssueWh",
        "FStockId.FNumber": "IssueWh.Code",
        "FStockId.FName": "IssueWh.Name",
        "FMoBillNo": "MOs.Code",
        "FDeptId": "Dept",
    },
    "PRD_Instock": {
        "FMaterialId": "Item",
        "FMaterialId.FNumber": "Item.Code",
        "FMaterialId.FName": "Item.Name",
        "FQty": "CompleteQty",
        "FInQty": "CompleteQty",
        "FStockId": "Wh",
        "FStockId.FNumber": "Wh.Code",
        "FStockId.FName": "Wh.Name",
        "FDeptId": "ApplyDept",
    },
}

_OBJECT_FIELDS = {
    "Supplier", "PriceList", "PurOper", "PurDept", "OrderBy", "Seller",
    "SaleDepartment", "ShipToSite", "BillToSite", "PayerCustomer", "PayerToSite",
    "ItemInfo", "ItemMaster", "Wh", "TaxSchedule", "PaymentTerm", "ConfirmTerm",
    "TradePath", "Project", "Task", "Mfc", "RcvOrgDTO", "RequiredPerson", "RequiredDept",
    "Customer", "Department", "Org", "Currency", "UOM", "Category", "Territory",
}


def _field_alias(form_id: str, field: str) -> str:
    raw = (field or "").strip()
    if not raw:
        return raw
    candidates = [raw, raw.replace(" ", "")]
    svc_aliases = next(
        (v for k, v in _SERVICE_FIELD_ALIASES.items() if k.upper() == (form_id or "").upper()),
        {},
    )
    svc_upper = {k.upper(): v for k, v in svc_aliases.items()}
    global_upper = {k.upper(): v for k, v in _GLOBAL_FIELD_ALIASES.items()}
    for candidate in candidates:
        if candidate in svc_aliases:
            return svc_aliases[candidate]
        if candidate in _GLOBAL_FIELD_ALIASES:
            return _GLOBAL_FIELD_ALIASES[candidate]
        upper = candidate.upper()
        if upper in svc_upper:
            return svc_upper[upper]
        if upper in global_upper:
            return global_upper[upper]

    parts = raw.split(".")
    mapped_parts = []
    for i, part in enumerate(parts):
        low = part.lower()
        if low in ("fnumber", "fcode"):
            mapped_parts.append("Code" if i else part[1:])
        elif low == "fname":
            mapped_parts.append("Name")
        elif low == "fid":
            mapped_parts.append("ID")
        elif part.startswith("F") and len(part) > 1:
            mapped_parts.append(part[1:])
        else:
            mapped_parts.append(part)
    return ".".join(mapped_parts)


def _catalog_field_sets(form_id: str) -> tuple[set, set, Optional[str]]:
    catalog = u9c_catalog.form_fields(form_id)
    header = {f.get("name") for f in catalog.get("fields") or [] if f.get("name")}
    line: set = set()
    line_path = None
    for entry in catalog.get("entries") or []:
        fields = {f.get("name") for f in entry.get("fields") or [] if f.get("name")}
        line |= fields
        if line_path is None and entry.get("path"):
            line_path = entry.get("path")
    return header, line, line_path


def map_field_path(form_id: str, field: str, *, line: bool = False) -> str:
    """翻译单个字段/路径；分录字段自动补 ``POLines.`` 之类的前缀。"""
    raw = (field or "").strip()
    if not raw:
        return raw
    mapped = _field_alias(form_id, raw)
    header, line_fields, line_path = _catalog_field_sets(form_id)
    is_native = raw in header or raw in line_fields
    if line:
        return mapped
    if line_path and not _looks_pathed(raw) and mapped not in header:
        root = mapped.split(".", 1)[0]
        if root in line_fields:
            return f"{line_path}.{mapped}"
    return mapped


def _looks_pathed(field: str) -> bool:
    return "." in field


def _field_is_valid(form_id: str, mapped: str) -> bool:
    header, line_fields, line_path = _catalog_field_sets(form_id)
    entry_keys = {
        e.get("key") for e in u9c_catalog.form_fields(form_id).get("entries") or []
        if e.get("key")
    }
    root = (mapped or "").split(".", 1)[0]
    return bool(
        mapped in header
        or root in header
        or root in line_fields
        or root in entry_keys
        or (line_path and root == line_path)
        or root in {"POLines", "SOLines", "SOShiplines", "DocLines", "Lines"}
    )


def _is_alias_origin(field: str) -> bool:
    raw = (field or "").strip()
    if not raw:
        return False
    if raw.upper() in {k.upper() for k in _GLOBAL_FIELD_ALIASES}:
        return True
    return raw.startswith("F") and len(raw) > 1


def return_fields(form_id: str, field_keys: str = "") -> List[str]:
    raw = (field_keys or "").strip()
    if not raw or raw == "*":
        return u9c_catalog.default_return_fields(form_id)
    out: List[str] = []
    seen = set()
    dropped: List[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        mapped = map_field_path(form_id, part)
        # 旧工具的默认 F* 字段并不适用于所有 U9C 实体（如 BD_Material 没有
        # DocNo/BusinessDate），自动剔除，避免整次查询因一个默认字段失败。
        if _is_alias_origin(part) and not _field_is_valid(form_id, mapped):
            dropped.append(part)
            continue
        if mapped not in seen:
            seen.add(mapped)
            out.append(mapped)
    if not out:
        out = u9c_catalog.default_return_fields(form_id)
    return out


def field_mapping(form_id: str, field_keys: str = "") -> List[dict]:
    raw = (field_keys or "").strip()
    if not raw or raw == "*":
        return []
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        mapped = map_field_path(form_id, part)
        if mapped.lower() != part.lower():
            out.append({"from": part, "to": mapped})
    return out


def query_notice(form_id: str, fields: Sequence[str]) -> str:
    if not fields:
        return ""
    if not u9c_catalog.resolve_service(form_id):
        return ""
    return (
        "返回字段已按 U9C OpenAPI 命名转换（如 FBillNo→DocNo、FDocumentStatus→DocStatus）。"
    )


# ─────────────────────────────────────────────
# 过滤表达式 → CompositeCriterion
# ─────────────────────────────────────────────
_TOKEN_RE = re.compile(
    r"""
    \s*
    (?:
        (?P<lparen>\()
      | (?P<rparen>\))
      | (?P<op><>|!=|>=|<=|=|>|<)
      | (?P<comma>,)
      | (?P<quoted>'(?:[^']|'')*'|"(?:[^"\\]|\\.)*")
      | (?P<word>[A-Za-z_一-鿿][A-Za-z0-9_.$#\/]*)
      | (?P<number>-?\d+(?:\.\d+)?)
    )
    """,
    re.VERBOSE,
)

_KEYWORDS = {"and", "or", "not", "in", "like", "is", "null", "between", "true", "false"}


def _tokenize(expr: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        if expr[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise MappingError(f"无法解析过滤条件（位置 {pos}）：{expr[pos:pos + 40]}")
        kind = m.lastgroup
        value = m.group(kind)
        if kind == "word":
            lower = value.lower()
            if lower in _KEYWORDS:
                kind = lower
            else:
                kind = "field"
        tokens.append((kind, value))
        pos = m.end()
    return tokens


class _FilterParser:
    def __init__(self, form_id: str, tokens: List[Tuple[str, str]]):
        self.form_id = form_id
        self.tokens = tokens
        self.i = 0

    def peek(self) -> Tuple[str, str]:
        return self.tokens[self.i] if self.i < len(self.tokens) else ("eof", "")

    def take(self, kind: Optional[str] = None) -> Tuple[str, str]:
        tok = self.peek()
        if kind and tok[0] != kind:
            raise MappingError(f"过滤条件语法错误：期望 {kind}，实际 {tok[1] or tok[0]}")
        self.i += 1
        return tok

    def parse(self):
        node = self.parse_or()
        if self.peek()[0] != "eof":
            raise MappingError(f"过滤条件存在未解析内容：{self.peek()[1]}")
        return node

    def parse_or(self):
        nodes = [self.parse_and()]
        while self.peek()[0] == "or":
            self.take()
            nodes.append(self.parse_and())
        return nodes[0] if len(nodes) == 1 else ("or", nodes)

    def parse_and(self):
        nodes = [self.parse_factor()]
        while self.peek()[0] == "and":
            self.take()
            nodes.append(self.parse_factor())
        return nodes[0] if len(nodes) == 1 else ("and", nodes)

    def parse_factor(self):
        kind, value = self.peek()
        if kind == "lparen":
            self.take()
            node = self.parse_or()
            self.take("rparen")
            return node
        return self.parse_atom()

    def parse_atom(self):
        _, field = self.take("field")
        kind, value = self.peek()
        if kind == "op":
            self.take()
            raw = self.take()
            return ("cmp", field, value, self._value(raw))
        if kind == "like":
            self.take()
            raw = self.take()
            return ("cmp", field, "like", self._value(raw))
        if kind == "not":
            self.take()
            nxt = self.take()
            if nxt[0] == "like":
                raw = self.take()
                return ("cmp", field, "not like", self._value(raw))
            if nxt[0] == "in":
                return ("in", field, self._in_values(), True)
            raise MappingError(f"不支持的过滤语法：NOT {nxt[1]}")
        if kind == "in":
            self.take()
            return ("in", field, self._in_values(), False)
        if kind == "between":
            self.take()
            low = self._value(self.take())
            self.take("word")
            high = self._value(self.take())
            return ("between", field, low, high)
        if kind == "is":
            self.take()
            negate = False
            if self.peek()[0] == "not":
                self.take()
                negate = True
            self.take("null")
            return ("null", field, negate)
        raise MappingError(f"字段「{field}」后缺少比较运算符：{value or kind}")

    def _in_values(self):
        self.take("lparen")
        values = []
        while True:
            tok = self.take()
            if tok[0] == "rparen":
                break
            values.append(self._value(tok))
            if self.peek()[0] == "comma":
                self.take()
                continue
            self.take("rparen")
            break
        return values

    @staticmethod
    def _value(tok: Tuple[str, str]):
        kind, text = tok
        if kind == "quoted":
            if text.startswith("'"):
                return text[1:-1].replace("''", "'")
            return bytes(text[1:-1], "utf-8").decode("unicode_escape")
        if kind == "number":
            return float(text) if "." in text else int(text)
        if kind in ("true", "false"):
            return kind == "true"
        if kind == "null":
            return None
        if kind == "field":
            return text
        if kind == "word":
            return text
        raise MappingError(f"无法解析过滤值：{text or kind}")


_STATUS_MAP = {"A": 0, "B": 1, "C": 2, "D": 2, "Z": 0}


def _status_value(field: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    upper = value.strip().upper()
    if field.upper() in ("FDOCUMENTSTATUS", "DOCSTATUS", "STATUS") and upper in _STATUS_MAP:
        return _STATUS_MAP[upper]
    return value


def _operator(field: str, op: str) -> str:
    op = (op or "=").strip().lower()
    return {
        "=": "eq", "==": "eq", "!=": "ne", "<>": "ne",
        ">": "gt", ">=": "ge", "<": "lt", "<=": "le",
        "like": "like", "not like": "notlike",
        "in": "in", "not in": "nin",
    }.get(op, op)


def _criterion(form_id: str, field: str, op: str, value: Any) -> dict:
    mapped = map_field_path(form_id, field)
    return {
        "Field": mapped,
        "Operator": _operator(field, op),
        "Value": _status_value(field, value),
        "ValueIsField": False,
        "Logic": "and",
    }


def _convert_node(form_id: str, node) -> dict:
    kind = node[0]
    if kind == "cmp":
        _, field, op, value = node
        return _criterion(form_id, field, op, value)
    if kind == "in":
        _, field, values, negate = node
        joined = ",".join(str(v) for v in values)
        return _criterion(form_id, field, "not in" if negate else "in", joined)
    if kind == "between":
        _, field, low, high = node
        return {
            "Filters": [
                _criterion(form_id, field, ">=", low),
                _criterion(form_id, field, "<=", high),
            ],
            "Logic": "and",
            "ValueIsField": False,
        }
    if kind == "null":
        _, field, negate = node
        return _criterion(form_id, field, "ne" if negate else "eq", None)
    if kind in ("and", "or"):
        children = [_convert_node(form_id, child) for child in node[1]]
        return {
            "Filters": children,
            "Logic": kind,
            "ValueIsField": False,
        }
    raise MappingError(f"不支持的过滤节点：{kind}")


def build_filters(form_id: str, filter_string: str = "") -> List[dict]:
    raw = (filter_string or "").strip()
    if not raw:
        return []
    # 允许直接传 U9C 原生过滤 JSON（迁移期/高级场景）
    if raw[:1] in ("[", "{"):
        import json
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise MappingError(f"filter_string 以 JSON 开头但无法解析：{exc}") from exc
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        raise MappingError("原生 U9C 过滤 JSON 必须是对象或数组。")
    parser = _FilterParser(form_id, _tokenize(raw))
    node = parser.parse()
    if node[0] == "and":
        return [_convert_node(form_id, child) for child in node[1]]
    if node[0] == "or":
        return [_convert_node(form_id, node)]
    return [_convert_node(form_id, node)]


def build_orders(form_id: str, order_string: str = "") -> str:
    parts = []
    for token in (order_string or "").split(","):
        token = token.strip()
        if not token:
            continue
        bits = token.split()
        field = map_field_path(form_id, bits[0])
        direction = (bits[1] if len(bits) > 1 else "ASC").upper()
        if direction not in ("ASC", "DESC"):
            raise MappingError(f"排序方向必须是 ASC/DESC：{token}")
        parts.append(f"{field} {direction.lower()}")
    return ", ".join(parts)


def page_window(start_row: int, limit: int) -> Tuple[int, int, int]:
    limit = max(1, int(limit))
    start_row = max(0, int(start_row))
    return limit, start_row // limit + 1, start_row % limit


# ─────────────────────────────────────────────
# 保存模型转换
# ─────────────────────────────────────────────
_LEGACY_ENTRY_NAMES = {
    "FBillHead": None,
    "FPOOrderEntry": "POLineDTOList",
    "FPurchaseOrderEntry": "POLineDTOList",
    "FPurchaseOrderEntry1": "POLineDTOList",
    "FPurchaseOrderFinance": None,
    "FSaleOrderEntry": "SOLineDTOList",
    "FSaleOrderEntry1": "SOLineDTOList",
    "FSaleOrderFinance": None,
    "FEntity": "POLineDTOList",
    "FEntry": "POLineDTOList",
}

_FINANCE_MERGE_KEYS = {"FBillingOrgId", "FSettleOrgId", "FSettleCurrId", "FSettleTypeId", "FExchangeRate"}


_SCALAR_CODE_FIELDS = {
    "ItemCode", "OrderBy", "Seller", "SaleDepartment", "DocumentType",
    "TC", "AC", "ShipToSite", "BillToSite", "PayerCustomer", "PayerToSite",
    "TU", "PU", "TradePath", "ConfirmTermCode", "CustomerPONo",
}


def _value_for_field(field: str, value: Any, mapped: str) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            low = str(key).lower()
            if low in ("fnumber", "fcode", "code"):
                out["Code"] = item
            elif low == "fname":
                out["Name"] = item
            elif low == "fid":
                out["ID"] = item
            else:
                out[key] = item
        if mapped in _SCALAR_CODE_FIELDS:
            return out.get("Code", out.get("Name", value))
        return out
    if isinstance(value, str) and mapped.split(".", 1)[0] in _OBJECT_FIELDS:
        # 旧调用常传 FSupplierId: "S001"；U9C 要求对象 {Code: ...}
        return {"Code": value}
    return value


def _map_line(form_id: str, line: dict, entry_key: str) -> dict:
    header, line_fields, _ = _catalog_field_sets(form_id)
    out = {}
    for key, value in line.items():
        if key in line_fields:
            out[key] = value
            continue
        mapped = _field_alias(form_id, key)
        if mapped not in line_fields:
            raise MappingError(
                f"无法把分录字段「{key}」映射为 U9C 字段。{entry_key} 可用字段："
                + ", ".join(sorted(x for x in line_fields if x)[:60])
            )
        out[mapped] = _value_for_field(key, value, mapped)
    return out


def _is_known_alias(key: str) -> bool:
    return any(k.upper() == key.upper() for k in _GLOBAL_FIELD_ALIASES) or key.startswith("F")


def convert_model(form_id: str, model: dict) -> dict:
    """把旧版 F* 风格 model 转为 U9C Create/Modify DTO。"""
    if not isinstance(model, dict):
        raise MappingError("model 必须是 JSON 对象")
    catalog = u9c_catalog.form_fields(form_id)
    if not catalog.get("service"):
        raise MappingError(
            f"form_id「{form_id}」没有对应的 U9C Service，无法保存。"
            "请用 u9_list_forms 查看支持的服务，或先用数据库只读查询核对。"
        )
    header_fields = {f.get("name") for f in catalog.get("fields") or [] if f.get("name")}
    entries = {e.get("key"): e for e in catalog.get("entries") or [] if e.get("key")}
    first_entry = next(iter(entries), None)

    source = copy.deepcopy(model)
    # FBillHead 在旧协议里是主表包装；U9C 直接平铺
    if isinstance(source.get("FBillHead"), dict):
        merged = source.pop("FBillHead")
        for k, v in merged.items():
            source.setdefault(k, v)

    out: dict = {}
    unknown = []
    for key, value in source.items():
        if key in entries:
            target_entry = key
            if not isinstance(value, list):
                raise MappingError(f"分录「{key}」必须是数组")
            out[target_entry] = [_map_line(form_id, row, target_entry) for row in value if isinstance(row, dict)]
            continue
        if key in _LEGACY_ENTRY_NAMES:
            target_entry = _LEGACY_ENTRY_NAMES[key]
            if target_entry is None:
                if isinstance(value, dict):
                    # 财务信息等旧包装：字段能合并就合并，不能合并就报出来
                    for fk, fv in value.items():
                        mapped = _field_alias(form_id, fk)
                        if mapped in header_fields:
                            out[mapped] = _value_for_field(fk, fv, mapped)
                        else:
                            unknown.append(fk)
                continue
            if not isinstance(value, list):
                raise MappingError(f"分录「{key}」必须是数组")
            out[target_entry] = [_map_line(form_id, row, target_entry) for row in value if isinstance(row, dict)]
            continue
        if key in header_fields:
            out[key] = value
            continue
        mapped = _field_alias(form_id, key)
        if mapped in header_fields:
            out[mapped] = _value_for_field(key, value, mapped)
            continue
        # 允许服务端只读/第三方标识字段
        if key in ("OtherID",):
            out[key] = value
            continue
        unknown.append(key)

    if unknown:
        raise MappingError(
            f"以下字段无法映射到 U9C {catalog.get('service')} DTO：{', '.join(unknown[:20])}。"
            f"可用字段：{', '.join(sorted(x for x in header_fields if x)[:60])}"
            + (f"；分录字段请放在 {list(entries)} 中。" if entries else "")
        )
    # 新建时 ID=0 表示“由 U9C 生成”，不要原样传给 Create DTO。
    if out.get("ID") in (0, "0", None):
        out.pop("ID", None)
    return out


def convert_models(form_id: str, models: Sequence[dict]) -> List[dict]:
    if not isinstance(models, (list, tuple)) or not models:
        raise MappingError("models 必须是非空数组")
    return [convert_model(form_id, item) for item in models]


# ─────────────────────────────────────────────
# 动作解析
# ─────────────────────────────────────────────
_ACTION_CANDIDATES = {
    "submit": ("Submit", "SubmitAndApprove", "SubmitLine"),
    "audit": ("Approve", "Approved", "ApproveMo", "ApproveLine"),
    "unaudit": ("UnApprove", "UnApproved", "Unapprove", "UnApproveLine", "CancelApprove"),
    "delete": ("Delete", "DelSup", "DeleteMO", "Detele", "DeleteLine"),
    "close": ("Close", "CompleteMo"),
    "unclose": ("Open", "CompleteMo"),
    "void": ("Cancel", "CancelMo", "BipCancel"),
    "forbid": ("Forbid", "Disable", "Suspend"),
    "enable": ("Enable", "UnForbid", "Resume"),
    "cancel_assign": ("CancelReleaseSO", "CancelAssign"),
}

_OPERATION_ALIASES = {
    "SAVE": ("Create", "NewCreate", "CreateByAutoCode"),
    "BILLCLOSE": ("Close", "CompleteMo"),
    "YLBILLCLOSE": ("Close", "CompleteMo"),
    "BILLUNCLOSE": ("Open", "CompleteMo"),
    "UNCLOSE": ("Open", "CompleteMo"),
    "YLUNBILLCLOSE": ("Open", "CompleteMo"),
    "FORBID": ("Forbid", "Disable", "Suspend"),
    "ENABLE": ("Enable", "UnForbid", "Resume"),
    "AUDIT": ("Approve", "Approved", "ApproveMo"),
    "APPROVE": ("Approve", "Approved", "ApproveMo"),
    "UNAUDIT": ("UnApprove", "UnApproved", "Unapprove", "CancelApprove"),
    "UNAPPROVE": ("UnApprove", "UnApproved", "Unapprove", "CancelApprove"),
    "SUBMIT": ("Submit", "SubmitAndApprove"),
    "DELETE": ("Delete", "DelSup", "DeleteMO", "Detele"),
    "CANCEL": ("Cancel", "CancelMo", "BipCancel"),
    "UNINVALID": (),
    "CANCELASSIGN": ("CancelReleaseSO",),
}


def _hold_release_action(service: str, *, enable: bool) -> Optional[str]:
    """按 U9C 动作摘要解析挂起/解除挂起。

    U9C 的命名不统一：PurchaseOrder 的 ``Release`` 是“挂起”、``Hold`` 是
    “解除挂起”，而 Receivement 的 ``HoldLine`` 才是“挂起”。因此不能按
    其他 ERP 产品的习惯硬编码 Hold=禁用、Release=反禁用。
    """
    actions = u9c_catalog.service_actions(service)
    for name, info in actions.items():
        if "line" in name.lower():
            continue
        summary = str(info.get("summary") or "")
        if enable:
            if any(word in summary for word in ("解除", "反禁用", "启用", "恢复", "解冻")):
                return name
        else:
            if (
                any(word in summary for word in ("挂起", "禁用", "冻结", "停用"))
                and not any(word in summary for word in ("解除", "反禁用", "启用", "恢复", "解冻"))
            ):
                return name
    names = ("Enable", "UnForbid", "Resume") if enable else ("Forbid", "Disable", "Suspend")
    return u9c_catalog.resolve_action(service, *names)


def resolve_action(form_id: str, action: str, *, model: Any = None) -> Tuple[str, str]:
    """返回 ``(service, actual_action)``；不存在时抛出可读错误。"""
    service = service_for_form(form_id)
    if not service:
        raise MappingError(
            f"form_id「{form_id}」没有对应的 U9C Service。"
            "请用 u9_list_forms 搜索，或直接把 form_id 传成 U9C Service 名称（如 PurchaseOrder）。"
        )
    actions = u9c_catalog.service_actions(service)
    if not actions:
        raise MappingError(f"U9C Service「{service}」在 OpenAPI 目录中不存在。")

    op = (action or "").strip().lower()
    if op in ("save", "batch_save"):
        aid = None
        if isinstance(model, dict):
            aid = model.get("ID", model.get("FID"))
        elif isinstance(model, (list, tuple)) and model and isinstance(model[0], dict):
            aid = model[0].get("ID", model[0].get("FID"))
        if aid and str(aid) not in ("", "0", "None"):
            actual = u9c_catalog.resolve_action(service, "Modify")
            if not actual:
                raise MappingError(
                    f"{service} 只提供新增接口，未提供 Modify，不能按 ID 修改。"
                    "请新建，或先删除后重建。"
                )
            return service, actual
        actual = u9c_catalog.resolve_action(service, "Create", "NewCreate", "CreateByAutoCode")
        if not actual:
            raise MappingError(f"{service} 没有 Create/NewCreate 保存接口。可用动作：{', '.join(sorted(actions))}")
        return service, actual

    if op in ("forbid", "enable"):
        actual = _hold_release_action(service, enable=(op == "enable"))
        if actual:
            return service, actual
        raise MappingError(
            f"U9C Service「{service}」没有{'反禁用/启用' if op == 'enable' else '禁用/挂起'}动作。"
            f"该服务可用动作：{', '.join(sorted(actions))}"
        )

    candidates = _ACTION_CANDIDATES.get(op)
    if candidates is None:
        candidates = _OPERATION_ALIASES.get((action or "").upper(), (action,))
    actual = u9c_catalog.resolve_action(service, *candidates)
    if not actual:
        raise MappingError(
            f"U9C Service「{service}」不支持动作「{action}」。"
            f"该服务可用动作：{', '.join(sorted(actions))}"
        )
    return service, actual


def resolve_operation(form_id: str, operation: str) -> Tuple[str, str]:
    """解析 ``u9_execute_operation`` 的 operation（操作编码或中文/英文别名）。"""
    service = service_for_form(form_id)
    if not service:
        raise MappingError(f"form_id「{form_id}」没有对应的 U9C Service。")
    key = (operation or "").strip().upper()
    if key in ("FORBID", "ENABLE"):
        actual = _hold_release_action(service, enable=(key == "ENABLE"))
        if actual:
            return service, actual
        raise MappingError(
            f"U9C Service「{service}」没有操作「{operation}」。"
            f"可用动作：{', '.join(sorted(u9c_catalog.service_actions(service)))}"
        )
    candidates = _OPERATION_ALIASES.get(key, (operation,))
    actual = u9c_catalog.resolve_action(service, *candidates)
    if not actual:
        raise MappingError(
            f"U9C Service「{service}」没有操作「{operation}」。"
            f"可用动作：{', '.join(sorted(u9c_catalog.service_actions(service)))}"
        )
    return service, actual


def supports_action(form_id: str, action: str) -> bool:
    service = service_for_form(form_id)
    return bool(service and u9c_catalog.resolve_action(service, action))
