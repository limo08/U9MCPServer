"""U9C WebAPI 客户端适配层。

本模块保留旧工具层的公共函数签名（``_login`` / ``_post`` / ``_post_raw`` /
``_post_query`` / ``_query_payload``），内部实现已切换到 U9C OpenAPI：

* 认证：OAuth2 ``/webapi/OAuth2/AuthLogin``，请求头 ``token``；
* 查询：``/webapi/CommonEntity/Query``；
* 保存/提交/审核/删除/关闭：实体 Service 的 ``Create`` / ``Modify`` /
  ``Submit`` / ``Approve`` / ``UnApprove`` / ``Delete`` / ``Close`` / ``Open`` 等；
* 不再使用旧版动态表单端点、Cookie 会话或
  ``{"data": "<JSON 字符串>"}`` 请求体。
"""

import asyncio
import json
import time
from typing import Any, List, Optional

from ..config import settings
from ..config import u9c_catalog
from ..services import u9c_client, u9c_mapping
from ..services.no_fid import _LEARNED_NO_FID_FORMS, _form_lacks_fid, _is_no_fid_error, _strip_fid
from ..utils.formatting import _normalize_ids, _safe_json
from ..utils.usage_log import _sanitize_params, log_tool_usage


# 兼容旧模块名：U9C 的 token 在旧代码中常被称为 session。
_session_id: Optional[str] = None
_session_lock: Optional[asyncio.Lock] = None


def _get_session_lock() -> asyncio.Lock:
    global _session_lock
    if _session_lock is None:
        _session_lock = asyncio.Lock()
    return _session_lock


def _sync_token() -> None:
    """让旧的 ``_session_id`` 与新的 U9C token 缓存保持一致（便于测试/嵌入）。"""
    global _session_id
    if _session_id and not u9c_client._TOKEN:
        u9c_client._TOKEN = _session_id
    elif u9c_client._TOKEN:
        _session_id = u9c_client._TOKEN


async def _login() -> str:
    """登录 U9C，返回 OAuth2 token。

    所需环境变量：``U9_API_CLIENT_ID``、``U9_API_CLIENT_SECRET``、
    ``U9_API_ENT_CODE``、``U9_API_ORG_CODE``、``U9_API_USERNAME``；
    也可直接设置 ``U9_API_TOKEN`` 跳过登录。
    """
    global _session_id
    token = await u9c_client.login()
    _session_id = token
    return token


def _url(ep_key: str) -> str:
    """返回 U9C 端点 URL。

    ``ep_key`` 可以是 ``_EP`` 中的键，也可以直接是 ``Service/Action``。
    """
    path = settings._EP.get(ep_key, ep_key)
    return settings.u9c_base_url().rstrip("/") + "/webapi/" + path.lstrip("/")


def _log_api(ep_key: str, form_id: str, payload: Any, started: float,
             success: bool, error_type: str = "", error_msg: str = "") -> None:
    try:
        log_tool_usage(
            tool_name=f"api:{ep_key}",
            params=_sanitize_params({
                "ep_key": ep_key,
                "form_id": form_id or "",
                "payload_keys": list(payload.keys()) if isinstance(payload, dict) else [],
            }),
            duration_ms=(time.perf_counter() - started) * 1000,
            success=success,
            result_preview="" if success else error_msg[:200],
            error_type=error_type,
        )
    except Exception:
        pass


def _compat_query_result(query: dict, form_id: str, field_keys: str) -> dict:
    """把 U9C 查询结果包装成旧工具层能消费的结构。"""
    rows = query.get("rows") or []
    mapped_fields = u9c_mapping.field_mapping(form_id, field_keys)
    notice = query.get("notice") or ""
    if mapped_fields:
        notice = (notice + " " if notice else "") + (
            "字段已转换为 U9C 命名：" + ", ".join(f"{m['from']}→{m['to']}" for m in mapped_fields[:8])
            + (" 等" if len(mapped_fields) > 8 else "")
        )
    return {
        "Result": rows,
        "Data": rows,
        "ResCode": 0,
        "Success": True,
        "_u9c": query.get("result"),
        "_notice": notice,
        "_total": query.get("total"),
    }


