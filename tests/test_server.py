from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import server
from node_red_client import NodeREDError


# ============================================================
# list_flows
# ============================================================


class TestListFlows:
    async def test_success_filters_only_tabs(
        self, mock_client: AsyncMock, call_tool
    ) -> None:
        mock_client.get_flows.return_value = {
            "rev": "rev-1",
            "flows": [
                {
                    "id": "t1",
                    "type": "tab",
                    "label": "A",
                    "disabled": False,
                    "info": "i1",
                },
                {"id": "t2", "type": "tab", "label": "B", "disabled": True, "info": ""},
                {"id": "n1", "type": "inject", "z": "t1"},  # 非 tab，应被过滤
            ],
        }

        result = await call_tool(server.list_flows)

        assert result["success"] is True
        assert result["data"]["rev"] == "rev-1"
        assert len(result["data"]["flows"]) == 2
        assert result["data"]["flows"][0] == {
            "id": "t1",
            "label": "A",
            "disabled": False,
            "info": "i1",
        }
        assert result["data"]["flows"][1]["disabled"] is True
        mock_client.get_flows.assert_awaited_once()

    async def test_empty_flows(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_flows.return_value = {"rev": None, "flows": []}
        result = await call_tool(server.list_flows)
        assert result["success"] is True
        assert result["data"]["flows"] == []
        assert "0 个" in result["message"]

    async def test_handles_api_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_flows.side_effect = NodeREDError("connection refused")
        result = await call_tool(server.list_flows)
        assert result["success"] is False
        assert "connection refused" in result["message"]
        assert result["data"] is None


# ============================================================
# get_flow
# ============================================================


class TestGetFlow:
    async def test_success(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_flow.return_value = {
            "id": "t1",
            "label": "Demo",
            "nodes": [{"id": "n1", "type": "inject"}],
        }
        result = await call_tool(server.get_flow, "t1")
        assert result["success"] is True
        assert result["data"]["id"] == "t1"
        mock_client.get_flow.assert_awaited_once_with("t1")

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_flow.side_effect = NodeREDError("404 Not Found")
        result = await call_tool(server.get_flow, "missing")
        assert result["success"] is False
        assert "404" in result["message"]


# ============================================================
# get_all_flows_raw
# ============================================================


class TestGetAllFlowsRaw:
    async def test_success(self, mock_client: AsyncMock, call_tool) -> None:
        payload = {"rev": "r1", "flows": [{"id": "t1", "type": "tab"}]}
        mock_client.get_flows.return_value = payload
        result = await call_tool(server.get_all_flows_raw)
        assert result["success"] is True
        assert result["data"] == payload

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_flows.side_effect = NodeREDError("boom")
        result = await call_tool(server.get_all_flows_raw)
        assert result["success"] is False


# ============================================================
# create_flow
# ============================================================


class TestCreateFlow:
    async def test_minimal(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.create_flow.return_value = {"id": "new-id"}
        result = await call_tool(server.create_flow, label="MyFlow")

        assert result["success"] is True
        assert "MyFlow" in result["message"]
        mock_client.create_flow.assert_awaited_once()

        payload = mock_client.create_flow.call_args.args[0]
        assert payload["label"] == "MyFlow"
        assert payload["info"] == ""
        assert payload["disabled"] is False
        assert payload["nodes"] == []
        assert "id" in payload and len(payload["id"]) > 0

    async def test_normalizes_nodes(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.create_flow.return_value = {"id": "new-id"}
        nodes = [
            {"type": "inject", "name": "n1"},  # 无 id、无 z
            {"id": "fixed", "type": "debug", "z": "will-be-overwritten"},
        ]
        await call_tool(
            server.create_flow,
            label="L",
            nodes=nodes,
            info="desc",
            disabled=True,
        )

        payload = mock_client.create_flow.call_args.args[0]
        flow_id = payload["id"]
        assert payload["disabled"] is True
        assert payload["info"] == "desc"
        assert len(payload["nodes"]) == 2
        for n in payload["nodes"]:
            assert "id" in n and n["id"]
            assert n["z"] == flow_id  # 新建时 z 统一指向新 flow
        assert payload["nodes"][1]["id"] == "fixed"

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.create_flow.side_effect = NodeREDError("bad request")
        result = await call_tool(server.create_flow, label="X")
        assert result["success"] is False
        assert "bad request" in result["message"]


# ============================================================
# update_flow
# ============================================================


class TestUpdateFlow:
    async def test_partial_update_preserves_existing(
        self, mock_client: AsyncMock, call_tool
    ) -> None:
        mock_client.get_flow.return_value = {
            "id": "t1",
            "label": "Old",
            "info": "old-info",
            "disabled": False,
            "nodes": [{"id": "n1", "type": "inject", "z": "t1"}],
        }
        mock_client.update_flow.return_value = {"id": "t1"}

        result = await call_tool(server.update_flow, "t1", label="New")

        assert result["success"] is True
        mock_client.get_flow.assert_awaited_once_with("t1")
        mock_client.update_flow.assert_awaited_once()
        flow_id_arg, payload = mock_client.update_flow.call_args.args
        assert flow_id_arg == "t1"
        assert payload["label"] == "New"
        assert payload["info"] == "old-info"  # 未传则保留原值
        assert payload["disabled"] is False
        assert payload["nodes"] == [{"id": "n1", "type": "inject", "z": "t1"}]

    async def test_replace_nodes_and_toggle_disabled(
        self, mock_client: AsyncMock, call_tool
    ) -> None:
        mock_client.get_flow.return_value = {
            "id": "t1",
            "label": "A",
            "info": "",
            "disabled": False,
            "nodes": [{"id": "old", "type": "debug", "z": "t1"}],
        }
        mock_client.update_flow.return_value = {"id": "t1"}

        new_nodes = [{"type": "inject"}, {"id": "keep", "type": "debug"}]
        await call_tool(
            server.update_flow,
            "t1",
            nodes=new_nodes,
            disabled=True,
            info="updated",
        )

        _, payload = mock_client.update_flow.call_args.args
        assert payload["disabled"] is True
        assert payload["info"] == "updated"
        assert len(payload["nodes"]) == 2
        for n in payload["nodes"]:
            assert n["z"] == "t1"  # 全部 z 指向被更新的 flow
            assert "id" in n and n["id"]
        assert payload["nodes"][1]["id"] == "keep"

    async def test_error_on_get(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_flow.side_effect = NodeREDError("not found")
        result = await call_tool(server.update_flow, "t1", label="X")
        assert result["success"] is False
        mock_client.update_flow.assert_not_called()


# ============================================================
# delete_flow
# ============================================================


class TestDeleteFlow:
    async def test_success(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.delete_flow.return_value = None
        result = await call_tool(server.delete_flow, "t1")
        assert result["success"] is True
        assert "t1" in result["message"]
        mock_client.delete_flow.assert_awaited_once_with("t1")

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.delete_flow.side_effect = NodeREDError("403")
        result = await call_tool(server.delete_flow, "t1")
        assert result["success"] is False
        assert "403" in result["message"]


# ============================================================
# enable_flow / disable_flow
# ============================================================


class TestEnableDisableFlow:
    async def test_enable_flow(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.set_flow_state.return_value = {"id": "t1", "disabled": False}
        result = await call_tool(server.enable_flow, "t1")
        assert result["success"] is True
        mock_client.set_flow_state.assert_awaited_once_with("t1", disabled=False)

    async def test_disable_flow(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.set_flow_state.return_value = {"id": "t1", "disabled": True}
        result = await call_tool(server.disable_flow, "t1")
        assert result["success"] is True
        mock_client.set_flow_state.assert_awaited_once_with("t1", disabled=True)

    async def test_enable_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.set_flow_state.side_effect = NodeREDError("oops")
        result = await call_tool(server.enable_flow, "t1")
        assert result["success"] is False


# ============================================================
# deploy_flows
# ============================================================


class TestDeployFlows:
    async def test_full_deploy_default(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.set_flows.return_value = {"rev": "r2"}
        flows = [{"id": "t1", "type": "tab", "label": "A"}]
        result = await call_tool(server.deploy_flows, flows)
        assert result["success"] is True
        mock_client.set_flows.assert_awaited_once_with(
            flows, rev=None, deployment_type="full"
        )

    async def test_with_rev_and_type(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.set_flows.return_value = {"rev": "r3"}
        flows: list[dict] = []
        await call_tool(
            server.deploy_flows,
            flows,
            rev="r1",
            deployment_type="nodes",
        )
        mock_client.set_flows.assert_awaited_once_with(
            flows, rev="r1", deployment_type="nodes"
        )

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.set_flows.side_effect = NodeREDError("rev mismatch")
        result = await call_tool(server.deploy_flows, [])
        assert result["success"] is False
        assert "rev mismatch" in result["message"]


# ============================================================
# list_node_types
# ============================================================


class TestListNodeTypes:
    async def test_success(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_nodes.return_value = [
            {
                "id": "node-red/inject",
                "name": "inject",
                "types": ["inject"],
                "enabled": True,
                "module": "node-red",
                "version": "4.0.0",
            },
            {
                "id": "contrib/mqtt",
                "name": "mqtt",
                "types": ["mqtt in", "mqtt out"],
                "enabled": False,
                "module": "node-red-contrib-mqtt",
                "version": "1.0.0",
            },
        ]
        result = await call_tool(server.list_node_types)
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][1]["types"] == ["mqtt in", "mqtt out"]
        assert "2 个" in result["message"]

    async def test_empty(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_nodes.return_value = []
        result = await call_tool(server.list_node_types)
        assert result["success"] is True
        assert result["data"] == []

    async def test_none_response(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_nodes.return_value = None
        result = await call_tool(server.list_node_types)
        assert result["success"] is True
        assert result["data"] == []

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_nodes.side_effect = NodeREDError("timeout")
        result = await call_tool(server.list_node_types)
        assert result["success"] is False


# ============================================================
# get_runtime_settings
# ============================================================


class TestGetRuntimeSettings:
    async def test_success(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_settings.return_value = {"version": "4.0.0"}
        result = await call_tool(server.get_runtime_settings)
        assert result["success"] is True
        assert result["data"]["version"] == "4.0.0"

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_settings.side_effect = NodeREDError("401")
        result = await call_tool(server.get_runtime_settings)
        assert result["success"] is False


# ============================================================
# _ok / _err 工具函数
# ============================================================


class TestHelpers:
    def test_ok_structure(self) -> None:
        r = server._ok({"a": 1}, "done")
        assert r == {"success": True, "message": "done", "data": {"a": 1}}

    def test_ok_default_message(self) -> None:
        r = server._ok([1, 2])
        assert r["success"] is True
        assert r["message"] == "ok"

    def test_err_structure(self) -> None:
        r = server._err("bad")
        assert r == {"success": False, "message": "bad", "data": None}


class TestGetCustomNodes:
    _MOCK_DATA = {
        "name": "scc4-device-registry",
        "version": "1.4.7",
        "local": False,
        "user": False,
        "path": "/usr/src/node-red/node_modules/scc4-device-registry",
        "nodes": [
            {"id": "scc4-device-registry/Air", "name": "Air", "types": ["Air"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/WorkdayJudge", "name": "WorkdayJudge", "types": ["WorkdayJudge"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/Light", "name": "Light", "types": ["Light"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/FreshAir", "name": "FreshAir", "types": ["FreshAir"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/CO2Sensor", "name": "CO2Sensor", "types": ["CO2Sensor"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/PM25Sensor", "name": "PM25Sensor", "types": ["PM25Sensor"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/Curtain", "name": "Curtain", "types": ["Curtain"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/SignalR", "name": "SignalR", "types": ["SignalRNode"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/OCCSensor", "name": "OCCSensor", "types": ["OCCSensor"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/CommonLight", "name": "CommonLight", "types": ["CommonLight"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/Television", "name": "Television", "types": ["Television"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/OutdoorSenser", "name": "OutdoorSenser", "types": ["OutdoorSensor"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/IndoorSenser", "name": "IndoorSenser", "types": ["EnvSensor"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/LuxSensor", "name": "LuxSensor", "types": ["LuxSensor"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
            {"id": "scc4-device-registry/LogNode", "name": "LogNode", "types": ["LogNode"], "enabled": True, "local": False, "user": False, "module": "scc4-device-registry", "version": "1.4.7"},
        ],
    }

    async def test_success(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_custom_nodes.return_value = self._MOCK_DATA
        result = await call_tool(server.get_custom_nodes)

        assert result["success"] is True
        assert result["data"]["name"] == "scc4-device-registry"
        assert result["data"]["version"] == "1.4.7"
        assert len(result["data"]["nodes"]) == 15
        node_names = [n["name"] for n in result["data"]["nodes"]]
        assert "Air" in node_names
        assert "SignalR" in node_names
        assert "LogNode" in node_names
        mock_client.get_custom_nodes.assert_awaited_once()

    async def test_node_types_correct(self, mock_client: AsyncMock, call_tool) -> None:
        """验证 types 字段与 name 不一定相同（如 SignalR → SignalRNode）。"""
        mock_client.get_custom_nodes.return_value = self._MOCK_DATA
        result = await call_tool(server.get_custom_nodes)

        nodes_by_name = {n["name"]: n for n in result["data"]["nodes"]}
        assert nodes_by_name["SignalR"]["types"] == ["SignalRNode"]
        assert nodes_by_name["OutdoorSenser"]["types"] == ["OutdoorSensor"]
        assert nodes_by_name["IndoorSenser"]["types"] == ["EnvSensor"]

    async def test_all_nodes_enabled(self, mock_client: AsyncMock, call_tool) -> None:
        """验证所有节点均为 enabled 状态。"""
        mock_client.get_custom_nodes.return_value = self._MOCK_DATA
        result = await call_tool(server.get_custom_nodes)

        disabled = [n["name"] for n in result["data"]["nodes"] if not n["enabled"]]
        assert disabled == [], f"以下节点未启用: {disabled}"

    async def test_error(self, mock_client: AsyncMock, call_tool) -> None:
        mock_client.get_custom_nodes.side_effect = NodeREDError("module not found")
        result = await call_tool(server.get_custom_nodes)

        assert result["success"] is False
        assert "module not found" in result["message"]
        assert result["data"] is None
