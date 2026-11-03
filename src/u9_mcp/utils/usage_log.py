"""工具调用日志与使用统计。"""

import json
import os
import time
from datetime import datetime
from typing import Any, Callable
from collections import defaultdict

from ..config.settings import _USAGE_LOG_FILE

_ERROR_STATS: dict[str, int] = defaultdict(int)  # 错误类型统计
_TOOL_STATS: dict[str, dict] = defaultdict(lambda: {
    "total": 0, "success": 0, "failed": 0, "total_ms": 0
})

def _get_log_dir() -> str:
    """获取日志目录，优先使用环境变量指定的目录"""
    log_dir = os.environ.get("MCP_USAGE_LOG_DIR", ".")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def _sanitize_params(params: dict, max_len: int = 200) -> dict:
    """清理参数，移除敏感信息和过长的值"""
    sensitive_keys = {"password", "secret", "app_sec", "token", "cookie", "session"}
    sanitized = {}
    for k, v in params.items():
        k_lower = k.lower()
        if k_lower in sensitive_keys:
            sanitized[k] = "***"
        elif isinstance(v, str) and len(v) > max_len:
            sanitized[k] = v[:max_len] + "..."
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_params(v, max_len)
        elif isinstance(v, list) and len(v) > 10:
            sanitized[k] = v[:10] + [f"...({len(v)-10} more)"]
        else:
            sanitized[k] = v
    return sanitized

