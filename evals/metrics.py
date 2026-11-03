"""指标统计：把逐条结果汇总成评估指标。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {"total": 0, "pass_rate": 0.0}

    passed = sum(1 for r in results if r["passed"])

    # 工具选择准确率（轨迹层 coverage 平均）
    coverages = [
        r["grades"]["trajectory"]["details"].get("coverage", 0.0)
        for r in results
        if "trajectory" in r["grades"]
    ]
    tool_accuracy = sum(coverages) / len(coverages) if coverages else None

    # 步数
    steps = [r["steps"] for r in results]
    avg_steps = sum(steps) / total
    over_steps = sum(
        1 for r in results
        if r["grades"].get("trajectory", {}).get("details", {}).get("over_steps")
    )

    # 安全规则违反数
    safety_violations = sum(
        r["grades"].get("rule", {}).get("details", {}).get("violations", 0)
        for r in results
    )

    # 失败模式分布（按 category）
    fail_by_category: dict[str, int] = defaultdict(int)
    total_by_category: dict[str, int] = defaultdict(int)
    for r in results:
        cat = r.get("category") or "未分类"
        total_by_category[cat] += 1
        if not r["passed"]:
            fail_by_category[cat] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4),
        "tool_accuracy": round(tool_accuracy, 4) if tool_accuracy is not None else None,
        "avg_steps": round(avg_steps, 2),
        "over_steps_count": over_steps,
        "safety_violations": safety_violations,
        "fail_by_category": dict(fail_by_category),
        "total_by_category": dict(total_by_category),
        "avg_duration_ms": round(sum(r["duration_ms"] for r in results) / total, 1),
    }
