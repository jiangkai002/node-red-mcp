from __future__ import annotations

import json
import os
import logging
import time
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

from logging.handlers import TimedRotatingFileHandler
_file_handler = TimedRotatingFileHandler(
    filename=os.path.join(_LOG_DIR, "mcp.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8",
)
_file_handler.setFormatter(_formatter)
_file_handler.suffix = "%Y-%m-%d"

logger = logging.getLogger("nodered-mcp")
logger.setLevel(logging.INFO)
logger.addHandler(_console_handler)
logger.addHandler(_file_handler)
logger.propagate = False


class ToolCallLogger(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        arguments = context.message.arguments or {}
        logger.info(">>> 调用工具: %s | 参数: %s", tool_name, json.dumps(arguments, ensure_ascii=False))
        t0 = time.perf_counter()
        try:
            result = await call_next(context)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("<<< 完成工具: %s | 耗时: %.1fms", tool_name, elapsed)
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error("<<< 工具异常: %s | 耗时: %.1fms | 错误: %s", tool_name, elapsed, exc)
            raise


mcp = FastMCP(
    name="NodeRED-MCP",
    instructions=(
        "用于管理远程 Node-RED 服务的 flows（策略）。"
        "支持列出、查看、创建、修改、删除、启用/停用 flow，以及整体部署。"
    ),
)
mcp.add_middleware(ToolCallLogger())


def _ok(data: Any, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}


def _err(message: str) -> dict[str, Any]:
    return {"success": False, "message": message, "data": None}
