from node_red_client import NodeREDClient
import os
from dotenv import load_dotenv
load_dotenv()

class NodeREDTemplateClient:
    def __init__(self):
        self.client = NodeREDClient(
            base_url=os.getenv("NODE_RED_URL","http://127.0.0.1:1880"),
            token="",
            username="admin",
            password="admin",
        )
    
    def get_flow_template(self):
        flows = self.client.get_flows()
        return flows


