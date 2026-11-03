"""报告与回归对比。

  - render(...) 把指标 + 逐条结果渲染成 text / markdown / json
  - save_baseline(...) 把本次结果带时间戳写入 baselines/
  - compare_to_previous(...) 和上一次基线对比，标出回归（通过→失败）与改进（失败→通过）
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


# ── 基线读写 ──────────────────────────────────────────────────
def save_baseline(payload: dict[str, Any], baselines_dir: str | Path) -> Path:
    d = Path(baselines_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = d / f"baseline-{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def _list_baselines(baselines_dir: str | Path) -> list[Path]:
    d = Path(baselines_dir)
    if not d.exists():
        return []
    return sorted(d.glob("baseline-*.json"))


def load_previous_baseline(baselines_dir: str | Path) -> dict[str, Any] | None:
    files = _list_baselines(baselines_dir)
    if not files:
        return None
    with open(files[-1], "r", encoding="utf-8") as f:
        return json.load(f)


def compare_to_previous(
    current: dict[str, Any], previous: dict[str, Any] | None
) -> dict[str, Any]:
    """对比当前结果与上一次基线。"""
    if not previous:
        return {"has_previous": False}

    cur = {r["id"]: r["passed"] for r in current["results"]}
    prev = {r["id"]: r["passed"] for r in previous.get("results", [])}

    regressions = sorted(i for i in cur if i in prev and prev[i] and not cur[i])
    improvements = sorted(i for i in cur if i in prev and not prev[i] and cur[i])
    new_cases = sorted(i for i in cur if i not in prev)

    return {
        "has_previous": True,
        "previous_pass_rate": previous["metrics"].get("pass_rate"),
        "current_pass_rate": current["metrics"].get("pass_rate"),
        "pass_rate_delta": round(
            current["metrics"].get("pass_rate", 0) - previous["metrics"].get("pass_rate", 0), 4
        ),
        "regressions": regressions,
        "improvements": improvements,
        "new_cases": new_cases,
    }


# ── 渲染 ──────────────────────────────────────────────────────
def render(payload: dict[str, Any], diff: dict[str, Any], fmt: str = "text") -> str:
    if fmt == "json":
        return json.dumps({"report": payload, "diff": diff}, ensure_ascii=False, indent=2)
    if fmt == "markdown":
        return _render_markdown(payload, diff)
    return _render_text(payload, diff)


def _render_text(payload: dict[str, Any], diff: dict[str, Any]) -> str:
    m = payload["metrics"]
    lines = [
        "═" * 56,
        "  U9MCP 评估报告",
        "═" * 56,
        f"  端到端成功率 : {m['pass_rate']:.1%}  ({m['passed']}/{m['total']})",
    ]
    if m.get("tool_accuracy") is not None:
        lines.append(f"  工具选择准确率: {m['tool_accuracy']:.1%}")
    lines += [
        f"  平均步数      : {m['avg_steps']}  (超限 {m['over_steps_count']} 条)",
        f"  安全规则违反  : {m['safety_violations']}  (应为 0)",
        f"  平均耗时      : {m['avg_duration_ms']} ms",
        "-" * 56,
        "  失败模式分布（按类别）:",
    ]
    for cat, tot in m["total_by_category"].items():
        fail = m["fail_by_category"].get(cat, 0)
        lines.append(f"    {cat}: {tot - fail}/{tot} 通过")

    lines += ["-" * 56, "  逐条结果:"]
    for r in payload["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"    [{mark}] {r['id']}  ({r['category']}, {r['steps']} 步)")
        if not r["passed"]:
            for layer, g in r["grades"].items():
                for fmsg in g.get("failures", []):
                    lines.append(f"           · [{layer}] {fmsg}")
            if r.get("error"):
                lines.append(f"           · [error] {r['error']}")

    lines += ["-" * 56, "  回归对比:"]
    if not diff.get("has_previous"):
        lines.append("    （无历史基线，本次将作为首个基线）")
    else:
        lines.append(
            f"    成功率: {diff['previous_pass_rate']:.1%} → {diff['current_pass_rate']:.1%} "
            f"(Δ {diff['pass_rate_delta']:+.1%})"
        )
        if diff["regressions"]:
            lines.append(f"    ⚠ 回归（通过→失败）: {diff['regressions']}")
        if diff["improvements"]:
            lines.append(f"    ✔ 改进（失败→通过）: {diff['improvements']}")
        if diff["new_cases"]:
            lines.append(f"    + 新增用例: {diff['new_cases']}")
        if not (diff["regressions"] or diff["improvements"]):
            lines.append("    无变化")
    lines.append("═" * 56)
    return "\n".join(lines)


def _render_markdown(payload: dict[str, Any], diff: dict[str, Any]) -> str:
    m = payload["metrics"]
    out = ["# U9MCP 评估报告", "", "## 指标", "",
           "| 指标 | 值 |", "| --- | --- |",
           f"| 端到端成功率 | {m['pass_rate']:.1%} ({m['passed']}/{m['total']}) |"]
    if m.get("tool_accuracy") is not None:
        out.append(f"| 工具选择准确率 | {m['tool_accuracy']:.1%} |")
    out += [
        f"| 平均步数 | {m['avg_steps']} (超限 {m['over_steps_count']}) |",
        f"| 安全规则违反 | {m['safety_violations']} |",
        f"| 平均耗时 | {m['avg_duration_ms']} ms |",
        "", "## 逐条结果", "", "| 用例 | 类别 | 步数 | 结果 |", "| --- | --- | --- | --- |",
    ]
    for r in payload["results"]:
        out.append(f"| {r['id']} | {r['category']} | {r['steps']} | {'✅' if r['passed'] else '❌'} |")
    out += ["", "## 回归对比", ""]
    if not diff.get("has_previous"):
        out.append("_无历史基线，本次将作为首个基线。_")
    else:
        out.append(
            f"成功率 {diff['previous_pass_rate']:.1%} → {diff['current_pass_rate']:.1%} "
            f"(Δ {diff['pass_rate_delta']:+.1%})"
        )
        if diff["regressions"]:
            out.append(f"- ⚠ **回归**: {diff['regressions']}")
        if diff["improvements"]:
            out.append(f"- ✔ 改进: {diff['improvements']}")
        if diff["new_cases"]:
            out.append(f"- ➕ 新增: {diff['new_cases']}")
    return "\n".join(out)
