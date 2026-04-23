from __future__ import annotations

import asyncio
import json
import os

from dotenv import load_dotenv

from node_red_client import NodeREDClient, NodeREDError


async def main() -> None:
    load_dotenv()
    client = NodeREDClient(
        base_url=os.getenv("NODE_RED_URL", "http://127.0.0.1:1880"),
        token=os.getenv("NODE_RED_TOKEN") or None,
        username=os.getenv("NODE_RED_USERNAME") or None,
        password=os.getenv("NODE_RED_PASSWORD") or None,
    )
    try:
        flows = await client.get_flows()
        tabs = [n for n in flows if n.get("type") == "tab"]
        print(f"Node-RED 连接成功，共 {len(tabs)} 个 flow：")
        for t in tabs:
            state = "停用" if t.get("disabled") else "启用"
            print(f"  - [{state}] {t.get('id')}  {t.get('label')}")
    except NodeREDError as e:
        print("调用失败：", e)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
