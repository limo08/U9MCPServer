"""运行配置：环境变量、U9C OpenAPI 认证、SQL Server 连接参数。

本版本默认使用 **U9C OpenAPI**（``/webapi/{Service}/{Action}`` + ``token`` 头）。
历史版本的旧接口协议不再支持；如需旧协议，请使用重构前的历史版本。
"""

import json
import os
from functools import lru_cache


def _env(name: str, default: str = "") -> str:
    """读取 U9_* 环境变量（MCP 运行参数，如 U9_MCP_PORT）。"""
    return os.getenv(f"U9_{name}") or default


def _api_env(name: str, default: str = "") -> str:
    """读取用友接口配置（U9_API_*）。"""
    return os.getenv(f"U9_API_{name}") or default


# ─────────────────────────────────────────────
# 使用日志模块（改进反馈层）
# 记录每次工具调用的参数、耗时、结果，用于分析改进 MCP
# ─────────────────────────────────────────────
_USAGE_LOG_FILE = os.environ.get("MCP_USAGE_LOG", "usage_log.jsonl")

# ─────────────────────────────────────────────
# 连接配置（从环境变量读取）
# ─────────────────────────────────────────────
# U9C 服务根地址（不要以 /webapi 结尾；真实地址按部署环境填写）
SERVER_URL = _api_env("SERVER_URL", "http://localhost:8080").rstrip("/")

# U9C OAuth2 应用凭证与登录上下文
CLIENT_ID     = _api_env("CLIENT_ID") or _api_env("APP_ID")
CLIENT_SECRET = _api_env("CLIENT_SECRET") or _api_env("APP_SEC")
ENT_CODE      = _api_env("ENT_CODE") or _api_env("ACCT_ID")
ORG_CODE      = _api_env("ORG_CODE")
USERNAME      = _api_env("USERNAME") or _api_env("USER_CODE")
TOKEN         = _api_env("TOKEN")            # 可选：直接注入已签发的 token
LANGUAGE      = _api_env("LANGUAGE", "zh-CN")
LOGIN_TYPE    = int(_api_env("LOGIN_TYPE", "1") or "1")
LOGIN_DATE    = _api_env("LOGIN_DATE")       # 可选：上下文日期 yyyy-MM-dd
TOKEN_TIMEOUT = float(_api_env("TOKEN_TIMEOUT", "0") or "0")

# 兼容旧配置读取（旧协议字段已不再使用；保留符号避免第三方代码 import 失败）
ACCT_ID  = ENT_CODE
PASSWORD = _api_env("PASSWORD")
LCID     = int(_env("LCID", "2052"))

# 认证是否齐全（用于 --check 与错误提示）。TOKEN 直填时只需 SERVER_URL。
U9C_AUTH_CONFIGURED = bool(SERVER_URL and (TOKEN or (CLIENT_ID and CLIENT_SECRET and ENT_CODE and USERNAME and ORG_CODE)))


@lru_cache(maxsize=1)
def entity_map() -> dict:
    """读取 form_id/Service → EntityFullName 的覆盖映射。

    支持:
      * ``U9_API_ENTITY_MAP``：内联 JSON，如 ``{"PUR_PurchaseOrder":"UFIDA.U9..."}``
      * ``U9_API_ENTITY_MAP_FILE``：JSON 文件路径
    """
    data = {}
    path = os.getenv("U9_API_ENTITY_MAP_FILE", "")
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f) or {}
            if isinstance(loaded, dict):
                data.update({str(k): str(v) for k, v in loaded.items() if v})
        except Exception:
            pass
    inline = os.getenv("U9_API_ENTITY_MAP", "")
    if inline:
        try:
            loaded = json.loads(inline)
            if isinstance(loaded, dict):
                data.update({str(k): str(v) for k, v in loaded.items() if v})
        except Exception:
            pass
    return data


def u9c_base_url() -> str:
    """规范化 U9C 根地址：去掉末尾斜杠及常见的 ``/webapi`` 后缀。"""
    url = (SERVER_URL or "").rstrip("/")
    if url.lower().endswith("/webapi"):
        url = url[: -len("/webapi")]
    return url

# ─────────────────────────────────────────────
# SQL Server 探查配置（可选，从环境变量读取）
# ─────────────────────────────────────────────
_SQL_HOST     = os.getenv("MCP_SQLSERVER_HOST", "")
_SQL_PORT     = os.getenv("MCP_SQLSERVER_PORT", "1433")
_SQL_USER     = os.getenv("MCP_SQLSERVER_USER", "")
_SQL_PASSWORD = os.getenv("MCP_SQLSERVER_PASSWORD", "")
_SQL_DATABASE = os.getenv("MCP_SQLSERVER_DATABASE", "")
_SQL_SCHEMA   = os.getenv("MCP_SQLSERVER_SCHEMA", "dbo")
_SQL_ENABLED  = bool(_SQL_HOST and _SQL_DATABASE and _SQL_USER and _SQL_PASSWORD)


# U9C OpenAPI 固定入口（其余 Service/Action 见 config/u9c_catalog.py）
_EP = {
    "login_user": "OAuth2/AuthLogin",
    "authorize_code": "OAuth2/GetAuthorizeCode",
    "login": "OAuth2/Login",
    "refresh_token": "OAuth2/RefreshToken",
    "destroy_token": "OAuth2/DestroyToken",
    "query": "CommonEntity/Query",
    "query_new": "CommonEntity/QueryNew",
    "attachment_upload": "AttachmentFile/AttachmentFileUpload",
    "attachment_download": "AttachmentFile/AttachmentFileDownload",
    "attachment_download_by_doc": "AttachmentFile/AttachmentFileDownloadByDocID",
    "attachment_delete": "AttachmentFile/AttachmentFileDelete",
    "report": "Report/GetReportPdfFile",
}


# A per-call MCP limit, not a U9 server limit. Larger files use chunks.
_ATTACHMENT_CHUNK_BYTES = 4 * 1024 * 1024
_ATTACHMENT_BASE64_LENGTH = 4 * ((_ATTACHMENT_CHUNK_BYTES + 2) // 3)