async def _post(ep_key: str, payload: Any) -> Any:
    """执行查询/报表等只读调用（保留旧签名）。"""
    global _session_id
    started = time.perf_counter()
    form_id = ""
    success = False
    error_type = ""
    error_msg = ""
    try:
        _sync_token()

        if ep_key in ("save", "view"):
            if isinstance(payload, (tuple, list)) and len(payload) == 2:
                form_id, inner = payload
            else:
                inner = payload
                form_id = (inner or {}).get("FormId", "") if isinstance(inner, dict) else ""
            if ep_key == "save":
                if isinstance(inner, dict) and isinstance(inner.get("Model"), dict):
                    inner = inner["Model"]
                result = await _post_raw("save", form_id, inner or {})
            else:
                if isinstance(inner, dict) and isinstance(inner.get("Model"), dict):
                    inner = inner["Model"]
                result = await _post_raw("view", form_id, inner or {})
            success = u9c_client.result_ok(result) if isinstance(result, dict) else True
            return result

        if ep_key == "query":
            # 旧结构：{FormId, FieldKeys, FilterString, OrderString, StartRow, Limit}
            if isinstance(payload, (tuple, list)) and len(payload) == 2:
                form_id, params = payload
                params = params or {}
            else:
                params = payload or {}
                form_id = params.get("FormId", "")
            field_keys = params.get("FieldKeys", "")
            filter_string = params.get("FilterString", "")
            order_string = params.get("OrderString", "")
            start_row = int(params.get("StartRow", 0) or 0)
            limit = int(params.get("Limit", 20) or 20)
            query = await u9c_client.common_query_form(
                form_id, field_keys, filter_string, order_string, start_row, limit
            )
            success = True
            return _compat_query_result(query, form_id, field_keys)

        if ep_key == "report":
            if isinstance(payload, (tuple, list)) and len(payload) == 2:
                form_id, inner = payload
            else:
                form_id = (payload or {}).get("formid", "") if isinstance(payload, dict) else ""
                inner = payload
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except Exception:
                    inner = {"ReportCaseID": inner}
            request: dict = {}
            if isinstance(inner, dict):
                if inner.get("ReportCaseID"):
                    request["ReportCaseID"] = inner["ReportCaseID"]
                elif inner.get("SubscirbeReportName"):
                    request["SubscirbeReportName"] = inner["SubscirbeReportName"]
                elif inner.get("ReportName"):
                    request["SubscirbeReportName"] = inner["ReportName"]
            if not request and form_id:
                request["ReportCaseID"] = form_id
            if not request:
                raise u9c_client.U9CError(
                    "U9C 报表接口需要 ReportCaseID 或 SubscirbeReportName；"
                    "请把 data 传成 {\"ReportCaseID\": \"...\"}。"
                )
            result = await u9c_client.request("Report", "GetReportPdfFile", request)
            success = u9c_client.result_ok(result)
            return result

        if ep_key in ("metadata",):
            if isinstance(payload, (tuple, list)) and payload:
                form_id = payload[0]
            elif isinstance(payload, str):
                form_id = payload
            return await _metadata_catalog_result(form_id)

        raise u9c_client.U9CError(
            f"U9C OpenAPI 没有通用端点「{ep_key}」。"
            "请改用对应的 Service/Action，或使用 u9_query_bills / u9_get_fields。"
        )
    except Exception as exc:
        error_type = type(exc).__name__
        error_msg = str(exc)
        raise
    finally:
        _log_api(ep_key, form_id, payload, started, success, error_type, error_msg)


async def _metadata_catalog_result(form_id: str) -> dict:
    catalog = u9c_catalog.form_fields(form_id)
    if not catalog.get("service"):
        raise u9c_client.U9CError(f"form_id「{form_id}」没有对应的 U9C Service/字段目录。")
    return catalog


def _parse_ids_codes(model: dict) -> tuple[List[str], List[str]]:
    if not isinstance(model, dict):
        return [], []
    ids: List[str] = []
    codes: List[str] = []
    raw_ids = model.get("Ids", model.get("IDs", model.get("id", model.get("ID"))))
    if raw_ids not in (None, ""):
        normalized = _normalize_ids(raw_ids, ep_key="action")
        ids = [x for x in str(normalized).split(",") if x.strip()]
    raw_codes = model.get("Numbers", model.get("Codes", model.get("codes", model.get("Code"))))
    if raw_codes not in (None, ""):
        if isinstance(raw_codes, (list, tuple, set)):
            codes = [str(x).strip() for x in raw_codes if str(x).strip()]
        else:
            codes = [x.strip() for x in str(raw_codes).split(",") if x.strip()]
    return ids, codes


