# 运维 / 诊断脚本

本目录只保留**非测试**类脚本：运维工具、失败追溯、报表生成，以及一次性实机操作脚本。
测试代码统一放在 `tests/`：

- 自动化测试：`tests/`
- 需真实环境的手工测试：`tests/manual/`（不被 pytest 自动收集）

| 脚本 | 类型 | 说明 |
| --- | --- | --- |
| `check_harness.py` | 诊断工具 | 检查操作链 trace 是否满足 Harness 约束，可用于 CI |
| `extract_failures.py` | 诊断工具 | 扫描 `examples/failure_log.jsonl`，提取失败模式 |
| `extract_remember.py` | 运维工具 | 扫描代码中的 `💡 REMEMBER` 注释并汇总到记忆文件 |
| `failure_log.py` | 运行时模块 | 被 `src/u9_mcp/` 导入，记录操作失败日志，**不要移动/删除** |
| `usage_report.py` | 报表工具 | 根据使用日志生成 JSON / Markdown 报告 |
| `create_quotation.py` | 一次性实机脚本 | 创建销售报价单并提交审核，⚠️ 会写入真实 ERP |
| `submit_audit.py` | 一次性实机脚本 | 提交并审核指定报价单，⚠️ 会写入真实 ERP |
