# U9MCP 评估层（evals）

把 agent 在用友U9上的行为从"凭感觉"变成"看数字"，并支持每次改动（prompt / 工具描述 / 换模型）后的回归对比。

设计来源：`docs/U9MCP 评估层实现文档.md`。

## 快速开始

```bash
# 离线自检：用 mock agent + mock 账套状态跑通整条管线（无需用友、不写任何数据）
python -m evals.run_eval --dry-run

# 评估子集
python -m evals.run_eval --dry-run --tags 高频
python -m evals.run_eval --dry-run --category 采购订单

# 输出 markdown 报告到文件
python -m evals.run_eval --dry-run --format markdown -o report.md

# 真实评估（连测试账套，需先完成下面"接入真实环境"）
python -m evals.run_eval
```

## 三层评估

| 层 | 判分器 | 管什么 |
|----|--------|--------|
| 结果层（最重要）| `ResultGrader` | 任务做完后查 API，比对账套最终状态是否符合 `expected_result.assertions` |
| 轨迹层 | `TrajectoryGrader` | 工具选择是否覆盖 `expected_tools`、步数是否超 `max_steps`、有无失败调用 |
| 规则层 | `RuleGrader` | 安全硬约束：大额未确认、危险工具（反审核/删除）未声明即调用 |

判定：**结果层全过 = 这条用例端到端成功**。结果对但轨迹差 → "通过但低效"；结果错 → 失败，轨迹用于定位错在哪步。

## 目录结构

```
evals/
  config.yaml          连接安全闸、阈值、中文↔用友字段映射
  config.py            配置加载 + assert_safe_for_writes 安全闸
  cases/               JSON 用例，按单据类型分目录
  fixtures/registry.py 夹具（prepare/cleanup），目前多为骨架/TODO
  sandbox/
    u9_client.py  U9StateClient（查真实账套）+ MockStateClient（离线）
    reset.py           Sandbox：reset / apply_fixtures
  agent/               AgentRunner 协议 + MockAgent / HttpAgent
  graders/             base + result/trajectory/rule 三个判分器
  runner.py            主执行器（load_cases / run_case / run_all）
  metrics.py           指标汇总
  report.py            报告渲染 + 基线读写 + 回归对比
  baselines/           历史结果（带时间戳），回归对比用
  run_eval.py          入口（python -m evals.run_eval）
```

## 用例 Schema

见 `docs/U9MCP 评估层实现文档.md` 第 4 节。要点：

- `expected_result.assertions` 每条断言支持两种写法，**ResultGrader 优先用 raw**：
  - raw：直接给 `form_id` + `filter_string`（用友语法）+ `field_checks`（用友字段 key）+ `exact_count`/`min_count`
  - semantic：给中文 `doc_type` + `filter`{中文字段:值} + `field_checks`{中文字段:值}，靠 `config.yaml` 的 `doc_type_map`/`field_map`/`status_map` 翻译
- 每条用例可带 `mock_trajectory` + `mock_state`，供 `--dry-run` 离线自检整条管线。

## 安全闸（重要）

评估**只能在独立测试账套**运行。任何写操作/夹具类用例在非 `--dry-run` 下运行前，
`config.assert_safe_for_writes` 会强制校验：

1. `config.yaml` 的 `test_account.confirmed` 必须为 `true`；
2. `U9_API_SERVER_URL` 不含疑似生产标记（prod/production/正式…）；
3. 若配置了 `allowed_ent_codes`，当前 `U9_API_ENT_CODE`（或 `entCode/orgCode`）
   必须在白名单内。

任一不满足直接拒绝运行（退出码 2）。

## 接入真实环境（待办 / 按部署补全）

1. **测试账套**：设好 `U9_API_*` 环境变量指向测试账套，并把 `config.yaml`
   `test_account.confirmed` 设为 `true`、填上 `allowed_ent_codes`。
2. **重置**：`sandbox/reset.py` 目前用"按标记清理 + 用例幂等"。若需"还原到初始状态"，
   接入数据库快照还原（见文件内 TODO）。
3. **夹具**：`fixtures/registry.py` 的 prepare 目前只"确认基础资料存在"。需要自动创建的，
   按测试账套补全 Save 逻辑。
4. **agent 入口**：把 `config.yaml` 的 `agent.type` 从 `mock` 换成 `http`（或 `custom`），
   在 `agent/http_agent.py` 对齐你的 agent 服务请求/响应格式，使其能返回完整工具调用轨迹。
5. **字段映射**：按测试账套实际字段，补全 `config.yaml` 的 `doc_type_map`/`field_map`/`status_map`，
   或直接在用例里用 raw 断言（更可靠）。

## 回归对比

每次（非 dry-run）跑完把结果写入 `baselines/baseline-<时间戳>.json`，并自动和上一份基线对比，
标出回归（通过→失败，报警并以非零码退出）、改进（失败→通过）、成功率变化。

## 实施阶段对照

- **Phase 0（MVP）✅**：u9_client / sandbox.reset / ResultGrader / runner，
  10+ 条结果层用例，一条命令输出成功率。
- **Phase 1 ✅**：TrajectoryGrader + RuleGrader，含下推/反写/安全阈值用例。
- **Phase 2 ✅**：metrics / report / baseline 回归对比，一键运行。
- **Phase 3（按需）**：扩充用例覆盖更多单据类型；对无法程序化判定的部分谨慎引入 LLM-as-judge；
  建立"线上失败 case → 人工纠正 → 补进测试集"的回流。
