"""Parse Alteryx workflow files (.yxmd / .yxmc) into plain Python data.

Usage:
    python src/parser.py <workflow>               tools and connections (summary)
    python src/parser.py <workflow> --config      every tool's settings in detail
    python src/parser.py <workflow> --raw <ID>    one tool's raw XML settings
    python src/parser.py <workflow or folder> --save
                                                  write JSON to outputs/parsed/
"""
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import parse as safe_parse

# Tools that build a macro's interface; they hold no data logic to migrate.
INTERFACE_TOOLS = {"Tab", "ControlParam", "Action", "MacroInput", "MacroOutput",
                   "TextBox", "DropDown", "CheckBox", "ListBox", "NumericUpDown"}


def load_workflow(path):
    """Read a workflow file and return the top of its XML tree."""
    # defusedxml: safe against XML tricks a malicious file could contain
    return safe_parse(path, forbid_dtd=True).getroot()


# ---------- small helpers ----------

def _text(parent, path):
    """Text inside the element at `path`, or None."""
    el = parent.find(path)
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


def _attr(parent, path, name):
    """Attribute `name` of the element at `path`, or None."""
    el = parent.find(path)
    return el.get(name) if el is not None else None


def _leaf_values(cfg, limit=40):
    """Fallback for tool types we don't know yet: every setting as 'path = value'."""
    found = []

    def walk(el, path):
        for key, val in el.attrib.items():
            found.append(f"{path}@{key} = {val}")
        if el.text and el.text.strip():
            found.append(f"{path} = {el.text.strip()[:200]}")
        for child in el:
            walk(child, f"{path}/{child.tag}")

    for child in cfg:
        walk(child, child.tag)
    return found[:limit]


# ---------- settings per tool type ----------

def get_config(node, tool_type):
    """Return the settings that hold a tool's logic, in a readable form."""
    cfg = node.find("Properties/Configuration")
    if tool_type in INTERFACE_TOOLS:
        return {"interface_tool": True}
    if cfg is None:
        return {}

    if tool_type in ("DbFileInput", "DbFileOutput"):
        return {"file": _text(cfg, "File")}

    if tool_type == "Filter":
        return {
            "mode": _text(cfg, "Mode"),
            "expression": _text(cfg, "Expression"),
            "simple": {
                "field": _text(cfg, "Simple/Field"),
                "operator": _text(cfg, "Simple/Operator"),
                "value": _text(cfg, "Simple/Operands/Operand"),
            },
        }

    if tool_type == "Formula":
        return {"formulas": [
            {"field": f.get("field"), "type": f.get("type"), "expression": f.get("expression")}
            for f in cfg.findall("FormulaFields/FormulaField")
        ]}

    if tool_type == "MultiRowFormula":
        return {
            "new_field": _text(cfg, "CreateField_Name"),
            "expression": _text(cfg, "Expression"),
            "group_by": [f.get("field") for f in cfg.findall("GroupByFields/Field")],
            "rows_that_dont_exist": _text(cfg, "OtherRows"),
        }

    if tool_type == "AlteryxSelect":
        fields = cfg.findall("SelectFields/SelectField")
        return {
            "deselected": [f.get("field") for f in fields if f.get("selected") == "False"],
            "renamed": {f.get("field"): f.get("rename") for f in fields if f.get("rename")},
            "type_changes": {f.get("field"): f.get("type") for f in fields if f.get("type")},
        }

    if tool_type == "Join":
        keys = {}
        for info in cfg.findall("JoinInfo"):
            keys[info.get("connection", "?").lower()] = [f.get("field") for f in info.findall("Field")]
        return {"join_keys": keys}

    if tool_type == "Union":
        return {"mode": _text(cfg, "Mode")}

    if tool_type == "Unique":
        return {"unique_on": [f.get("field") for f in cfg.findall("UniqueFields/Field")]}

    if tool_type == "Summarize":
        return {"actions": [
            {"field": f.get("field"), "action": f.get("action"), "rename": f.get("rename")}
            for f in cfg.findall("SummarizeFields/SummarizeField")
        ]}

    if tool_type == "Sort":
        return {"sort_by": [
            {"field": f.get("field"), "order": f.get("order")}
            for f in cfg.findall("SortInfo/Field")
        ]}

    if tool_type == "RegEx":
        # Alteryx spells this tag "CaseInsensitve" in its files; accept both spellings.
        case = _attr(cfg, "CaseInsensitve", "value") or _attr(cfg, "CaseInsensitive", "value")
        return {
            "field": _text(cfg, "Field"),
            "expression": _attr(cfg, "RegExExpression", "value"),
            "method": _text(cfg, "Method"),
            "case_insensitive": case,
        }

    if tool_type == "JupyterCode":
        return {"python_code": _python_code(cfg)}

    if tool_type == "Macro":
        return {"macro_settings": {v.get("name"): (v.text or "").strip() for v in cfg.findall("Value")}}

    # Unknown tool type: keep everything so nothing is silently lost.
    return {"unrecognized_settings": _leaf_values(cfg)}


def _python_code(cfg):
    """Pull the code cells out of the Python tool's embedded Jupyter notebook."""
    for el in cfg.iter():
        if el.tag.lower() == "notebook" and el.text:
            try:
                notebook = json.loads(el.text)
            except json.JSONDecodeError:
                return el.text.strip()[:2000]
            cells = [c for c in notebook.get("cells", []) if c.get("cell_type") == "code"]
            return "\n\n".join("".join(c.get("source", [])) for c in cells)
    return None


