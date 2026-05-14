import httpx
import os
from typing import Any
from dotenv import load_dotenv
import asyncio

load_dotenv()


class IBCNodeREDService:

    def __init__(self):
        self.client = httpx.AsyncClient(base_url=os.getenv("IBC_NODERED_URL"))

    async def get_flow_description(self, project_id: str) -> list[dict[str, Any]]:
        """获取指定项目下的设备控制策略列表。

        :param project_id: 项目 ID。
        :return: 策略列表，每项包含 id / name / flowId / description / category / lowCarbonValue。
        """
        resp = await self.client.get(
            f"/api/nodered/projects/{project_id}/DeviceControlStrategy"
        )
        resp.raise_for_status()
        return resp.json()

    async def get_room_strategy(
        self, project_id: str, room_number: str = None
    ) -> list[dict[str, Any]]:
        """获取指定房间下的设备控制策略列表。

        :param project_id: 项目 ID。
        :param room_number: 房间号,如果不传则获取项目下的所有策略。
        :return: 房间列表，每项包含 roomNumber / flowId。
        """
        resp = await self.client.get(
            f"/api/nodered/projects/{project_id}/roomtoflows",
            params={"filter": f'roomNumber="{room_number}"' if room_number else None},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_strategy_in_rooms(self, project_id: str, strategy_id: str):
        """获取指定策略在项目下的所有房间。

        :param project_id: 项目 ID。
        :param strategy_id: 策略 ID。
        :return: 房间列表，每项包含 roomNumber。
        """
        resp = await self.client.get(
            f"/api/nodered/projects/{project_id}/strategytoroom",
            params={"filter": f'flowId="{strategy_id}"' if strategy_id else None},
        )
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    service = IBCNodeREDService()
    result = asyncio.run(service.get_room_strategy("1486", "24XFJ"))
    print(result)
