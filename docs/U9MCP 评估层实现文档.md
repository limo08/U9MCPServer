# U9MCP 评估层实现文档

> 本文档交给 Claude Code 实现。目标是为 U9MCP（连接 LLM 与用友U9的 MCP server）建立一套评估层，把 agent 的行为从"凭感觉"变成"看数字"，并支持每次改动后的回归对比。

## 0. 实现前需要确认的事项（请先和我对齐）

这些影响实现，开始前请确认或在代码里留出明确的配置位：

1. **技术栈**：本文档假设 U9MCP 用 Python + MCPServer（mcp 2.x），评估层也用 Python。若实际不同请调整。
2. **当前工具清单**：U9MCP 目前暴露了哪些工具（名称、入参、覆盖的单据类型）？评估用例需要按这些工具来设计。
3. **测试账套**：是否有独立的用友测试账套（绝不能用生产账套跑评估）？能否在每次评估前重置到已知初始状态？
4. **用友接入方式**：通过用友 Open API 读写？凭证如何配置（appId / appSecret / 账套 ID 等）？查询单据状态用哪个接口？
5. **agent 调用入口**：如何用代码触发 agent 跑完一个自然语言任务，并拿到它的完整调用轨迹（调了哪些工具、参数、顺序）？

未确认的部分，先按下面的设计搭骨架，把不确定的地方做成 TODO 和配置项。

## 1. 设计原则

- **优先程序化断言**：用友单据的对错大多客观可验证，做完任务后查 API 比对账套最终状态。能断言就断言，断言不了才用规则检查，最后才考虑 LLM 打分。
- **三层评估**：工具层（单个工具调用对不对）、轨迹层（agent 决策对不对）、结果层（最终账套状态对不对）。三层各管一类问题，都要有。
- **可重置的测试环境**：每个用例跑之前把测试账套重置到已知初始状态，避免用例之间互相污染。
- **一键可跑、可回归**：评估能用一条命令跑完，输出指标，并和上一次基线对比。
- **MVP 优先，迭代扩充**：先做出能吐出"成功率"数字的最小版本，再逐步加轨迹评估、回归、judge、扩用例。

## 2. 整体架构

模块划分：

- **测试集（cases）**：一组带标准答案的 JSON 用例。
- **环境管理（sandbox）**：重置测试账套、准备/清理用例所需的基础数据。
- **执行器（runner）**：逐条加载用例 → 重置环境 → 准备数据 → 调 agent → 抓取轨迹 → 查最终状态 → 调判分器 → 记录结果。
- **判分器（graders）**：ResultGrader（结果层，查 API 断言）、TrajectoryGrader（轨迹层）、RuleGrader（安全规则）。
- **指标统计（metrics）**：汇总成功率等指标。
- **报告与回归（report）**：输出本次结果，和历史基线对比，标出回归。

## 3. 建议目录结构

```
evals/
  config.yaml              # 测试账套连接、阈值、模型等配置
  cases/                   # JSON 用例，按单据类型分目录
    purchase_order/
    sales_order/
    query/
  fixtures/                # 用例所需基础数据的准备/清理脚本
  sandbox/
    reset.py               # 重置测试账套到初始状态
    u9_client.py      # 封装查询账套状态的 API 调用
  graders/
    base.py                # Grader 接口与 GradeResult 定义
    result_grader.py
    trajectory_grader.py
    rule_grader.py
  runner.py                # 主执行器
  metrics.py
  report.py
  baselines/               # 历史评估结果，用于回归对比
  run_eval.py              # 入口：python run_eval.py
```

## 4. 测试用例 Schema

每个用例是一个 JSON 文件，字段如下：

```json
{
  "id": "po_create_basic_001",
  "category": "采购订单",
  "tags": ["高频", "创建"],
  "input": "给供应商A创建一张采购订单，物料螺丝，数量1000",
  "setup": {
    "description": "确保供应商A、物料螺丝存在；清理同条件已有单据",
    "fixtures": ["supplier_A", "material_luosi"]
  },
  "expected_result": {
    "assertions": [
      {
        "desc": "采购订单存在且字段正确",
        "doc_type": "采购订单",
        "filter": { "供应商": "A", "物料": "螺丝" },
        "field_checks": { "数量": 1000, "单据状态": "已保存" }
      }
    ]
  },
  "expected_tools": ["query_supplier", "create_purchase_order"],
  "max_steps": 5,
  "safety": {
    "require_confirm_over_amount": null
  }
}
```

字段说明：

- `id`：唯一标识，命名建议 `<单据>_<动作>_<场景>_<序号>`。
- `category` / `tags`：用于分类统计和筛选（如只跑"高频"用例）。
- `input`：用户的自然语言指令，原样喂给 agent。
- `setup`：跑之前要准备的账套状态，`fixtures` 引用 `fixtures/` 下的数据准备脚本。
- `expected_result.assertions`：结果层标准答案。每条断言描述任务做完后账套应满足的状态，由 ResultGrader 查 API 校验。
- `expected_tools`：轨迹层参考——理想情况下应调用的工具集合。
- `max_steps`：步数上限，超过判为低效。
- `safety`：安全规则参数，如金额超阈值必须停下等确认。