async def _view_bill(form_id: str, bill_id: str) -> dict:
    entity = u9c_mapping.entity_for_form(form_id)
    if not entity:
        raise u9c_client.U9CError(
            f"无法把 form_id「{form_id}」解析为 U9C 实体。请配置 U9_API_ENTITY_MAP。"
        )
    fields = u9c_catalog.default_return_fields(form_id, include_lines=True) or ["ID", "DocNo"]
    # 确保 ID 一定在返回字段里，便于定位
    if "ID" not in fields:
        fields.insert(0, "ID")
    filters = [{
        "Field": "ID", "Operator": "eq", "Value": bill_id,
        "ValueIsField": False, "Logic": "and",
    }]
    query = await u9c_client.common_query(entity, fields, filters=filters, page_index=1, page_size=1)
    rows = query["rows"]
    data = rows[0] if rows else None
    return {
        "ResCode": 0 if rows else 404,
        "Success": bool(rows),
        "ResMsg": "" if rows else f"未找到 ID={bill_id} 的单据",
        "Data": data,
    }


async def _push_bill(form_id: str, target_form_id: str, model: dict) -> Any:
    source_service = u9c_mapping.service_for_form(form_id)
    target_service = u9c_mapping.service_for_form(target_form_id)
    if source_service == "PurchaseOrder" and target_service == "SO":
        codes = model.get("Numbers") or model.get("Codes") or model.get("BillNos") or []
        if isinstance(codes, str):
            codes = [x.strip() for x in codes.split(",") if x.strip()]
        if not codes:
            raise u9c_client.U9CError("U9C POCreateSO 需要源采购订单编号（Numbers）。")
        body = [{"Code": code} for code in codes]
        return await u9c_client.request("PurchaseOrder", "POCreateSO", body)
    raise u9c_client.U9CError(
        f"U9C OpenAPI 没有通用的下推接口；当前仅支持 PurchaseOrder → SO 的 "
        f"POCreateSO（实际请求为 {source_service} → {target_service}）。"
        "其他下推请在 U9 单据转换/UI 中配置，或使用来源单据的 CreateXxxBySrc 接口。"
    )


