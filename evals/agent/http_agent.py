"""HttpAgent —— 通过 HTTP 调用外部 agent 服务（骨架 + TODO）。

约定（按你的实际 agent 服务调整）：
  POST {endpoint}
  body: {"input": "<自然语言任务>"}
  resp: {
    "tool_calls": [{"name": ..., "arguments": {...}, "result": ..., "error": null}],
    "final_text": "...",
    "error": null
  }

TODO:
  - 对齐你的 agent 服务的真实请求/响应格式（鉴权、字段名、轨迹结构）。
  - 如果 agent 不直接吐轨迹，需要在服务侧或网关侧把 MCP 工具调用记录下来回传。
"""
from __future__ import annotations

from typing import Any

import httpx

from .base import AgentRunner, ToolCall, Trajectory


class HttpAgent(AgentRunner):
    def __init__(self, endpoint: str, timeout_seconds: float = 120):
        if not endpoint:
            raise ValueError("agent.type=http 需要在 config.yaml 配置 agent.endpoint")
        self.endpoint = endpoint
        self.timeout = timeout_seconds

    async def run(self, task_input: str, case: dict[str, Any] | None = None) -> Trajectory:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.endpoint, json={"input": task_input})
            resp.raise_for_status()
            data = resp.json()

        calls = [ToolCall.from_dict(c) for c in data.get("tool_calls", [])]
        return Trajectory(
            input=task_input,
            tool_calls=calls,
            final_text=data.get("final_text", ""),
            error=data.get("error"),
        )