## 5. 种子用例（先实现这几条）

按"高频 + 错了后果重"优先。下面是起步用的几类，实际数值按测试账套填：

1. **查询类（最安全，先跑通流程）**：查某供应商最近一个月的采购订单，断言返回数量和单号正确。
2. **采购订单创建（高频）**：建单后断言供应商、物料、数量、状态正确。
3. **销售订单下推（易错、涉及反写）**：下推成发货通知单，断言下游单据正确生成，且源单下推数量被正确反写。
4. **边界/错误场景**：对一张已下推的单据再次下推，断言 agent 正确识别并拒绝，而不是重复操作。
5. **安全场景**：超过金额阈值的操作，断言 agent 停下等人工确认，未擅自提交。

每类先 2-3 条，合计 10-15 条即可启动。

## 6. 判分器接口

```python
# graders/base.py
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class GradeResult:
    layer: str               # "result" | "trajectory" | "rule"
    passed: bool
    score: float             # 0.0 - 1.0
    failures: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

class Grader(Protocol):
    def grade(self, case: dict, trajectory: list, final_state_client) -> GradeResult:
        ...
```

三个判分器：

- **ResultGrader（结果层，最重要）**：用 `final_state_client`（封装用友查询 API）逐条执行 `expected_result.assertions`，比对账套实际状态。这是核心，先把它做扎实。
- **TrajectoryGrader（轨迹层）**：检查 agent 实际调用的工具是否覆盖 `expected_tools`、有无多余/错误调用、步数是否超过 `max_steps`。
- **RuleGrader（安全规则）**：检查是否触发了硬性约束，如金额超阈值未确认、调用了不该调的反审核类工具。

判分优先级：结果层断言为主，轨迹层和规则层为辅。结果对但轨迹差 → 记为"通过但低效"；结果错 → 失败，并由轨迹定位错在哪一步。

## 7. 执行器流程

```python
# runner.py 主流程（伪代码）
def run_case(case, agent, sandbox, graders):
    sandbox.reset()                      # 重置测试账套
    sandbox.apply_fixtures(case["setup"]["fixtures"])

    trajectory = agent.run(case["input"]) # 返回完整调用轨迹

    state_client = sandbox.state_client() # 查最终账套状态的客户端
    results = [g.grade(case, trajectory, state_client) for g in graders]

    return {
        "id": case["id"],
        "category": case["category"],
        "passed": all(r.passed for r in results if r.layer == "result"),
        "grades": results,
        "steps": len(trajectory),
    }
```

入口 `run_eval.py` 加载全部用例 → 逐条 `run_case` → 汇总 `metrics` → 写 `report`。

## 8. 指标

汇总并输出：

- **端到端成功率**：结果层通过的用例占比（核心指标）。
- **工具选择准确率**：轨迹层 `expected_tools` 命中比例。
- **平均步数 / 步数超限率**：效率。
- **安全规则违反数**：RuleGrader 失败计数（应为 0）。
- **失败模式分布**：按 `category` 统计失败集中在哪类任务。
- **（可选）token 成本 / 单任务耗时**。

## 9. 回归对比

每次跑完把结果写入 `baselines/`（带时间戳），并自动和上一次基线对比，标出：哪些用例从通过变失败（回归，重点报警）、哪些从失败变通过（改进）、整体成功率变化。这样每次改 prompt / 工具描述 / 换模型，都能看到是变好还是变坏。

## 10. 实施阶段

**Phase 0 — MVP（先做这个）**
- 实现 `u9_client`（查询账套状态）、`sandbox.reset`、ResultGrader、最简 runner。
- 写 5-10 条结果层用例（以查询和创建类为主）。
- 跑完输出一个端到端成功率数字。
- 目标：能用一条命令跑出"现在多少分"。

**Phase 1 — 加轨迹评估**
- 让 agent 调用能返回完整轨迹，实现 TrajectoryGrader 和 RuleGrader。
- 加入下推、反写、安全阈值类用例。

**Phase 2 — 回归自动化**
- 实现 metrics、report、baseline 对比，接入一键运行。

**Phase 3 — 扩充与回流**
- 用例扩到覆盖主要单据类型。
- 对无法程序化判定的部分按需引入 LLM-as-judge（谨慎，要校准）。
- 建立"线上失败 case → 人工纠正 → 补进测试集"的回流流程。

## 11. 注意事项

- 评估只在独立测试账套运行，任何脚本不得指向生产环境。
- 用例之间必须靠 `sandbox.reset` 隔离，否则结果不可复现。
- 测试集是"考题"不是"训练数据"，不喂给模型学习，只用于打分。
- 不要一开始追求完整框架，先把 Phase 0 跑通。