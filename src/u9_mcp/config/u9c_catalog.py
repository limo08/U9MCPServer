"""U9C OpenAPI 静态目录。

数据来源：https://openapi.yyu9c.com/file/U9COPENAPI.json
（Knife4j 文档 ``/v3/api-docs/swagger-config`` 指向的 U9C OPENAPI 规范）。

本模块把 628 个 ``/webapi/{Service}/{Action}`` 端点、DTO schema 与本地
form_id 目录做映射，供以下能力离线使用：

* ``u9_list_forms`` / ``u9_get_fields``：无需先连通 U9 即可查看字段；
* 查询/保存/审核等工具：把 form_id 解析为 U9C Service 与实体全名；
* 标准动作解析：只允许调用该 Service 实际存在的 Action，避免“猜端点”。

⚠️ 规范中的 server 地址为 ``http://localhost:8080``，真实 U9 地址必须由
``U9_API_SERVER_URL`` 提供；本目录只保存协议形状，不包含任何租户信息。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


_SPEC_PATH = Path(__file__).resolve().parent.parent / "data" / "u9c_openapi.json"

# 本地 form_id → U9C Service（/webapi/{Service}/{Action} 的第一段）。
# 未列出的 form_id 若本身就是 Service 名（如 PurchaseOrder），也可直接使用。
FORM_TO_U9C_SERVICE: Dict[str, str] = {
    # 基础资料
    "BD_Material": "ItemMaster",
    "BD_Customer": "Customer",
    "BD_Supplier": "Supplier",
    "BD_Department": "Department",
    "BD_Empinfo": "PersonInfoDoc",
    "BD_Stock": "Location",
    "BD_Unit": "UOM",
    "BD_Currency": "Currency",
    "BD_User": "UserInfo",
    # 采购
    "PUR_PurchaseOrder": "PurchaseOrder",
    "PUR_ReceiveBill": "Receivement",
    "PUR_MRB": "RMR",
    "PUR_Requisition": "PR",
    "PUR_MRAPP": "RMR",
    "PUR_Contract": "PC",
    "PUR_PriceCategory": "PurPriceList",
    "PUR_PAT": "PurPriceAdjustment",
    "SVM_InquiryBill": "RequestForQuotation",
    "SVM_QuoteBill": "SupplierQuotation",
    "SVM_ComparePrice": "ComparePrice",
    # 销售
    "SAL_SaleOrder": "SO",
    "SAL_OUTSTOCK": "Ship",
    "SAL_RETURNSTOCK": "RMA",
    "SAL_Quotation": "Quot",
    "SAL_DELIVERYNOTICE": "ShipPlan",
    "SAL_RetuenNotice": "RMA",
    "SAL_AvailableQuery": "ItemQty",
    # 库存
    "STK_InStock": "Receivement",
    "STK_MisDelivery": "MiscShip",
    "STK_Miscellaneous": "MiscRcvTrans",
    "STK_TransferDirect": "TransferForm",
    "STK_Inventory": "ItemQty",
    "STK_StockCountInput": "InventorySheet",
    "STK_TransferApply": "TransferApply",
    "STK_TRANSFERIN": "TransferIn",
    "STK_TRANSFEROUT": "TransferOut",
    "STK_AssembledApp": "AssemblyDoc",
    "STK_OutStockApply": "IssueApplyDoc",
    "STK_StatusConvert": "StatusConvertDoc",
    # 质量 / 财务
    "QIS_InspectBill": "QCDoc",
    "AP_Payable": "APBill",
    "AR_Receivable": "ARBill",
    "FA_FAGet": "AssetCard",
    "FA_AssetCard": "AssetCard",
    # 二开单据没有 U9C 标准端点，必须由 CommonEntity 实体名配置覆盖
    "TRNV_Receipt": "TRNV_Receipt",
    "TRNV_PaymentSlip": "TRNV_PaymentSlip",
    # 生产 / 委外
    "SUB_SubReqOrder": "MODoc",
    "PRD_MO": "MODoc",
    "PRD_PickMtrl": "IssueDoc",
    "PRD_Instock": "RcvRptDoc",
    # 费用
    "ER_ExpenseRequest": "PayReqFund",
    "ER_ExpenseReimburse": "ReimBill",
}

# U9C Service → 业务实体全名（CommonEntity/Query 的 EntityFullName）。
# 说明：U9C 文档没有提供“Service → EntityFullName”的机器可读映射，这里只收录
# 已确认/按用友命名空间惯例可判定的条目；其余可设置 U9C_ENTITY_MAP_FILE 覆盖，
# 或直接把 form_id 传成完整的 UFIDA.U9.* 实体名。
SERVICE_TO_U9C_ENTITY: Dict[str, str] = {
    "PurchaseOrder": "UFIDA.U9.PM.PO.PurchaseOrder",
    "PR": "UFIDA.U9.PM.PR.PR",
    "Receivement": "UFIDA.U9.PM.Rcv.Receivement",
    "RMR": "UFIDA.U9.PM.RMR.RMR",
    "SO": "UFIDA.U9.SM.SO.SO",
    "Ship": "UFIDA.U9.SM.Ship.Ship",
    "RMA": "UFIDA.U9.SM.RMA.RMA",
    "Quot": "UFIDA.U9.SM.Quot.Quot",
    "ShipPlan": "UFIDA.U9.SM.ShipPlan.ShipPlan",
    "ItemMaster": "UFIDA.U9.CBO.SCM.Item.ItemMaster",
    "Customer": "UFIDA.U9.CBO.SCM.Customer.Customer",
    "Supplier": "UFIDA.U9.CBO.SCM.Supplier.Supplier",
    "Department": "UFIDA.U9.CBO.HR.Department",
    "UOM": "UFIDA.U9.Base.UOM.UOM",
    "Currency": "UFIDA.U9.Base.Currency.Currency",
    "Location": "UFIDA.U9.CBO.SCM.Inv.Location",
    "ItemQty": "UFIDA.U9.CBO.SCM.Item.ItemQty",
    "InventorySheet": "UFIDA.U9.InvDoc.InventorySheet.InventorySheet",
    "MiscShip": "UFIDA.U9.InvDoc.MiscShip.MiscShip",
    "MiscRcvTrans": "UFIDA.U9.InvDoc.MiscRcvTrans.MiscRcvTrans",
    "TransferForm": "UFIDA.U9.InvDoc.TransferForm.TransferForm",
    "TransferApply": "UFIDA.U9.InvDoc.TransferApply.TransferApply",
    "TransferIn": "UFIDA.U9.InvDoc.TransferIn.TransferIn",
    "TransferOut": "UFIDA.U9.InvDoc.TransferOut.TransferOut",
    "IssueApplyDoc": "UFIDA.U9.InvDoc.IssueApplyDoc.IssueApplyDoc",
    "QCDoc": "UFIDA.U9.QC.QCDoc.QCDoc",
    "APBill": "UFIDA.U9.AP.APBill.APBill",
    "ARBill": "UFIDA.U9.AR.ARBill.ARBill",
    "MODoc": "UFIDA.U9.MO.MODoc.MODoc",
    "IssueDoc": "UFIDA.U9.MO.IssueDoc.IssueDoc",
    "RcvRptDoc": "UFIDA.U9.MO.RcvRptDoc.RcvRptDoc",
    "ReimBill": "UFIDA.U9.ER.ReimBill.ReimBill",
    "PayReqFund": "UFIDA.U9.ER.PayReqFund.PayReqFund",
    "PurPriceList": "UFIDA.U9.PPR.PurPriceList.PurPriceList",
    "PurPriceAdjustment": "UFIDA.U9.PPR.PurPriceAdjustment.PurPriceAdjustment",
    "PersonInfoDoc": "UFIDA.U9.CBO.HR.Person",
    "UserInfo": "UFIDA.U9.CBO.Sys.UserInfo",
}

# DTO 字段里“分录列表属性” → CommonEntity 查询路径的常见映射。
# 仅用于生成默认返回字段/视图字段；未知的列表属性不会强行猜。
_LINE_PATH_MAP = {
    "POLineDTOList": "POLines",
    "SOLineDTOList": "SOLines",
    "SOShiplineDTOList": "SOShiplines",
    "DocLineList": "DocLines",
    "Lines": "Lines",
}


@lru_cache(maxsize=1)
def load_spec() -> dict:
    """读取打包的 U9C OpenAPI 规范（只读、进程内缓存）。"""
    with open(_SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _operations_index() -> Dict[str, Dict[str, dict]]:
    """``{Service: {Action: operation}}``。"""
    index: Dict[str, Dict[str, dict]] = {}
    for path, methods in (load_spec().get("paths") or {}).items():
        if not path.startswith("/webapi/"):
            continue
        rest = path[len("/webapi/"):]
        if "/" not in rest:
            continue
        service, action = rest.split("/", 1)
        if "{" in action or "/" in action:
            continue
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            index.setdefault(service, {})[action] = {
                "method": method.upper(),
                "path": path,
                "summary": op.get("summary") or "",
                "operation_id": op.get("operationId") or "",
                "tags": op.get("tags") or [],
                "parameters": op.get("parameters") or [],
            }
    return index


def services() -> List[str]:
    return sorted(_operations_index())


def service_actions(service: str) -> Dict[str, dict]:
    """返回 Service 实际支持的 Action（大小写以规范为准）。"""
    if not service:
        return {}
    hit = _operations_index().get(service)
    if hit is None:
        lower = service.lower()
        for name, actions in _operations_index().items():
            if name.lower() == lower:
                return actions
        return {}
    return hit


def has_service(service: str) -> bool:
    return bool(service_actions(service))


def resolve_action(service: str, *candidates: str) -> Optional[str]:
    """在 Service 支持的 Action 中按候选名（大小写不敏感）选择一个。"""
    actions = service_actions(service)
    if not actions:
        return None
    lower_map = {name.lower(): name for name in actions}
    for candidate in candidates:
        hit = lower_map.get((candidate or "").lower())
        if hit:
            return hit
    return None


def resolve_service(form_id: str) -> Optional[str]:
    """form_id / Service / tag → U9C Service。"""
    raw = (form_id or "").strip()
    if not raw:
        return None
    mapped = FORM_TO_U9C_SERVICE.get(raw) or FORM_TO_U9C_SERVICE.get(raw.upper())
    if mapped:
        return mapped
    if has_service(raw):
        return raw
    lower = raw.lower()
    for service in _operations_index():
        if service.lower() == lower:
            return service
    return None


def resolve_entity(form_id: str) -> Optional[str]:
    """解析 CommonEntity/Query 的 EntityFullName。

    优先级：完整实体名（UFIDA.U9.*） > 环境变量/JSON 文件覆盖 > 内置映射。
    """
    raw = (form_id or "").strip()
    if raw.startswith("UFIDA.U9.") or raw.startswith("UFSoft."):
        return raw
    from . import settings

    override = settings.entity_map().get(raw) or settings.entity_map().get(raw.upper())
    if override:
        return override
    service = resolve_service(raw)
    return SERVICE_TO_U9C_ENTITY.get(service or "")


def _schema(name_ref: str) -> Optional[dict]:
    if not name_ref:
        return None
    name = name_ref.split("/")[-1]
    return (load_spec().get("components", {}).get("schemas") or {}).get(name)


def _ref_name(node: Any) -> str:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            return ref.split("/")[-1]
    return ""


def _dto_name_for_action(service: str, action: str) -> Optional[str]:
    op = service_actions(service).get(action)
    if not op:
        return None
    for param in op.get("parameters") or []:
        if param.get("in") != "body":
            continue
        schema = param.get("schema") or {}
        ref = _ref_name(schema)
        if ref:
            return ref
        items = schema.get("items") or {}
        ref = _ref_name(items)
        if ref:
            return ref
    return None


def _properties(dto_name: str) -> List[dict]:
    schema = _schema(dto_name) or {}
    required = set(schema.get("required") or [])
    out: List[dict] = []
    for name, node in (schema.get("properties") or {}).items():
        if not isinstance(node, dict):
            continue
        out.append({
            "name": name,
            "type": node.get("type") or ("object" if node.get("$ref") else ""),
            "description": (node.get("description") or "").replace("\r", " ").replace("\n", " ").strip(),
            "required": name in required,
            "ref": _ref_name(node),
            "items_ref": _ref_name((node.get("items") or {}) if isinstance(node.get("items"), dict) else {}),
        })
    return out


def _pick_dto(service: str) -> tuple[Optional[str], Optional[str]]:
    """选择一个能代表实体字段的 DTO：优先 Create / Modify，其次 Query。"""
    actions = service_actions(service)
    preferred = (
        "Create", "NewCreate", "CreateByAutoCode", "CreateByAttributes",
        "CreateBySrc", "Modify", "CreateOrUpdate", "Query", "QueryPage", "QrySupplier",
    )
    for action in preferred:
        if action not in actions:
            continue
        dto = _dto_name_for_action(service, action)
        if not dto:
            continue
        props = _properties(dto)
        # 过滤查询专用包装 DTO（只有 ItemMaster/OtherID 这类）
        if props and not (len(props) <= 2 and any(p["name"] in ("ItemMaster", "OtherID") for p in props)):
            return action, dto
    for action in actions:
        dto = _dto_name_for_action(service, action)
        if dto and _properties(dto):
            return action, dto
    return None, None


def service_fields(service: str) -> dict:
    """返回某 Service 的代表性 DTO 字段与分录结构。"""
    action, dto = _pick_dto(service)
    if not dto:
        return {"service": service, "actions": sorted(service_actions(service)),
                "dto": None, "fields": [], "entries": []}
    fields, entries = [], []
    for prop in _properties(dto):
        if prop["type"] == "array" and prop["items_ref"]:
            line_fields = _properties(prop["items_ref"])
            if line_fields:
                entries.append({
                    "key": prop["name"],
                    "caption": prop["description"],
                    "source_dto": prop["items_ref"],
                    "fields": line_fields,
                    "path": _LINE_PATH_MAP.get(prop["name"]),
                })
                continue
        fields.append(prop)
    return {
        "service": service,
        "dto": dto,
        "dto_action": action,
        "actions": sorted(service_actions(service)),
        "fields": fields,
        "entries": entries,
    }


def form_fields(form_id: str) -> dict:
    """form_id → U9C Service 字段目录。"""
    service = resolve_service(form_id)
    if not service:
        return {"form_id": form_id, "service": None, "entity": None,
                "actions": [], "fields": [], "entries": []}
    out = service_fields(service)
    out["form_id"] = form_id
    out["entity"] = resolve_entity(form_id)
    return out


def form_operations(form_id: str) -> List[dict]:
    """form_id 在 U9C 上真实支持的 Action 列表。"""
    service = resolve_service(form_id)
    if not service:
        return []
    return [
        {"number": action, "name": meta.get("summary") or action,
         "method": meta.get("method"), "path": meta.get("path")}
        for action, meta in service_actions(service).items()
    ]


def default_return_fields(form_id: str, include_lines: bool = False) -> List[str]:
    """生成 CommonEntity/Query 的默认 ReturnFields。"""
    catalog = form_fields(form_id)
    fields: List[str] = []
    for f in catalog.get("fields") or []:
        if f.get("name"):
            fields.append(f["name"])
    if include_lines:
        for entry in catalog.get("entries") or []:
            path = entry.get("path")
            if not path:
                continue
            for line in entry.get("fields") or []:
                if line.get("name"):
                    fields.append(f"{path}.{line['name']}")
    # 排除纯粹的 DTO 包装字段，Limit 防止一次返回过宽
    return fields[:120]


def search_services(keyword: str = "") -> List[dict]:
    """按 Service 名或操作摘要搜索 U9C Service。"""
    kw = (keyword or "").lower()
    out = []
    for service, actions in sorted(_operations_index().items()):
        summaries = " ".join((a.get("summary") or "") for a in actions.values())
        if kw and kw not in service.lower() and kw not in summaries.lower():
            continue
        out.append({
            "service": service,
            "actions": sorted(actions),
            "action_count": len(actions),
            "summary": next((a.get("summary") for a in actions.values() if a.get("summary")), ""),
        })
    return out
