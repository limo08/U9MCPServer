"""agent 轨迹数据模型与 AgentRunner 协议。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolCall:
    """agent 一次工具调用的记录。"""
    name: str                              # 工具名，如 u9_save_bill
    arguments: dict[str, Any] = field(default_factory=dict)
    result: Any = None                     # 工具返回（通常是 JSON 字符串/字典）
    error: str | None = None               # 调用失败时的错误信息
    ok: bool = True                        # 该步是否成功

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolCall":
        return cls(
            name=d.get("name") or d.get("tool") or "",
            arguments=d.get("arguments") or d.get("args") or {},
            result=d.get("result"),
            error=d.get("error"),
            ok=d.get("ok", d.get("error") is None),
        )


@dataclass
class Trajectory:
    """agent 跑完一个任务的完整调用轨迹。"""
    input: str                             # 喂给 agent 的自然语言指令
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_text: str = ""                   # agent 给用户的最终自然语言回复
    error: str | None = None               # 整体执行失败时的信息

    @property
    def steps(self) -> int:
        return len(self.tool_calls)

    def tool_names(self) -> list[str]:
        return [tc.name for tc in self.tool_calls]

    def __len__(self) -> int:  # 让 runner 里的 len(trajectory) 可用
        return len(self.tool_calls)


@runtime_checkable
class AgentRunner(Protocol):
    """触发 agent 跑完一个自然语言任务并返回轨迹。"""

    async def run(self, task_input: str, case: dict[str, Any] | None = None) -> Trajectory:
        """执行任务。

        Args:
            task_input: 用户自然语言指令（即用例的 input 字段）。
            case: 完整用例 dict，供需要用例上下文的实现（如 MockAgent）使用。
        """
        ...
