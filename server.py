from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP

from node_red_client import NodeREDClient, NodeREDError

load_dotenv()

NODE_RED_URL = os.getenv("NODE_RED_URL", "http://127.0.0.1:1880")
NODE_RED_TOKEN = os.getenv("NODE_RED_TOKEN") or None
NODE_RED_USERNAME = os.getenv("NODE_RED_USERNAME") or None
NODE_RED_PASSWORD = os.getenv("NODE_RED_PASSWORD") or None

mcp = FastMCP(
    name="NodeRED-MCP",
    instructions=(
        "用于管理远程 Node-RED 服务的 flows（策略）。"
        "支持列出、查看、创建、修改、删除、启用/停用 flow，以及整体部署。"
    ),
)

_client: NodeREDClient | None = None


def get_client() -> NodeREDClient:
    global _client
    if _client is None:
        _client = NodeREDClient(
            base_url=NODE_RED_URL,
            token=NODE_RED_TOKEN,
            username=NODE_RED_USERNAME,
            password=NODE_RED_PASSWORD,
        )
    return _client


def _ok(data: Any, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}


def _err(message: str) -> dict[str, Any]:
    return {"success": False, "message": message, "data": None}


@mcp.tool
async def list_flows() -> dict[str, Any]:
    """列出所有 flow（tab）的摘要信息。

    返回：每个 flow 的 id、label（名称）、disabled（是否停用）、info（描述）。
    不返回节点细节，便于快速概览。
    """
    try:
        client = get_client()
        result = await client.get_flows()
        flows = result.get("flows", []) if isinstance(result, dict) else result
        tabs = [
            {
                "id": n.get("id"),
                "label": n.get("label") or n.get("name") or "",
                "disabled": bool(n.get("disabled", False)),
                "info": n.get("info", ""),
            }
            for n in flows
            if n.get("type") == "tab"
        ]
        rev = result.get("rev") if isinstance(result, dict) else None
        return _ok({"rev": rev, "flows": tabs}, f"共 {len(tabs)} 个 flow")
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def get_flow(flow_id: str) -> dict[str, Any]:
    """获取指定 flow（tab）的完整配置，含其下所有节点。

    :param flow_id: flow 的 id（即 tab 节点的 id）。
    """
    try:
        client = get_client()
        data = await client.get_flow(flow_id)
        return _ok(data)
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def get_all_flows_raw() -> dict[str, Any]:
    """获取 Node-RED 全部 flows 的原始配置（含所有节点 & rev 版本号）。

    适合在需要批量分析或整体部署前使用。返回内容可能较大。
    """
    try:
        client = get_client()
        data = await client.get_flows()
        return _ok(data)
    except NodeREDError as e:
        return _err(str(e))


# ============================================================
# Flow 创建 / 修改 / 删除
# ============================================================


