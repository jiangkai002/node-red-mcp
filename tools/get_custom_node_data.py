"""解析 CustomNodes 目录下的自定义节点 HTML，提取结构化信息供大模型使用。

每个 HTML 文件包含：
  1. <script type="text/javascript"> — RED.nodes.registerType(...) 节点注册配置
  2. <script type="text/html" data-template-name="..."> — 编辑器 UI 字段模板

本模块提供：
  - get_node_info(name)    按节点名称获取解析后的结构化数据
  - list_node_names()      列出所有可用节点名称
  - get_node_raw(name)     按节点名称获取原始 HTML
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CUSTOM_NODES_DIR = Path(__file__).resolve().parent.parent / "CustomNodes"


def _html_files() -> list[Path]:
    return sorted(CUSTOM_NODES_DIR.glob("*.html"))


def _extract_register_type_name(js_block: str) -> str | None:
    """从 registerType("NodeName", ...) 中提取节点类型名称。"""
    m = re.search(r'RED\.nodes\.registerType\(\s*["\']([^"\']+)["\']', js_block)
    return m.group(1) if m else None


def _extract_defaults(js_block: str) -> dict[str, Any]:
    """从 defaults: { ... } 中提取字段名及默认值。"""
    defaults: dict[str, Any] = {}
    m = re.search(
        r"defaults\s*:\s*\{([\s\S]*?)\},?\s*(?:inputs|outputs|icon|label|color|category)",
        js_block,
    )
    if not m:
        return defaults
    block = m.group(1)
    for field_m in re.finditer(r"(\w+)\s*:\s*\{\s*value\s*:\s*([^}]+?)\s*\}", block):
        key = field_m.group(1)
        raw_val = field_m.group(2).strip().rstrip(",")
        if raw_val in ("true", "false"):
            defaults[key] = raw_val == "true"
        elif raw_val.startswith('"') or raw_val.startswith("'"):
            defaults[key] = raw_val.strip("\"'")
        else:
            try:
                defaults[key] = int(raw_val)
            except ValueError:
                defaults[key] = raw_val
    return defaults


def _extract_int(js_block: str, key: str) -> int | None:
    m = re.search(rf"{key}\s*:\s*(\d+)", js_block)
    return int(m.group(1)) if m else None


def _extract_labels(js_block: str, key: str) -> list[str]:
    m = re.search(rf"{key}\s*:\s*\[([^\]]*)\]", js_block)
    if not m:
        return []
    return re.findall(r'["\']([^"\']+)["\']', m.group(1))


def _extract_template_html(html: str, node_type: str) -> str:
    """提取 data-template-name 对应的 HTML 模板内容。"""
    pattern = rf'<script[^>]*data-template-name=["\']?{re.escape(node_type)}["\']?[^>]*>([\s\S]*?)</script>'
    m = re.search(pattern, html)
    return m.group(1).strip() if m else ""


def _extract_help_text(html: str, node_type: str) -> str:
    """提取 data-help-name 对应的帮助文本。"""
    pattern = rf'<script[^>]*data-help-name=["\']?{re.escape(node_type)}["\']?[^>]*>([\s\S]*?)</script>'
    m = re.search(pattern, html)
    if not m:
        return ""
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


def _parse_html(path: Path) -> dict[str, Any] | None:
    """解析单个 HTML 文件，返回结构化节点信息。"""
    html = path.read_text(encoding="utf-8")

    js_m = re.search(r'<script type="text/javascript">([\s\S]*?)</script>', html)
    if not js_m:
        return None
    js_block = js_m.group(1)

    node_type = _extract_register_type_name(js_block)
    if not node_type:
        return None

    return {
        "node_type": node_type,
        "file": path.name,
        "category": (
            re.search(r'category\s*:\s*["\']([^"\']+)["\']', js_block) or [None, ""]
        )[1],
        "color": (
            re.search(r'color\s*:\s*["\']([^"\']+)["\']', js_block) or [None, ""]
        )[1],
        "inputs": _extract_int(js_block, "inputs") or 0,
        "outputs": _extract_int(js_block, "outputs") or 0,
        "output_labels": _extract_labels(js_block, "outputLabels"),
        "input_labels": _extract_labels(js_block, "inputLabels"),
        "defaults": _extract_defaults(js_block),
        "template_html": _extract_template_html(html, node_type),
        "help_text": _extract_help_text(html, node_type),
        "raw_html": html,
    }


# ---------------------------------------------------------------------------
# 构建名称索引（文件名 / node_type 均可查找，大小写不敏感）
# ---------------------------------------------------------------------------


def _build_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in _html_files():
        info = _parse_html(path)
        if info is None:
            continue
        stem = path.stem.lower()
        node_type = info["node_type"].lower()
        index[stem] = info
        index[node_type] = info
    return index


_INDEX: dict[str, dict[str, Any]] | None = None


def _get_index() -> dict[str, dict[str, Any]]:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def list_node_names() -> list[dict[str, str]]:
    """返回所有可用节点的名称列表。

    每项包含：
      - file_name: HTML 文件名（不含后缀）
      - node_type: registerType 中注册的类型名
    """
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for info in _get_index().values():
        key = info["node_type"]
        if key not in seen:
            seen.add(key)
            result.append({"file_name": Path(info["file"]).stem, "node_type": key})
    return sorted(result, key=lambda x: x["node_type"])


def get_node_info(name: str) -> dict[str, Any] | None:
    """按节点名称获取解析后的结构化信息（不含原始 HTML）。

    :param name: 节点类型名或文件名，大小写不敏感。
                 例如 "Air" / "air" / "SignalRNode" / "SignalR"
    :return: 包含 node_type / defaults / inputs / outputs / template_html 等字段的字典，
             找不到时返回 None。
    """
    info = _get_index().get(name.lower())
    if info is None:
        return None
    return {k: v for k, v in info.items() if k != "raw_html"}


def get_node_raw(name: str) -> str | None:
    """按节点名称获取原始 HTML 文件内容。

    :param name: 节点类型名或文件名，大小写不敏感。
    :return: 原始 HTML 字符串，找不到时返回 None。
    """
    info = _get_index().get(name.lower())
    return info["raw_html"] if info else None


def get_node_prompt(name: str) -> str | None:
    """生成适合直接拼入 LLM prompt 的节点描述文本。

    包含：节点类型、分类、输入输出数量、可配置属性（defaults）、UI 字段（template）。
    不包含冗余的 HTML 标签，让 token 更紧凑。

    :param name: 节点类型名或文件名，大小写不敏感。
    :return: 纯文本描述，找不到时返回 None。
    """
    info = get_node_info(name)
    if info is None:
        return None

    lines: list[str] = [
        f"## Node-RED 自定义节点：{info['node_type']}",
        f"- 分类：{info['category']}",
        f"- 输入端口数：{info['inputs']}",
        f"- 输出端口数：{info['outputs']}",
    ]

    if info["output_labels"]:
        lines.append(f"- 输出标签：{', '.join(info['output_labels'])}")
    if info["input_labels"]:
        lines.append(f"- 输入标签：{', '.join(info['input_labels'])}")

    if info["defaults"]:
        lines.append("\n### 可配置属性（defaults）")
        for k, v in info["defaults"].items():
            lines.append(f"  - {k}: 默认值={v!r}")

    if info["help_text"]:
        lines.append(f"\n### 节点说明\n{info['help_text']}")

    if info["template_html"]:
        lines.append(
            f"\n### 编辑器 UI 模板（HTML）\n```html\n{info['template_html']}\n```"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    print(list_node_names())