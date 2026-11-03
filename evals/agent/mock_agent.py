"""MockAgent —— 离线回放用例内置的 mock_trajectory。

用途：在没有真实 agent / 用友环境时，自检整条评估管线（runner → graders →
metrics → report）是否串得通。用例可在 `mock_trajectory` 字段里预置一段
工具调用轨迹与最终回复；若用例没提供，则返回空轨迹。

注意：mock 轨迹是给"管线自检"用的，不代表真实 agent 行为；真实评估请把
config.yaml 的 agent.type 换成 http / custom 并接上真正的 agent。
"""
from __future__ import annotations

from typing import Any

from .base import AgentRunner, ToolCall, Trajectory


class MockAgent(AgentRunner):
    async def run(self, task_input: str, case: dict[str, Any] | None = None) -> Trajectory:
        case = case or {}
        mock = case.get("mock_trajectory") or {}
        calls = [ToolCall.from_dict(c) for c in mock.get("tool_calls", [])]
        return Trajectory(
            input=task_input,
            tool_calls=calls,
            final_text=mock.get("final_text", ""),
            error=mock.get("error"),
        )