@mcp.tool
async def create_flow(
    label: str,
    nodes: list[dict[str, Any]] | None = None,
    info: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    """新建一个 flow（tab）。

    :param label: flow 名称。
    :param nodes: flow 下的节点数组，可为空。每个节点需至少包含 id/type，
                  若不指定 z 字段会自动补全为新 flow 的 id。
    :param info: flow 描述。
    :param disabled: 是否创建后即停用。
    """
    try:
        client = get_client()
        flow_id = uuid.uuid4().hex[:16]
        normalized_nodes: list[dict[str, Any]] = []
        for node in nodes or []:
            n = dict(node)
            n.setdefault("id", uuid.uuid4().hex[:16])
            n.setdefault("z", flow_id)
            normalized_nodes.append(n)
        payload = {
            "id": flow_id,
            "label": label,
            "disabled": disabled,
            "info": info,
            "nodes": normalized_nodes,
        }
        data = await client.create_flow(payload)
        return _ok(data, f"已创建 flow: {label}")
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def update_flow(
    flow_id: str,
    label: str | None = None,
    nodes: list[dict[str, Any]] | None = None,
    info: str | None = None,
    disabled: bool | None = None,
) -> dict[str, Any]:
    """更新一个已有 flow（tab）。

    未传入的字段将沿用当前 flow 的值。传入 nodes 会整体替换该 tab 下的节点。

    :param flow_id: flow 的 id。
    :param label: 新名称。
    :param nodes: 新的节点数组（会替换原有节点）。
    :param info: 新描述。
    :param disabled: 是否停用。
    """
    try:
        client = get_client()
        current = await client.get_flow(flow_id)
        if label is not None:
            current["label"] = label
        if info is not None:
            current["info"] = info
        if disabled is not None:
            current["disabled"] = bool(disabled)
        if nodes is not None:
            normalized: list[dict[str, Any]] = []
            for node in nodes:
                n = dict(node)
                n.setdefault("id", uuid.uuid4().hex[:16])
                n["z"] = flow_id
                normalized.append(n)
            current["nodes"] = normalized
        data = await client.update_flow(flow_id, current)
        return _ok(data, f"已更新 flow: {flow_id}")
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def delete_flow(flow_id: str) -> dict[str, Any]:
    """删除指定 flow（tab）及其所有节点。

    :param flow_id: flow 的 id。
    """
    try:
        client = get_client()
        await client.delete_flow(flow_id)
        return _ok(None, f"已删除 flow: {flow_id}")
    except NodeREDError as e:
        return _err(str(e))


# ============================================================
# 启用 / 停用
# ============================================================


@mcp.tool
async def enable_flow(flow_id: str) -> dict[str, Any]:
    """启用指定 flow。"""
    try:
        client = get_client()
        data = await client.set_flow_state(flow_id, disabled=False)
        return _ok(data, f"已启用 flow: {flow_id}")
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def disable_flow(flow_id: str) -> dict[str, Any]:
    """停用指定 flow。"""
    try:
        client = get_client()
        data = await client.set_flow_state(flow_id, disabled=True)
        return _ok(data, f"已停用 flow: {flow_id}")
    except NodeREDError as e:
        return _err(str(e))


# ============================================================
# 整体部署 & 节点信息
# ============================================================


@mcp.tool
async def deploy_flows(
    flows: list[dict[str, Any]],
    rev: str | None = None,
    deployment_type: str = "full",
) -> dict[str, Any]:
    """整体部署 flows（相当于编辑器里的 Deploy 按钮）。

    :param flows: 完整的节点数组（tab / subflow / 普通节点）。
    :param rev: 当前 rev 版本号，用于乐观锁，防止并发覆盖；不传则强制覆盖。
    :param deployment_type: full / nodes / flows / reload，默认 full。
    """
    try:
        client = get_client()
        data = await client.set_flows(flows, rev=rev, deployment_type=deployment_type)
        return _ok(data, f"已部署，共 {len(flows)} 个节点")
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def list_node_types() -> dict[str, Any]:
    """列出 Node-RED 已安装的所有节点模块及其提供的节点类型。

    方便在创建/修改 flow 时确认节点 type 是否存在。
    """
    try:
        client = get_client()
        data = await client.get_nodes()
        summary = [
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "types": n.get("types", []),
                "enabled": n.get("enabled", True),
                "module": n.get("module"),
                "version": n.get("version"),
            }
            for n in (data or [])
        ]
        return _ok(summary, f"共 {len(summary)} 个节点模块")
    except NodeREDError as e:
        return _err(str(e))


@mcp.tool
async def get_runtime_settings() -> dict[str, Any]:
    """获取 Node-RED 运行时公开的 settings，用于排查版本/能力。"""
    try:
        client = get_client()
        data = await client.get_settings()
        return _ok(data)
    except NodeREDError as e:
        return _err(str(e))


# ============================================================
# 入口
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Node-RED MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="传输方式，默认 stdio",
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8765")))
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
