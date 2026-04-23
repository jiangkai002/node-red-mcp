"""Node-RED Admin API 客户端封装。

文档参考: https://nodered.org/docs/api/admin/methods/
"""
from __future__ import annotations

from typing import Any

import httpx


class NodeREDError(Exception):
    """Node-RED API 调用异常。"""


class NodeREDClient:
    """Node-RED Admin API 客户端。

    支持 Node-RED v1.x / v2.x / v3.x 的 flows API。
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            auth = None
            if not self.token and self.username and self.password:
                # Node-RED 默认不直接支持 Basic Auth，但可能在反向代理层配置
                auth = httpx.BasicAuth(self.username, self.password)
                # 如果 Node-RED 自身启用了用户认证，应先走 /auth/token 获取 token
                token = await self._login_for_token(self.username, self.password)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    auth = None

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                auth=auth,
            )
        return self._client

    async def _login_for_token(self, username: str, password: str) -> str | None:
        """调用 /auth/token 换取 Bearer Token（Node-RED 启用 adminAuth 时）。"""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as c:
                resp = await c.post(
                    "/auth/token",
                    data={
                        "client_id": "node-red-admin",
                        "grant_type": "password",
                        "scope": "*",
                        "username": username,
                        "password": password,
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")
        except httpx.HTTPError:
            return None
        return None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        client = await self._get_client()
        try:
            resp = await client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise NodeREDError(f"Node-RED 请求失败: {e}") from e

        if resp.status_code >= 400:
            raise NodeREDError(
                f"Node-RED API 错误 {resp.status_code}: {resp.text}"
            )
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # ---------- Flows（全局） ----------

    async def get_flows(self) -> dict[str, Any]:
        """获取全部 flows 配置（包含 rev 版本号与所有节点）。"""
        return await self._request("GET", "/flows")

    async def set_flows(
        self,
        flows: list[dict[str, Any]],
        rev: str | None = None,
        deployment_type: str = "full",
    ) -> dict[str, Any]:
        """整体部署 flows。

        :param flows: 节点数组（包含 tab/subflow/普通节点）。
        :param rev: 当前 flows 的版本号，用于乐观锁；不传则强制覆盖。
        :param deployment_type: full / nodes / flows / reload。
        """
        payload: dict[str, Any] = {"flows": flows}
        if rev:
            payload["rev"] = rev
        headers = {"Node-RED-Deployment-Type": deployment_type}
        return await self._request("POST", "/flows", json=payload, headers=headers)

    # ---------- Flow（单个 tab） ----------

    async def get_flow(self, flow_id: str) -> dict[str, Any]:
        """获取单个 flow（tab）的完整信息，包含其下所有节点。"""
        return await self._request("GET", f"/flow/{flow_id}")

    async def create_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
        """新增一个 flow（tab），payload 需包含 label / nodes 等字段。"""
        return await self._request("POST", "/flow", json=flow)

    async def update_flow(self, flow_id: str, flow: dict[str, Any]) -> dict[str, Any]:
        """更新单个 flow（tab），会替换该 tab 下所有节点。"""
        return await self._request("PUT", f"/flow/{flow_id}", json=flow)

    async def delete_flow(self, flow_id: str) -> None:
        """删除单个 flow（tab）及其所有节点。"""
        await self._request("DELETE", f"/flow/{flow_id}")

    # ---------- 启用 / 停用 ----------

    async def set_flow_state(self, flow_id: str, disabled: bool) -> dict[str, Any]:
        """启用或停用指定 flow（tab）。

        通过获取当前 flow，修改 disabled 字段，再整体 PUT 回去实现。
        """
        flow = await self.get_flow(flow_id)
        flow["disabled"] = bool(disabled)
        return await self.update_flow(flow_id, flow)

    # ---------- 节点信息 ----------

    async def get_nodes(self) -> list[dict[str, Any]]:
        """获取已安装的所有节点模块信息。"""
        return await self._request("GET", "/nodes")

    async def get_settings(self) -> dict[str, Any]:
        """获取 Node-RED 运行时 settings。"""
        return await self._request("GET", "/settings")