async def _post_raw(ep_key: str, form_id: str, model: dict,
                     need_update_fields: Optional[List[str]] = None,
                     need_return_fields: Optional[List[str]] = None,
                     is_delete_entry: bool = True,
                     op_number: Optional[str] = None) -> Any:
    """执行写操作（保留旧签名，内部调用 U9C 实体接口）。"""
    started = time.perf_counter()
    success = False
    error_type = ""
    error_msg = ""
    try:
        _sync_token()

        if ep_key == "view":
            bill_id = (model or {}).get("Id", (model or {}).get("ID", ""))
            if bill_id in (None, ""):
                raise u9c_client.U9CError("view 需要 Id")
            result = await _view_bill(form_id, str(bill_id))
            success = bool(result.get("Success"))
            return result

        if ep_key in ("save", "batch_save"):
            models = [model] if ep_key == "save" else (model if isinstance(model, list) else [model])
            service, action = u9c_mapping.resolve_action(form_id, ep_key, model=model)
            if ep_key == "save":
                result = await u9c_client.post_action(
                    service, action, [u9c_mapping.convert_model(form_id, model)]
                )
                success = u9c_client.result_ok(result)
                return result

            # U9C 没有通用 BatchSave；把新增/修改分组，分别调用 Create / Modify。
            creates, modifies = [], []
            for item in models:
                converted = u9c_mapping.convert_model(form_id, item)
                raw_id = item.get("FID", item.get("ID")) if isinstance(item, dict) else None
                if raw_id in (None, 0, "0", "", "None"):
                    creates.append(converted)
                else:
                    modifies.append(converted)
            results: list = []
            if creates:
                service, act = u9c_mapping.resolve_action(form_id, "save", model=[])
                results.append(await u9c_client.post_action(service, act, creates))
            if modifies:
                service, act = u9c_mapping.resolve_action(form_id, "save", model={"ID": 1})
                results.append(await u9c_client.post_action(service, act, modifies))
            if len(results) == 1:
                result = results[0]
            else:
                rows = []
                for res in results:
                    data = res.get("Data") if isinstance(res, dict) else None
                    rows.extend(data if isinstance(data, list) else ([data] if data else []))
                result = {
                    "ResCode": 0 if all(u9c_client.result_ok(r) for r in results) else 1,
                    "Success": all(u9c_client.result_ok(r) for r in results),
                    "ResMsg": " | ".join(u9c_client.result_message(r) for r in results if not u9c_client.result_ok(r)),
                    "Data": rows,
                }
            success = u9c_client.result_ok(result)
            return result

        if ep_key == "execute":
            if not op_number:
                raise u9c_client.U9CError("execute 必须提供 operation（U9C Action 名或标准动作别名）。")
            service, action = u9c_mapping.resolve_operation(form_id, op_number)
            ids, codes = _parse_ids_codes(model or {})
            result = await u9c_client.standard_action(service, action, ids=ids, codes=codes)
            success = u9c_client.result_ok(result)
            return result

        if ep_key == "push":
            result = await _push_bill(form_id, (model or {}).get("TargetFormId", ""), model or {})
            success = u9c_client.result_ok(result)
            return result

        if ep_key in ("submit", "audit", "unaudit", "delete", "close", "unclose",
                      "void", "forbid", "enable", "cancel_assign"):
            ids, codes = _parse_ids_codes(model or {})
            service, action = u9c_mapping.resolve_action(form_id, ep_key)
            result = await u9c_client.standard_action(service, action, ids=ids, codes=codes)
            success = u9c_client.result_ok(result)
            return result

        raise u9c_client.U9CError(
            f"U9C 适配层不支持操作「{ep_key}」。支持：save/batch_save/submit/audit/"
            "unaudit/delete/close/unclose/void/forbid/enable/execute/push/view。"
        )
    except Exception as exc:
        error_type = type(exc).__name__
        error_msg = str(exc)
        raise
    finally:
        _log_api(ep_key, form_id, model, started, success, error_type, error_msg)


def _query_payload(form_id: str, field_keys: str, filter_string: str,
                   order_string: str, start_row: int, limit: int) -> dict:
    """旧查询参数结构（保留给 API 层与兼容测试；_post 会翻译成 U9C）。"""
    return {
        "FormId": form_id,
        "FieldKeys": field_keys,
        "FilterString": filter_string,
        "OrderString": order_string,
        "StartRow": start_row,
        "Limit": limit,
    }


async def _post_query(form_id: str, field_keys: str, filter_string: str,
                      order_string: str, start_row: int, limit: int) -> tuple:
    """查询数据；返回 ``(result, notice)``。"""
    notice = ""
    fk, od = field_keys, order_string
    if _form_lacks_fid(form_id):
        fk, od = _strip_fid(field_keys, order_string)
        notice = f"{form_id} 的查询视图没有 FID 列，已自动去掉 FID 字段与 FID 排序。"

    result = await _post("query", _query_payload(form_id, fk, filter_string,
                                                 od, start_row, limit))
    if isinstance(result, dict) and result.get("_notice"):
        notice = (notice + " " if notice else "") + str(result["_notice"])

    if not notice and _is_no_fid_error(result):
        _LEARNED_NO_FID_FORMS.add((form_id or "").strip().upper())
        fk, od = _strip_fid(field_keys, order_string)
        result = await _post("query", _query_payload(form_id, fk, filter_string,
                                                     od, start_row, limit))
        notice = f"{form_id} 的查询视图没有 FID 列，已自动去掉 FID 后重试。"

    if _is_no_fid_error(result):
        notice = (f"{form_id} 该基础资料不支持自动查询（查询视图缺主键列）。"
                  f"请先确认 U9C 实体名与字段，再用 u9_get_fields 查看可用字段。")
    return result, notice


def status() -> dict:
    """连接/认证状态（不发起网络请求）。"""
    _sync_token()
    return {
        **u9c_client.status(),
        "token": bool(u9c_client._TOKEN),
    }
