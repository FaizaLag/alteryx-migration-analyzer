"""Parse Alteryx workflow files (.yxmd / .yxmc) into plain Python data.

Usage: python src/parser.py <path-to-workflow>
"""
import sys
import xml.etree.ElementTree as ET


def load_workflow(path):
    """Read a workflow file and return the top of its XML tree."""
    return ET.parse(path).getroot()


def get_tools(root):
    """Return one dictionary per tool: its ID, type, plugin name, macro file, and position."""
    tools = []
    # iter() finds every <Node>, including tools nested inside containers
    for node in root.iter("Node"):
        gui = node.find("GuiSettings")
        engine = node.find("EngineSettings")

        plugin = gui.get("Plugin", "") if gui is not None else ""
        macro = engine.get("Macro") if engine is not None else None

        # Tool type = last part of the plugin name, e.g. "...Filter.Filter" -> "Filter".
        # Macro tools have no plugin name; they point to a macro file instead.
        if plugin:
            tool_type = plugin.split(".")[-1]
        elif macro:
            tool_type = "Macro"
        else:
            tool_type = "Unknown"

        pos = gui.find("Position") if gui is not None else None
        position = None
        if pos is not None:
            position = {"x": float(pos.get("x", 0)), "y": float(pos.get("y", 0))}

        tools.append({
            "tool_id": node.get("ToolID"),
            "type": tool_type,
            "plugin": plugin or None,
            "macro": macro,
            "position": position,
        })
    return tools


if __name__ == "__main__":
    root = load_workflow(sys.argv[1])
    tools = get_tools(root)
    for tool in tools:
        print(tool)
    print(f"{len(tools)} tools found")