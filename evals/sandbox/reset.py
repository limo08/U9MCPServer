"""Sandbox —— 测试账套的重置与夹具准备。

重置策略说明（重要、且环境相关，故默认保守）：
  用友U9没有通用的"账套快照回滚"接口。可选实现方式：
    A. 数据库快照/还原（SQL Server 还原到已知备份）—— 最干净，但需 DBA 介入。
    B. 反向清理：删除上一轮评估创建的、带特定前缀/标记的单据。
    C. 用例自身幂等：每个用例用唯一编号/标记，互不干扰。

  本骨架默认采用 (B)+(C)：reset() 调用各夹具的 cleanup，按标记清理评估产生的单据；
  真正的"还原到初始状态"（方案 A）留作 TODO，由部署方按测试账套实际情况实现。

任何 reset/cleanup 逻辑执行前都应已通过 config.assert_safe_for_writes（防止误连生产）。
"""
from __future__ import annotations

from typing import Any

from ..fixtures import registry
from .u9_client import U9StateClient


class Sandbox:
    def __init__(self, config: dict[str, Any], dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self._client = U9StateClient()

    def state_client(self) -> U9StateClient:
        """返回查最终账套状态的只读客户端。"""
        return self._client

    async def reset(self) -> None:
        """把测试账套重置到已知初始状态。

        TODO（方案 A）：接入数据库快照还原，实现真正的"回到初始状态"。
        目前实现：调用所有已注册夹具的 cleanup，按标记清理上一轮评估产生的单据。
        """
        if self.dry_run:
            return
        await registry.cleanup_all(self._client, self.config)

    async def apply_fixtures(self, fixture_names: list[str] | None) -> dict[str, Any]:
        """准备用例声明的基础数据，返回 {fixture_name: 准备结果}。"""
        prepared: dict[str, Any] = {}
        if self.dry_run or not fixture_names:
            return prepared
        for name in fixture_names:
            prepared[name] = await registry.prepare(name, self._client, self.config)
        return prepared