def log_tool_usage(tool_name: str, params: dict, duration_ms: float,
                   success: bool, result_preview: str = "", error_type: str = ""):
    """记录单次工具调用"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "tool": tool_name,
        "params_keys": list(params.keys()),
        "duration_ms": round(duration_ms, 2),
        "success": success,
        "error_type": error_type,
        "result_preview": result_preview[:500] if result_preview else "",
    }
    log_path = os.path.join(_get_log_dir(), _USAGE_LOG_FILE)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 日志记录失败不影响主流程

    # 统计聚合
    _TOOL_STATS[tool_name]["total"] += 1
    _TOOL_STATS[tool_name]["total_ms"] += duration_ms
    if success:
        _TOOL_STATS[tool_name]["success"] += 1
    else:
        _TOOL_STATS[tool_name]["failed"] += 1
        if error_type:
            _ERROR_STATS[error_type] += 1

def get_usage_stats() -> dict:
    """获取使用统计摘要"""
    return {
        "tool_stats": dict(_TOOL_STATS),
        "error_stats": dict(_ERROR_STATS),
        "log_file": os.path.join(_get_log_dir(), _USAGE_LOG_FILE),
    }

def with_usage_log(tool_name: str):
    """工具函数日志装饰器：自动记录调用参数、耗时、结果"""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            # 从 kwargs 中提取参数（用于日志）
            params = {}
            for k, v in kwargs.items():
                if k not in ("return_response",):
                    params[k] = v
            # 如果有 self 参数（类方法），尝试提取其 attributes
            if args and hasattr(args[0], "__dict__"):
                instance_attrs = {
                    k: v for k, v in vars(args[0]).items()
                    if not k.startswith("_") and k not in ("mcp", "client", "logger")
                }
                params["_context"] = _sanitize_params(instance_attrs, max_len=100)
            sanitized_params = _sanitize_params(params)

            success = False
            result_preview = ""
            error_type = ""
            try:
                result = await func(*args, **kwargs)
                success = True
                if isinstance(result, str):
                    result_preview = result[:200]
                return result
            except Exception as e:
                error_type = type(e).__name__
                result_preview = str(e)[:200]
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                log_tool_usage(
                    tool_name=tool_name,
                    params=sanitized_params,
                    duration_ms=duration_ms,
                    success=success,
                    result_preview=result_preview,
                    error_type=error_type,
                )
        return wrapper
    return decorator


class ToolLogger:
    """工具函数日志上下文管理器，使用方法:

    ```python
    async def u9_query_bills(params) -> str:
        with ToolLogger("u9_query_bills", params) as logger:
            # ... 执行逻辑 ...
            logger.success(result)
            return result
    ```
    """
    def __init__(self, tool_name: str, params: dict):
        self.tool_name = tool_name
        self.params = _sanitize_params(params)
        self.start_time = time.perf_counter()
        self.success = False
        self.result_preview = ""
        self.error_type = ""

    def success(self, result: Any = None):
        self.success = True
        if result and isinstance(result, str):
            self.result_preview = result[:200]

    def error(self, exc: Exception):
        self.error_type = type(exc).__name__
        self.result_preview = str(exc)[:200]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        if exc_val:
            self.error(exc_val)
        log_tool_usage(
            tool_name=self.tool_name,
            params=self.params,
            duration_ms=duration_ms,
            success=self.success,
            result_preview=self.result_preview,
            error_type=self.error_type,
        )
        return False  # 不阻止异常传播

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)
        return False


def generate_usage_report(log_file: str = None) -> str:
    """生成使用报告"""
    import statistics

    if log_file is None:
        log_file = os.path.join(_get_log_dir(), _USAGE_LOG_FILE)

    if not os.path.exists(log_file):
        return "日志文件不存在，请先使用 MCP 工具。"

    # 读取所有日志
    entries = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return f"读取日志失败: {e}"

    if not entries:
        return "日志为空。"

    # 统计分析
    total_calls = len(entries)
    successful = sum(1 for e in entries if e.get("success"))
    failed = total_calls - successful

    # 工具使用排行
    tool_counts = defaultdict(int)
    tool_durations = defaultdict(list)
    error_types = defaultdict(int)
    for e in entries:
        tool_counts[e.get("tool", "unknown")] += 1
        tool_durations[e.get("tool", "unknown")].append(e.get("duration_ms", 0))
        if not e.get("success"):
            err_type = e.get("error_type", "unknown")
            error_types[err_type] += 1

    # 耗时统计
    all_durations = [e.get("duration_ms", 0) for e in entries]
    avg_duration = statistics.mean(all_durations) if all_durations else 0
    median_duration = statistics.median(all_durations) if all_durations else 0

    # 构建报告
    report_lines = [
        "=" * 60,
        "MCP 使用报告",
        "=" * 60,
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"日志文件: {log_file}",
        f"记录条目: {total_calls}",
        f"成功/失败: {successful}/{failed} ({successful/total_calls*100:.1f}% 成功率)" if total_calls else "N/A",
        "",
        "-" * 60,
        "📊 工具使用排行 (Top 10)",
        "-" * 60,
    ]

    sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (tool, count) in enumerate(sorted_tools, 1):
        durations = tool_durations[tool]
        avg_t = statistics.mean(durations) if durations else 0
        success_rate = sum(1 for e in entries if e.get("tool") == tool and e.get("success")) / count * 100
        report_lines.append(
            f"  {i:2}. {tool:<40} {count:4} 次 (平均 {avg_t:.0f}ms, 成功率 {success_rate:.0f}%)"
        )

    if error_types:
        report_lines.extend([
            "",
            "-" * 60,
            "❌ 错误类型统计",
            "-" * 60,
        ])
        sorted_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        for err_type, count in sorted_errors:
            report_lines.append(f"  • {err_type}: {count} 次")

    # 时段分布
    if entries:
        hours = defaultdict(int)
        for e in entries:
            try:
                hour = datetime.fromisoformat(e.get("timestamp", "")).hour
                hours[hour] += 1
            except (ValueError, TypeError):
                pass

        if hours:
            report_lines.extend([
                "",
                "-" * 60,
                "⏰ 使用时段分布",
                "-" * 60,
            ])
            max_count = max(hours.values())
            for h in range(24):
                count = hours.get(h, 0)
                bar = "█" * int(count / max_count * 20) if max_count > 0 else ""
                report_lines.append(f"  {h:02d}:00 {bar} {count}")

    # 性能建议
    slow_tools = [(t, d) for t, ds in tool_durations.items()
                  for d in ds if d > 5000]
    if slow_tools:
        report_lines.extend([
            "",
            "-" * 60,
            "⚡ 性能建议",
            "-" * 60,
        ])
        tool_slow = defaultdict(list)
        for t, d in slow_tools:
            tool_slow[t].append(d)
        for tool, durations in sorted(tool_slow.items(), key=lambda x: -statistics.mean(x[1]))[:5]:
            report_lines.append(f"  • {tool}: 平均 {statistics.mean(durations):.0f}ms (建议优化)")

    report_lines.extend([
        "",
        "=" * 60,
        f"📝 如需详细分析，请查看日志文件: {log_file}",
        "=" * 60,
    ])

    return "\n".join(report_lines)