# ---------- tools ----------

def get_tools(root):
    """Return one dictionary per tool: ID, type, plugin, macro file, position, and settings."""
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
            "config": get_config(node, tool_type),
        })
    return tools


# ---------- connections ----------

def get_connections(root):
    """Return one dictionary per connection: which tool and anchor it leaves, and where it arrives."""
    connections = []
    for conn in root.findall("./Connections/Connection"):
        origin = conn.find("Origin")
        dest = conn.find("Destination")
        if origin is None or dest is None:
            continue
        connections.append({
            "from_tool": origin.get("ToolID"),
            "from_anchor": origin.get("Connection"),   # e.g. Output, True, False, Join, Left, Right
            "to_tool": dest.get("ToolID"),
            "to_anchor": dest.get("Connection"),       # e.g. Input, Left, Right, Question
            "wireless": conn.get("Wireless") == "True",  # hidden connections on the canvas
            "name": conn.get("name"),                  # e.g. "#1", used by Python and multi-input tools
        })
    return connections


# ---------- comments ----------

def get_comments(root):
    """Text a developer wrote on the canvas: Comment tools and custom tool labels."""
    comments = []
    for node in root.iter("Node"):
        gui = node.find("GuiSettings")
        plugin = gui.get("Plugin", "") if gui is not None else ""
        if plugin.endswith("TextBox"):
            text = _text(node, "Properties/Configuration/Text")
            if text:
                comments.append({"tool_id": node.get("ToolID"), "kind": "comment", "text": text})
            continue
        # Interface tools carry their own names as labels (e.g. "Input"); not developer comments
        if plugin.split(".")[-1] in INTERFACE_TOOLS:
            continue
        # A label typed by the developer, as opposed to Alteryx's automatic one
        label = _text(node, "Properties/Annotation/AnnotationText")
        if label:
            comments.append({"tool_id": node.get("ToolID"), "kind": "tool_label", "text": label})
    return comments


# ---------- whole workflow ----------

def parse_workflow(path):
    """Everything the analyzer needs from one workflow file, in one dictionary."""
    path = Path(path)
    root = load_workflow(path)
    tools = get_tools(root)
    return {
        "file_name": path.name,
        "file_kind": "macro" if path.suffix.lower() == ".yxmc" else "workflow",
        "alteryx_version": root.get("yxmdVer"),
        "tool_count": sum(1 for t in tools if not t["config"].get("interface_tool")),
        "interface_tool_count": sum(1 for t in tools if t["config"].get("interface_tool")),
        "macros_used": [{"tool_id": t["tool_id"], "file": t["macro"]} for t in tools if t["macro"]],
        "tools": tools,
        "connections": get_connections(root),
        "comments": get_comments(root),
    }


def save_json(path, out_dir="outputs/parsed"):
    """Parse one workflow and write it to <out_dir>/<name>.json."""
    result = parse_workflow(path)
    out = Path(out_dir) / (Path(path).stem + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return out, result


def raw_config(root, tool_id):
    """The untouched XML settings of one tool, for checking what the parser misses."""
    for node in root.iter("Node"):
        if node.get("ToolID") == str(tool_id):
            cfg = node.find("Properties/Configuration")
            return ET.tostring(cfg, encoding="unicode") if cfg is not None else "(no settings)"
    return f"(no tool with ID {tool_id})"


if __name__ == "__main__":
    target = Path(sys.argv[1])
    args = sys.argv[2:]

    if args == ["--save"]:
        files = sorted(target.iterdir()) if target.is_dir() else [target]
        files = [f for f in files if f.suffix.lower() in (".yxmd", ".yxmc")]
        for f in files:
            out, r = save_json(f)
            print(f"{f.name}: {r['tool_count']} tools, {r['interface_tool_count']} interface tools, "
                  f"{len(r['connections'])} connections, {len(r['comments'])} comments -> {out}")
        sys.exit()

    root = load_workflow(target)

    if len(args) == 2 and args[0] == "--raw":
        print(raw_config(root, args[1]))
        sys.exit()

    tools = get_tools(root)
    if args == ["--config"]:
        for tool in tools:
            print(f"--- Tool {tool['tool_id']}: {tool['type']}")
            print(json.dumps(tool["config"], indent=2))
        print(f"{len(tools)} tools found")
        sys.exit()

    names = {t["tool_id"]: t["type"] for t in tools}
    print("TOOLS")
    for t in tools:
        print(f"  {t['tool_id']:>3}  {t['type']}")
    connections = get_connections(root)
    print("CONNECTIONS")
    for c in connections:
        hidden = "  (wireless)" if c["wireless"] else ""
        print(f"  {c['from_tool']:>3} {names.get(c['from_tool'], '?')} [{c['from_anchor']}]"
              f"  ->  {c['to_tool']} {names.get(c['to_tool'], '?')} [{c['to_anchor']}]{hidden}")
    comments = get_comments(root)
    if comments:
        print("COMMENTS")
        for c in comments:
            print(f"  {c['tool_id']:>3} ({c['kind']}): {c['text']}")
    print(f"{len(tools)} tools, {len(connections)} connections, {len(comments)} comments")