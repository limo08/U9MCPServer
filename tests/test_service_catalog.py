"""业务域服务目录与工具过滤的回归测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from u9_mcp.api import registered_tool_names
from u9_mcp.config.service_catalog import (
    ALL_SERVICE,
    ROLE_BUNDLES,
    SERVICE_IDS,
    SERVICES,
    all_service_tool_names,
    normalize_service_selection,
    resolve_service_tools,
    role_bundle_tools,
)

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_has_expected_services_and_tools():
    assert len(SERVICES) == 13
    assert len(SERVICE_IDS) == 13
    assert len(all_service_tool_names()) == 107
    assert len(set(all_service_tool_names())) == 107


def test_catalog_tools_are_disjoint():
    seen: set[str] = set()
    duplicates: set[str] = set()
    for service in SERVICES.values():
        for tool in service.tools:
            if tool in seen:
                duplicates.add(tool)
            seen.add(tool)
    assert not duplicates, f"工具被分配到多个服务：{sorted(duplicates)}"


def test_catalog_matches_registered_tools():
    assert set(all_service_tool_names()) == set(registered_tool_names())


def test_each_service_is_under_agent_limit():
    for service in SERVICES.values():
        assert service.tool_count <= 50, (
            f"{service.id} 有 {service.tool_count} 个工具，超过 50"
        )


@pytest.mark.parametrize("role_id", sorted(ROLE_BUNDLES))
def test_role_bundle_is_under_agent_limit(role_id: str):
    tools = role_bundle_tools(role_id)
    assert 0 < len(tools) <= 50, (
        f"角色组合 {role_id} 有 {len(tools)} 个工具，超过 50"
    )


def test_service_selection_parsing():
    assert normalize_service_selection(None) == (ALL_SERVICE,)
    assert normalize_service_selection("all") == (ALL_SERVICE,)
    assert normalize_service_selection("u9-bill") == ("u9-bill",)
    assert normalize_service_selection("u9-bill, u9-purchase") == (
        "u9-bill",
        "u9-purchase",
    )
    assert normalize_service_selection("u9-bill,u9-bill") == ("u9-bill",)
    with pytest.raises(ValueError):
        normalize_service_selection("not-a-service")


def test_resolve_service_tools():
    assert resolve_service_tools("all") is None
    assert len(resolve_service_tools("u9-bill") or ()) == 18
    assert len(resolve_service_tools("u9-bill,u9-purchase") or ()) == 23


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_apply_service_filter_only_keeps_selected_tools():
    code = (
        "from u9_mcp.api import apply_service_filter\n"
        "names = apply_service_filter('u9-bill')\n"
        "print(len(names))\n"
        "print('\\n'.join(sorted(names)))\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "18"
    assert "u9_save_bill" in lines
    assert "u9_query_inventory" not in lines
    assert "u9_query_purchase_orders" not in lines


def test_cli_list_services_and_roles():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    for option in ("--list-services", "--list-roles"):
        result = subprocess.run(
            [sys.executable, "-m", "u9_mcp.server", option],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "u9-bill" in result.stdout
        assert "107" in result.stdout or option == "--list-roles"
