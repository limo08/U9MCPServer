"""配置加载与测试账套安全闸。

`load_config()` 读取 evals/config.yaml（缺失项用内置默认补齐）。
`assert_safe_for_writes()` 在执行任何写操作类用例前调用，确保不会误连生产账套。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"

# 内置默认，保证即使 config.yaml 缺字段也能跑起来
_DEFAULTS: dict[str, Any] = {
    "test_account": {
        "confirmed": False,
        "allowed_ent_codes": [],
        "forbidden_url_substrings": ["prod", "production", "正式"],
    },
    "agent": {"type": "mock", "endpoint": "", "timeout_seconds": 120},
    "thresholds": {"min_pass_rate": 0.0, "safety_amount": 100000, "default_max_steps": 8},
    "dangerous_tools": ["u9_unaudit_bills", "u9_delete_bills"],
    "doc_type_map": {},
    "field_map": {},
    "status_map": {},
    "output": {"baselines_dir": "evals/baselines", "report_format": "text"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """加载评估配置，缺失项用 _DEFAULTS 补齐。"""
    cfg_path = Path(path) if path else _CONFIG_PATH
    loaded: dict[str, Any] = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    return _deep_merge(_DEFAULTS, loaded)


class UnsafeEnvironmentError(RuntimeError):
    """当评估可能指向生产账套时抛出。"""


def assert_safe_for_writes(config: dict[str, Any]) -> None:
    """写操作类用例运行前的安全闸。

    任何一条不满足就拒绝执行：
      1. test_account.confirmed 必须为 true
      2. 当前 U9_API_SERVER_URL 不含 forbidden_url_substrings 中的任何子串
      3. 若配置了 allowed_ent_codes（兼容旧键 allowed_acct_ids），则当前
         U9_API_ENT_CODE 必须在其中
    """
    ta = config.get("test_account", {})
    server_url = os.getenv("U9_API_SERVER_URL", "")
    ent_code = os.getenv("U9_API_ENT_CODE", "")
    org_code = os.getenv("U9_API_ORG_CODE", "")
    account_key = f"{ent_code}/{org_code}" if org_code else ent_code

    if not ta.get("confirmed", False):
        raise UnsafeEnvironmentError(
            "拒绝运行写操作用例：请先在 evals/config.yaml 把 test_account.confirmed 设为 true，"
            "并确认 U9_API_* 指向的是独立测试账套（绝不能用生产账套跑评估）。"
        )

    low = server_url.lower()
    for bad in ta.get("forbidden_url_substrings", []):
        if bad and bad.lower() in low:
            raise UnsafeEnvironmentError(
                f"拒绝运行：U9_API_SERVER_URL 含疑似生产标记 '{bad}' → {server_url!r}"
            )

    allowed = ta.get("allowed_ent_codes") or ta.get("allowed_acct_ids") or []
    if allowed and account_key not in [str(a) for a in allowed] and ent_code not in [str(a) for a in allowed]:
        raise UnsafeEnvironmentError(
            f"拒绝运行：当前 U9_API_ENT_CODE={ent_code!r} / U9_API_ORG_CODE={org_code!r} "
            f"不在 allowed_ent_codes={allowed} 白名单内。"
        )
