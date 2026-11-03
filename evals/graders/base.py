"""判分器接口与 GradeResult 定义。

与设计文档的一处实现性调整：文档把 Grader.grade 写成同步方法，但结果层判分需要
查询用友 API（异步），因此这里统一把 grade 定义为 **async**，三个判分器签名一致，
runner 用 `await g.grade(...)` 调用。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from ..agent.base import Trajectory
from ..sandbox.u9_client import U9StateClient


@dataclass
class GradeResult:
    layer: str                                   # "result" | "trajectory" | "rule"
    passed: bool
    score: float                                 # 0.0 - 1.0
    failures: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Grader(Protocol):
    layer: str

    async def grade(
        self,
        case: dict[str, Any],
        trajectory: Trajectory,
        final_state_client: U9StateClient,
    ) -> GradeResult:
        ...
