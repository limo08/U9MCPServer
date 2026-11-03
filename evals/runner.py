"""执行器：逐条加载用例 → 重置环境 → 准备数据 → 调 agent → 抓取轨迹 →
查最终状态 → 调判分器 → 记录结果。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .agent.base import AgentRunner, Trajectory
from .graders.base import Grader, GradeResult
from .sandbox.u9_client import MockStateClient
from .sandbox.reset import Sandbox

CASES_DIR = Path(__file__).parent / "cases"


def load_cases(cases_dir: Path | str | None = None, tags: list[str] | None = None,
               categories: list[str] | None = None) -> list[dict[str, Any]]:
    """递归加载 cases 目录下所有 .json 用例，可按 tags / category 过滤。"""
    root = Path(cases_dir) if cases_dir else CASES_DIR
    cases: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            case = json.load(f)
        case.setdefault("_path", str(path))
        if tags and not (set(tags) & set(case.get("tags", []))):
            continue
        if categories and case.get("category") not in categories:
            continue
        cases.append(case)
    return cases


def _state_client(case: dict[str, Any], sandbox: Sandbox, dry_run: bool):
    if dry_run:
        return MockStateClient(case.get("mock_state", {}))
    return sandbox.state_client()


async def run_case(
    case: dict[str, Any],
    agent: AgentRunner,
    sandbox: Sandbox,
    graders: list[Grader],
    dry_run: bool = False,
) -> dict[str, Any]:
    """跑单条用例，返回结构化结果。"""
    started = time.perf_counter()
    setup = case.get("setup") or {}
    error: str | None = None
    trajectory = Trajectory(input=case.get("input", ""))
    grade_results: list[GradeResult] = []

    try:
        await sandbox.reset()
        await sandbox.apply_fixtures(setup.get("fixtures"))

        trajectory = await agent.run(case.get("input", ""), case)

        state_client = _state_client(case, sandbox, dry_run)
        for g in graders:
            grade_results.append(await g.grade(case, trajectory, state_client))
    except Exception as e:  # 用例级别异常不应中断整批
        error = f"{type(e).__name__}: {e}"

    # 结果层是否全过 = 这条用例端到端是否成功
    result_grades = [g for g in grade_results if g.layer == "result"]
    passed = bool(result_grades) and all(g.passed for g in result_grades) and error is None

    by_layer = {g.layer: g.to_dict() for g in grade_results}
    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "tags": case.get("tags", []),
        "passed": passed,
        "error": error,
        "steps": trajectory.steps,
        "tool_calls": trajectory.tool_names(),
        "grades": by_layer,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }


async def run_all(
    cases: list[dict[str, Any]],
    agent: AgentRunner,
    sandbox: Sandbox,
    graders: list[Grader],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        results.append(await run_case(case, agent, sandbox, graders, dry_run))
    return results
