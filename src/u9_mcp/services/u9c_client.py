"""U9C OpenAPI 客户端：OAuth2 认证、token 请求、公共查询与标准动作。

协议要点（依据 https://openapi.yyu9c.com/file/U9COPENAPI.json）：

* 所有业务接口：``POST /webapi/{Service}/{Action}``，请求体直接是 DTO/数组，
  不再使用 ``{"data": "<JSON 字符串>"}`` 包装；
* 认证头：``token: <OAuth2 token>``；
* 统一响应：``{"ResCode": 0, "Success": true, "ResMsg": "", "Data": ..., "Exception": ""}``；
* 登录：GET ``/webapi/OAuth2/AuthLogin``（clientid/clientsecret/entCode/userCode/orgCode），
  兼容旧部署的 ``GetAuthorizeCode`` + ``Login`` 两步流程；
* 查询：POST ``/webapi/CommonEntity/Query``，参数结构见 ``ApiComParms``；
* 标准动作（提交/审核/删除/关闭…）：请求体为 ``OptDocRData[]``（ID/Code）。
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx

from ..config import settings, u9c_catalog
from . import u9c_mapping


_TOKEN: Optional[str] = None
_TOKEN_LOCK: Optional[asyncio.Lock] = None


class U9CError(RuntimeError):
    """U9C 认证/协议/业务错误。"""


def reset_token() -> None:
    """清除内存 token（测试与切换租户时使用）。"""
    global _TOKEN
    _TOKEN = None


def _get_token_lock() -> asyncio.Lock:
    global _TOKEN_LOCK
    if _TOKEN_LOCK is None:
        _TOKEN_LOCK = asyncio.Lock()
    return _TOKEN_LOCK


def _timeout() -> httpx.Timeout:
    try:
        total = float(vars(settings).get("U9C_TIMEOUT", 0) or 30)
    except Exception:
        total = 30.0
    return httpx.Timeout(total, connect=min(30.0, total))


def _client(timeout: Optional[httpx.Timeout] = None) -> httpx.AsyncClient:
    # 💡 U9/用友系服务对 HTTP/2 支持不稳定，保持显式 HTTP/1.1。
    return httpx.AsyncClient(
        timeout=timeout or _timeout(),
        proxy=None,
        transport=httpx.AsyncHTTPTransport(http1=True),
    )


def _url(path: str) -> str:
    base = settings.u9c_base_url()
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _service_url(service: str, action: str) -> str:
    return _url(f"/webapi/{service}/{action}")


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        return {
            "ResCode": resp.status_code or -1,
            "Success": False,
            "ResMsg": (resp.text or "").strip()[:2000],
            "Exception": "non-json-response",
            "Data": None,
        }


def _is_success_payload(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and bool(data.get("Success"))
        and int(data.get("ResCode") or 0) == 0
    )


def _token_expired(resp: httpx.Response, data: Any) -> bool:
    if resp.status_code == 401:
        return True
    if not isinstance(data, dict):
        return False
    if not _is_success_payload(data):
        text = " ".join(str(data.get(k) or "") for k in ("ResMsg", "Exception")).lower()
        return (
            str(data.get("ResCode")) in ("401", "-10001")
            or "token" in text and any(w in text for w in ("expire", "invalid", "过期", "无效", "未登录"))
            or "未登录" in text
            or "会话" in text
        )
    return False


def _auth_params() -> dict:
    params = {
        "clientid": settings.CLIENT_ID,
        "clientsecret": settings.CLIENT_SECRET,
        "entCode": settings.ENT_CODE,
        "userCode": settings.USERNAME,
        "orgCode": settings.ORG_CODE,
    }
    if settings.LOGIN_TYPE:
        params["loginType"] = settings.LOGIN_TYPE
    if settings.LOGIN_DATE:
        params["loginDate"] = settings.LOGIN_DATE
    if settings.LANGUAGE:
        params["language"] = settings.LANGUAGE
    return {k: v for k, v in params.items() if v not in (None, "")}


def _token_from(data: Any) -> Optional[str]:
    if _is_success_payload(data):
        value = data.get("Data")
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for key in ("Token", "token", "AccessToken", "access_token"):
                if value.get(key):
                    return str(value[key])
    return None


async def _auth_login() -> str:
    params = _auth_params()
    missing = [k for k in ("clientid", "clientsecret", "entCode", "userCode", "orgCode") if not params.get(k)]
    if missing:
        raise U9CError(
            "未配置 U9C OAuth2 登录参数：" + ", ".join(missing)
            + "。请设置 U9_API_CLIENT_ID / U9_API_CLIENT_SECRET / U9_API_ENT_CODE / "
              "U9_API_ORG_CODE / U9_API_USERNAME，或直接提供 U9_API_TOKEN。"
        )

    async with _client() as client:
        resp = await client.get(_url("/webapi/OAuth2/AuthLogin"), params=params)
        data = _safe_json(resp)
        token = _token_from(data)
        if token:
            return token

        # 兼容旧部署：先取授权码，再用授权码登录。
        try:
            code_resp = await client.get(
                _url("/webapi/OAuth2/GetAuthorizeCode"),
                params={"clientid": settings.CLIENT_ID, "clientsecret": settings.CLIENT_SECRET},
            )
            code_data = _safe_json(code_resp)
            code = code_data.get("Data") if isinstance(code_data, dict) else None
            if isinstance(code, str) and code.strip():
                login_resp = await client.get(
                    _url("/webapi/OAuth2/Login"),
                    params={
                        "entCode": settings.ENT_CODE,
                        "userCode": settings.USERNAME,
                        "orgCode": settings.ORG_CODE,
                        "code": code,
                        "loginType": settings.LOGIN_TYPE,
                        "language": settings.LANGUAGE,
                    },
                )
                login_data = _safe_json(login_resp)
                token = _token_from(login_data)
                if token:
                    return token
                data = login_data
        except Exception:
            pass

    raise U9CError(token_error_message(data) if isinstance(data, dict) else "U9C 登录失败")


async def _get_token(force: bool = False) -> str:
    global _TOKEN
    if settings.TOKEN and not _TOKEN:
        _TOKEN = settings.TOKEN
    if _TOKEN and not force:
        return _TOKEN
    async with _get_token_lock():
        if _TOKEN and not force:
            return _TOKEN
        if settings.TOKEN:
            # 静态 token 无法刷新：若同时提供了 OAuth2 凭证则降级重登，
            # 否则明确告知调用方更新 U9_API_TOKEN。
            credentials = all((
                settings.CLIENT_ID, settings.CLIENT_SECRET, settings.ENT_CODE,
                settings.USERNAME, settings.ORG_CODE,
            ))
            if not credentials:
                raise U9CError(
                    "静态 U9_API_TOKEN 已失效，且未配置 OAuth2 登录参数，无法自动续期。"
                    "请更新 U9_API_TOKEN，或配置 U9_API_CLIENT_ID / U9_API_CLIENT_SECRET / "
                    "U9_API_ENT_CODE / U9_API_ORG_CODE / U9_API_USERNAME。"
                )
        _TOKEN = await _auth_login()
        return _TOKEN


async def login() -> str:
    """执行 U9C 登录并返回 token（供 --check 与测试使用）。"""
    global _TOKEN
    if settings.TOKEN:
        _TOKEN = settings.TOKEN
        return _TOKEN
    return await _get_token(force=True)


def token_error_message(data: dict) -> str:
    parts = []
    for key in ("ResMsg", "Exception"):
        value = data.get(key)
        if value:
            parts.append(str(value))
    if data.get("ResCode") is not None:
        parts.append(f"ResCode={data.get('ResCode')}")
    return "U9C 登录失败：" + " | ".join(parts or ["未知错误"])


def _http_error(resp: httpx.Response) -> U9CError:
    sample = (resp.text or "").strip()[:500]
    return U9CError(f"U9C 接口 HTTP {resp.status_code}: {sample}")


async def request(
    service: str,
    action: str,
    body: Any = None,
    *,
    method: str = "POST",
    params: Optional[dict] = None,
    timeout: Optional[httpx.Timeout] = None,
    retry_auth: bool = True,
) -> Any:
    """调用 ``/webapi/{service}/{action}`` 并返回原始 ApiResult。

    token 过期（HTTP 401 / ResCode 401 / -10001 / 未登录）时自动重登并重试一次。
    写操作只有在确认是“认证失败”时才重试，避免业务失败被重复提交。
    """
    url = _service_url(service, action)
    attempts = 2 if retry_auth else 1
    last_exc: Optional[Exception] = None

    for attempt in range(attempts):
        token = await _get_token(force=(attempt > 0))
        headers = {"token": token, "Accept": "application/json"}
        try:
            async with _client(timeout) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, params=params, headers=headers)
                else:
                    resp = await client.post(url, json=body, params=params, headers=headers)
        except httpx.RequestError as exc:
            raise U9CError(f"U9C 接口网络异常 ({type(exc).__name__})") from exc

        data = _safe_json(resp)
        if resp.status_code >= 400:
            if attempt + 1 < attempts and _token_expired(resp, data):
                reset_token()
                continue
            raise _http_error(resp)
        if attempt + 1 < attempts and _token_expired(resp, data):
            reset_token()
            continue
        return data
    raise last_exc or U9CError("U9C 接口调用失败")


async def api_request(
    service: str,
    action: str,
    body: Any = None,
    *,
    method: str = "POST",
    params: Optional[dict] = None,
    timeout: Optional[httpx.Timeout] = None,
) -> Any:
    """同 :func:`request`，但对 HTTP 状态自动记录使用日志的薄封装入口。"""
    return await request(service, action, body, method=method, params=params, timeout=timeout)


def result_ok(data: Any) -> bool:
    return _is_success_payload(data)


def result_message(data: Any) -> str:
    if not isinstance(data, dict):
        return str(data)[:500]
    parts = []
    for key in ("ResMsg", "Exception"):
        if data.get(key):
            parts.append(str(data[key]))
    rows = data.get("Data")
    if isinstance(rows, list):
        for item in rows:
            if isinstance(item, dict):
                ok = item.get("IsSucess", item.get("IsSuccess", True))
                if ok is False and item.get("ErrorMsg"):
                    parts.append(str(item["ErrorMsg"]))
    return " | ".join(parts)


def _json_or_raw(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in ("{", "["):
            try:
                return json.loads(text)
            except Exception:
                return value
    return value


def _find_rows(value: Any, depth: int = 0) -> Optional[List[Any]]:
    if depth > 5:
        return None
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return None
    for key in ("RecordList", "Rows", "Records", "Result", "Items", "List", "Data", "data"):
        if key in value:
            rows = _find_rows(value[key], depth + 1)
            if rows is not None:
                return rows
    return None


def extract_query_result(payload: Any) -> dict:
    """把 U9C 查询响应的多种 Data 形状归一化为 ``{rows, total}``。"""
    data = payload
    if isinstance(payload, dict) and "Data" in payload:
        data = _json_or_raw(payload.get("Data"))
    total = None
    if isinstance(data, dict):
        total = data.get("RecordCount", data.get("TotalCount", data.get("total")))
    rows = _find_rows(data)
    if rows is None:
        if isinstance(data, dict) and data:
            rows = [data]
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
    if total is None:
        total = len(rows)
    return {"rows": rows, "total": total}


async def common_query(
    entity_full_name: str,
    return_fields: Sequence[str],
    *,
    filters: Optional[List[dict]] = None,
    orders: str = "",
    page_index: int = 1,
    page_size: int = 20,
) -> dict:
    """调用 U9C 公共查询 ``CommonEntity/Query``。"""
    body = {
        "PageSize": max(1, int(page_size)),
        "PageIndex": max(1, int(page_index)),
        "Orders": orders or "",
        "Filters": filters or [],
        "EntityFullName": entity_full_name,
        "ReturnFields": list(return_fields),
    }
    result = await request("CommonEntity", "Query", body)
    out = extract_query_result(result)
    out["result"] = result
    return out


async def common_query_form(
    form_id: str,
    field_keys: str = "",
    filter_string: str = "",
    order_string: str = "",
    start_row: int = 0,
    limit: int = 20,
) -> dict:
    """按本地 form_id 查询：自动完成 Service/实体、字段与过滤条件翻译。"""
    entity = u9c_mapping.entity_for_form(form_id)
    if not entity:
        service = u9c_catalog.resolve_service(form_id)
        if service and u9c_catalog.has_service(service):
            reason = (
                f"U9C 规范中有 Service「{service}」，但未收录对应的实体全名。"
                "请配置 U9_API_ENTITY_MAP 指向该实体。"
            )
        elif service:
            reason = (
                f"本地映射指向的 Service「{service}」不在 U9C OpenAPI 规范中，"
                "可能属于旧版对象或未开放对象。"
            )
        else:
            reason = (
                "该 form_id 在 U9C OpenAPI 规范中没有对应 Service/实体，"
                "可能属于旧版对象或未开放对象。"
            )
        raise U9CError(
            f"无法把 form_id「{form_id}」解析为 U9C 实体全名。{reason}"
            "可先用 u9_list_forms / u9_get_fields 查找等价对象；"
            "只读统计也可使用 u9_query_table / u9_execute_sql。"
        )
    fields = u9c_mapping.return_fields(form_id, field_keys)
    if not fields:
        raise U9CError(f"form_id「{form_id}」没有可用返回字段，请通过 field_keys 显式指定。")
    filters = u9c_mapping.build_filters(form_id, filter_string)
    orders = u9c_mapping.build_orders(form_id, order_string)

    page_size, page_index, skip = u9c_mapping.page_window(start_row, limit)
    # 为支持任意 start_row，多取一页再裁切。
    payload = await common_query(
        entity, fields, filters=filters, orders=orders,
        page_index=page_index, page_size=page_size,
    )
    rows = payload["rows"][skip:]
    return {
        "rows": rows[:limit],
        "total": payload.get("total"),
        "notice": u9c_mapping.query_notice(form_id, fields),
        "result": payload.get("result"),
    }


def _to_int_id(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        try:
            return int(text)
        except Exception:
            return value
    return value


def opt_doc_rdata(
    ids: Optional[Iterable[Any]] = None,
    codes: Optional[Iterable[Any]] = None,
    *,
    extra: Optional[dict] = None,
) -> List[dict]:
    """构造 U9C 标准动作的 ``OptDocRData[]`` 请求体。"""
    id_list = [x for x in (ids or []) if str(x).strip()]
    code_list = [x for x in (codes or []) if str(x).strip()]
    if not id_list and not code_list:
        raise U9CError("标准动作至少需要单据 ID 或单据编号 Code。")
    size = max(len(id_list), len(code_list))
    out: List[dict] = []
    for idx in range(size):
        item: dict = {}
        if idx < len(id_list):
            item["ID"] = _to_int_id(id_list[idx])
        if idx < len(code_list):
            item["Code"] = str(code_list[idx])
        if extra:
            item.update(extra)
        out.append(item)
    return out


async def standard_action(
    service: str,
    action: str,
    *,
    ids: Optional[Iterable[Any]] = None,
    codes: Optional[Iterable[Any]] = None,
    extra: Optional[dict] = None,
) -> Any:
    body = opt_doc_rdata(ids, codes, extra=extra)
    return await request(service, action, body)


async def post_action(service: str, action: str, body: Any) -> Any:
    return await request(service, action, body)


def status() -> dict:
    return {
        "protocol": "U9C OpenAPI",
        "base_url": settings.u9c_base_url(),
        "auth_configured": bool(settings.U9C_AUTH_CONFIGURED),
        "static_token": bool(settings.TOKEN),
        "client_id": bool(settings.CLIENT_ID),
        "ent_code": bool(settings.ENT_CODE),
        "org_code": bool(settings.ORG_CODE),
        "user_code": bool(settings.USERNAME),
        "token_cached": bool(_TOKEN),
    }


# 兼容旧模块对“session”的称呼（附件/测试会读取 client._session_id）。
def current_token() -> Optional[str]:
    return _TOKEN
