"""agent 调用入口抽象。

评估器需要"用代码触发 agent 跑完一个自然语言任务，并拿到完整调用轨迹"。
不同部署的 agent 接入方式不同，这里用 `AgentRunner` 协议把它抽象掉，
`build_agent(config)` 按配置选择具体实现。

当前提供：
  - MockAgent  —— 离线回放用例内置 mock_trajectory，用于自检整条评估管线（无需真实 agent / 用友）
  - HttpAgent  —— 调外部 agent HTTP 服务（骨架 + TODO，按你的实际服务接线）
"""
from __future__ import annotations

from typing import Any

from .base import AgentRunner, ToolCall, Trajectory
from .mock_agent import MockAgent

__all__ = ["AgentRunner", "ToolCall", "Trajectory", "MockAgent", "build_agent"]


def build_agent(config: dict[str, Any]) -> AgentRunner:
    """按配置构造 agent runner。"""
    agent_cfg = config.get("agent", {})
    kind = (agent_cfg.get("type") or "mock").lower()

    if kind == "mock":
        return MockAgent()
    if kind == "http":
        from .http_agent import HttpAgent

        return HttpAgent(
            endpoint=agent_cfg.get("endpoint", ""),
            timeout_seconds=agent_cfg.get("timeout_seconds", 120),
        )
    raise ValueError(
        f"未知 agent.type={kind!r}。可选: mock | http | custom（在 build_agent 里接线）。"
    )
