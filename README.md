# Node-RED MCP Server

一个用于管理远程 Node-RED 服务的 **MCP (Model Context Protocol)** 服务器，支持在 Dify、Claude Desktop、Cursor 等 MCP 客户端中通过自然语言对 Node-RED 的 flows（策略）进行增删改查、启用/停用、整体部署等操作。

## ✨ 功能

| 工具 | 说明 |
| --- | --- |
| `list_flows` | 列出所有 flow（tab）摘要 |
| `get_flow` | 获取单个 flow 的完整配置 |
| `get_all_flows_raw` | 获取全部 flows 原始配置（含 rev） |
| `create_flow` | 新建 flow |
| `update_flow` | 更新 flow（名称、描述、节点、启停） |
| `delete_flow` | 删除 flow |
| `enable_flow` / `disable_flow` | 启用 / 停用 flow |
| `deploy_flows` | 整体部署（等同编辑器 Deploy 按钮） |
| `list_node_types` | 列出已安装节点模块及类型 |
| `get_runtime_settings` | 查看 Node-RED 运行时 settings |

底层基于 [Node-RED Admin API](https://nodered.org/docs/api/admin/methods/) 实现。

## 📦 安装

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

## ⚙️ 配置

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

```dotenv
NODE_RED_URL=http://your-node-red:1880
NODE_RED_TOKEN=             # 推荐：直接使用 Bearer Token
NODE_RED_USERNAME=          # 或使用用户名密码（启用 adminAuth 时）
NODE_RED_PASSWORD=
```

### 如何获取 Node-RED 的 Token？

若 Node-RED 启用了 `adminAuth`，可通过：

```bash
curl -X POST http://your-node-red:1880/auth/token \
  -d "client_id=node-red-admin" \
  -d "grant_type=password" \
  -d "scope=*" \
  -d "username=admin" \
  -d "password=xxx"
```

返回的 `access_token` 即可作为 `NODE_RED_TOKEN`。

本项目也支持直接配置用户名/密码，启动时自动换取 token。

## 🚀 快速验证

先确认能连通 Node-RED：

```bash
python flow_get.py
```

正常应输出 flows 列表。

## ▶️ 运行 MCP Server

### 1. stdio 模式（本地，供 Cursor / Claude Desktop 使用）

```bash
python server.py
```

在 Cursor 的 `~/.cursor/mcp.json` 中加入：

```json
{
  "mcpServers": {
    "node-red": {
      "command": "python",
      "args": ["C:/02Code/Node-RED-MCP-Server/server.py"],
      "env": {
        "NODE_RED_URL": "http://your-node-red:1880",
        "NODE_RED_TOKEN": "xxx"
      }
    }
  }
}
```

### 2. SSE 模式（供 Dify 使用）

```bash
python server.py --transport sse --host 0.0.0.0 --port 8765
```

Dify → 工具 → MCP → 添加 MCP 服务：

- Server URL: `http://your-host:8765/sse`
- 传输类型: `SSE`

### 3. Streamable HTTP 模式

```bash
python server.py --transport http --host 0.0.0.0 --port 8765
```

URL 填 `http://your-host:8765/mcp`。

## 🧩 使用示例（通过大模型自然语言调用）

- "列出 Node-RED 上所有的 flow"
- "把名为 '温度告警' 的 flow 停用"
- "新建一个名为 'MQTT 采集' 的 flow，描述是 'xxx'"
- "把 id 为 `abc123` 的 flow 重命名为 '数据清洗'"
- "删除 id 为 `abc123` 的 flow"

## 📁 项目结构

```
.
├── server.py            # MCP Server 主入口
├── node_red_client.py   # Node-RED Admin API 客户端封装
├── flow_get.py          # 连接测试脚本
├── requirements.txt
├── .env.example
└── README.md
```

## ⚠️ 注意事项

- **整体部署会覆盖现有配置**，建议先用 `get_all_flows_raw` 备份。
- `update_flow` 中传入的 `nodes` 会**替换**该 tab 下所有节点，而非合并。
- Node-RED v3+ 默认使用 flows API v2，客户端已自动携带对应请求头。
- 建议为 MCP Server 配置反向代理 + HTTPS + 鉴权，避免暴露 Node-RED 管理面。
