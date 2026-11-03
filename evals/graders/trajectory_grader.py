"""TrajectoryGrader —— 轨迹层判分。

检查 agent 实际调用的工具是否覆盖 expected_tools、有无明显多余调用、步数是否超 max_steps。
轨迹层为辅：它不决定"任务成没成"（那是结果层的事），而是回答"决策路径好不好、效率高不高"。
"""
from __future__ import annotations

from typing import Any

from ..agent.base import Trajectory
from ..sandbox.u9_client import U9StateClient
from .base import GradeResult


class TrajectoryGrader:
    layer = "trajectory"

    def __init__(self, config: dict[str, Any]):
        self.default_max_steps = config.get("thresholds", {}).get("default_max_steps", 8)

    async def grade(
        self, case: dict[str, Any], trajectory: Trajectory, final_state_client: U9StateClient
    ) -> GradeResult:
        expected = list(case.get("expected_tools", []))
        actual = trajectory.tool_names()
        actual_set = set(actual)

        failures: list[str] = []

        # 1. expected_tools 覆盖率
        if expected:
            hit = [t for t in expected if t in actual_set]
            missing = [t for t in expected if t not in actual_set]
            coverage = len(hit) / len(expected)
            if missing:
                failures.append(f"缺少预期工具: {missing}")
        else:
            hit, missing, coverage = [], [], 1.0

        # 2. 多余工具（调了 expected 之外的）——仅作提示，不直接判失败
        extra = [t for t in actual if expected and t not in set(expected)]

        # 3. 步数上限
        max_steps = case.get("max_steps", self.default_max_steps)
        over_steps = trajectory.steps > max_steps
        if over_steps:
            failures.append(f"步数超限: {trajectory.steps} > max_steps={max_steps}")

        # 4. 失败的工具调用
        failed_calls = [tc.name for tc in trajectory.tool_calls if not tc.ok]
        if failed_calls:
            failures.append(f"工具调用失败: {failed_calls}")

        passed = coverage >= 1.0 and not over_steps and not failed_calls
        return GradeResult(
            layer=self.layer,
            passed=passed,
            score=coverage,
            failures=failures,
            details={
                "expected_tools": expected,
                "actual_tools": actual,
                "coverage": coverage,
                "missing": missing,
                "extra": extra,
                "steps": trajectory.steps,
                "max_steps": max_steps,
                "over_steps": over_steps,
            },
        )
