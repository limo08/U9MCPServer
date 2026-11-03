"""U9MCP 评估层（evals）。

把 agent 在用友U9上的行为从"凭感觉"变成"看数字"，并支持每次改动后的回归对比。

三层评估：
  - 结果层 (ResultGrader)    —— 任务做完后查 API 比对账套最终状态（最重要）
  - 轨迹层 (TrajectoryGrader) —— agent 的工具选择与步数是否合理
  - 规则层 (RuleGrader)       —— 是否触发安全硬约束（金额阈值、危险工具）

入口：`python -m evals.run_eval`（或 `python evals/run_eval.py`）。

设计与实现细节见 docs/「U9MCP 评估层实现文档.md」与 evals/README.md。
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
