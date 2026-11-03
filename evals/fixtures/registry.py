"""夹具注册表。

每个夹具负责一类基础数据的 prepare（准备/确保存在）与 cleanup（清理评估产物）。
用 @fixture("名字") 注册，用例的 setup.fixtures 用名字引用。

约定：
  - prepare(client, config) -> dict   返回该夹具准备结果（如 已存在的供应商编号）
  - cleanup(client, config) -> None   清理上一轮评估产生的、带标记的单据

注意：当前夹具多为骨架/TODO——确保基础资料存在通常依赖测试账套预置或专用导入接口，
这里只查询确认是否存在并给出告警，不擅自写入。真正的准备逻辑请按测试账套补全。
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..sandbox.u9_client import U9StateClient

# 评估创建的单据建议统一带这个备注前缀，便于 cleanup 按标记清理
EVAL_TAG = "[EVAL]"

PrepareFn = Callable[[U9StateClient, dict], Awaitable[dict]]
CleanupFn = Callable[[U9StateClient, dict], Awaitable[None]]

_PREPARE: dict[str, PrepareFn] = {}
_CLEANUP: dict[str, CleanupFn] = {}


def fixture(name: str, cleanup: CleanupFn | None = None):
    """注册一个 prepare 夹具，可选附带 cleanup。"""
    def deco(fn: PrepareFn) -> PrepareFn:
        _PREPARE[name] = fn
        if cleanup is not None:
            _CLEANUP[name] = cleanup
        return fn
    return deco


async def prepare(name: str, client: U9StateClient, config: dict) -> dict:
    fn = _PREPARE.get(name)
    if fn is None:
        # 未注册的夹具：不阻断评估，记一条告警
        return {"name": name, "status": "missing", "warning": f"夹具 '{name}' 未注册（TODO）"}
    return await fn(client, config)


async def cleanup_all(client: U9StateClient, config: dict) -> None:
    for fn in _CLEANUP.values():
        await fn(client, config)


# ─────────────────────────────────────────────────────────────
# 内置夹具（骨架）。只做"确认存在"，不擅自写基础资料。
# ─────────────────────────────────────────────────────────────

@fixture("supplier_A")
async def _supplier_a(client: U9StateClient, config: dict) -> dict:
    """确保示例供应商存在（默认按编号 'A' 查；按测试账套改 filter）。"""
    rows = await client.query(
        "BD_Supplier", ["FSupplierId", "FNumber", "FName"],
        "FNumber='A'", limit=1,
    )
    return {
        "name": "supplier_A",
        "exists": bool(rows),
        "data": rows[0] if rows else None,
        # TODO: 不存在时通过基础资料 Save 接口创建，或在测试账套预置
    }


@fixture("material_luosi")
async def _material_luosi(client: U9StateClient, config: dict) -> dict:
    """确保示例物料（螺丝）存在。"""
    rows = await client.query(
        "BD_Material", ["FMaterialId", "FNumber", "FName"],
        "FName like '%螺丝%'", limit=1,
    )
    return {
        "name": "material_luosi",
        "exists": bool(rows),
        "data": rows[0] if rows else None,
        # TODO: 不存在时创建物料，或在测试账套预置
    }
