"""独立登录测试：读取 MCP 客户端配置里的 u9 env，实机验证 _login()。

默认读取 ~/.workbuddy/mcp.json，可用 U9_MCP_CONFIG 指定配置文件；
用 U9_MCP_SERVER 指定 mcpServers 下的服务名（默认 u9）。
也可以不提供配置文件，直接使用当前进程已有的 U9_* 环境变量。

手工运行：
    python tests/manual/test_login.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

CONFIG_PATH = Path(
    os.environ.get("U9_MCP_CONFIG", Path.home() / ".workbuddy" / "mcp.json")
)
SERVER_NAME = os.environ.get("U9_MCP_SERVER", "u9")


def load_env_from_config() -> None:
    """把 MCP 配置里的 env 注入当前进程（已存在的环境变量优先）。"""
    if not CONFIG_PATH.exists():
        print(f"[WARN] 未找到 MCP 配置 {CONFIG_PATH}，直接使用当前环境变量")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    entry = cfg.get("mcpServers", {}).get(SERVER_NAME)
    if entry is None:
        raise KeyError(f"配置 {CONFIG_PATH} 中没有 mcpServers.{SERVER_NAME}")
    for k, v in entry.get("env", {}).items():
        os.environ.setdefault(k, str(v))


async def main():
    load_env_from_config()

    # 环境变量设置完成后再导入，确保 settings 读取到正确的配置
    import u9_mcp.server as s  # noqa: E402

    print(f"[INFO] SERVER   = {s.SERVER_URL}")
    print(f"[INFO] ACCT_ID  = {s.ACCT_ID}")
    print(f"[INFO] USERNAME = {s.USERNAME}")
    print(f"[INFO] PASSWORD = {'***已配置***' if s.PASSWORD else '(空，账号密码登录模式，必须填写)'}")
    try:
        sid = await s._login()
        print(f"[OK] 登录成功，SessionId 前缀: {sid[:12]}...")
    except RuntimeError as e:
        print(f"[EXPECTED] 缺少密码时的报错: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] 登录失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
