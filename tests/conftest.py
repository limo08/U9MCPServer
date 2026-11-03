"""
pytest 配置：集成 + 端到端测试需要真实用友服务器
没有配置环境变量时静默跳过
"""

import os
import pytest

# tests/manual/ 下是需真实用友环境或人工观察输出的脚本，不是 pytest 用例。
# 文件名虽包含 test，但不参与自动收集，避免 pytest 导入时触发实机调用。
collect_ignore_glob = ["manual/*"]

HAS_U9_CONFIG = bool(
    os.getenv("U9_API_SERVER_URL") and
    os.getenv("U9_API_USERNAME") and
    os.getenv("U9_API_ENT_CODE") and
    os.getenv("U9_API_ORG_CODE") and
    (os.getenv("U9_API_TOKEN") or (
        os.getenv("U9_API_CLIENT_ID") and os.getenv("U9_API_CLIENT_SECRET")
    ))
)


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: 真实用友环境的端到端测试（需 U9_API_* 环境变量）")


def pytest_collection_modifyitems(config, items):
    """test_integration.py 与 tests/e2e/ 在无真实配置时跳过"""
    skip_reason = "需要真实用友服务器环境变量（U9_API_SERVER_URL 等），当前未配置"
    needs_real = ("test_integration", "tests/e2e", "tests\\e2e")
    for item in items:
        if any(key in item.nodeid for key in needs_real):
            if not HAS_U9_CONFIG:
                item.add_marker(pytest.mark.skip(reason=skip_reason))