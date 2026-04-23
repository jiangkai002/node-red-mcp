"""pytest 共享 fixture。

核心策略：
- 用 AsyncMock 替换 `server.get_client()` 返回的 NodeREDClient，避免真实 HTTP 调用。
- 提供 `call_tool` 工具函数，透明解包 FastMCP 的 `@mcp.tool` 装饰器。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

# 把项目根目录加入 sys.path，便于 `import server`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def _unwrap(tool: Any):
    """从 FastMCP 的 Tool 对象中取出原始 async 函数。

    FastMCP 2.x: `@mcp.tool` 会把函数替换为 FunctionTool 实例，
    原始协程函数存放在 `.fn` 属性上；若直接拿到函数也兼容。
    """
    if hasattr(tool, "fn"):
        return tool.fn
    return tool


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """返回一个 AsyncMock 作为 NodeREDClient，并接管 server.get_client。"""
    client = AsyncMock()
    monkeypatch.setattr(server, "_client", client)
    monkeypatch.setattr(server, "get_client", lambda: client)
    return client


@pytest.fixture
def call_tool():
    """调用被 @mcp.tool 装饰的函数。

    用法： result = await call_tool(server.list_flows, arg1=..., arg2=...)
    """

    async def _call(tool: Any, *args: Any, **kwargs: Any) -> Any:
        fn = _unwrap(tool)
        return await fn(*args, **kwargs)

    return _call
