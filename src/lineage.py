"""Draw each workflow's data flow as a Mermaid flowchart (lineage diagram).

Reads parsed workflows (from parser.py) and tool names and difficulty from
rules/tool_rules.yaml, so the diagram is colored by migration difficulty.

Usage:
    python src/lineage.py outputs/parsed               every parsed file
    python src/lineage.py outputs/parsed/<file>.json   one file
    add --save to write diagrams to outputs/lineage/
"""
import json
import sys
from pathlib import Path

import yaml

RULES_FILE = Path("rules/tool_rules.yaml")

# Anchor names that tell the reader something, translated to plain words.
FROM_ANCHOR_LABELS = {"True": "true", "False": "false", "Join": "matched",
                      "Left": "unmatched left", "Right": "unmatched right",
                      "Unique": "unique", "Duplicates": "duplicates"}
TO_ANCHOR_LABELS = {"Left": "left", "Right": "right", "Control": "control", "Action": "sets value"}
# Readable names for macro interface tools (they have no scoring rule)
INTERFACE_NAMES = {"MacroInput": "Macro Input", "MacroOutput": "Macro Output",
                   "ControlParam": "Control Parameter", "Action": "Action"}

# Colors per difficulty: soft fills that read well in light and dark themes.
STYLES = {
    "high": "fill:#f8d7da,stroke:#b02a37,color:#3d0a10",
    "medium": "fill:#fff3cd,stroke:#b8860b,color:#3d2e00",
    "low": "fill:#d1e7dd,stroke:#2e7d4f,color:#0b2e1c",
    "none": "fill:#e9ecef,stroke:#6c757d,color:#212529",
}


def _short(text, limit=40):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _safe(text):
    """Make text safe inside a Mermaid label."""
    return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def tool_detail(tool):
    """One short line describing what the tool does, from its settings."""
    cfg, t = tool["config"], tool["type"]
    if t in ("DbFileInput", "DbFileOutput") and cfg.get("file"):
        return Path(cfg["file"].replace("\\", "/")).name
    if t == "Filter":
        if cfg.get("expression"):
            return cfg["expression"]
        s = cfg.get("simple") or {}
        return f"{s.get('field')} {s.get('operator')} {s.get('value')}"
    if t == "Formula":
        return "new: " + ", ".join(f["field"] for f in cfg.get("formulas", []))
    if t == "MultiRowFormula":
        return f"new: {cfg.get('new_field')} by {', '.join(cfg.get('group_by', []))}"
    if t == "AlteryxSelect":
        renames = [f"{a} as {b}" for a, b in cfg.get("renamed", {}).items()]
        dropped = len(cfg.get("deselected", []))
        parts = renames + ([f"drop {dropped}"] if dropped else [])
        return ", ".join(parts) or "select fields"
    if t == "Join":
        return "on " + ", ".join(cfg.get("join_keys", {}).get("left", []))
    if t == "Summarize":
        groups = [a["field"] for a in cfg.get("actions", []) if a.get("action") == "GroupBy"]
        aggs = [f"{a['action']} {a['field']}" for a in cfg.get("actions", []) if a.get("action") != "GroupBy"]
        parts = (["by " + ", ".join(groups)] if groups else []) + aggs
        return "; ".join(parts) or "totals"
    if t == "Sort":
        return "by " + ", ".join(s["field"] for s in cfg.get("sort_by", []))
    if t == "Unique":
        return "on " + ", ".join(cfg.get("unique_on", []))
    if t == "Union":
        return f"mode: {cfg.get('mode')}"
    if t == "RegEx":
        return f"parse {cfg.get('field')}"
    if t == "JupyterCode":
        return "Python code"
    if t == "Macro":
        return tool.get("macro") or "macro"
    return ""


def to_mermaid(parsed, rules):
    tool_rules = rules["tools"]
    connected = {c["from_tool"] for c in parsed["connections"]} | {c["to_tool"] for c in parsed["connections"]}
    lines = ["flowchart LR"]
    classes = {level: [] for level in STYLES}

    for tool in parsed["tools"]:
        tid = tool["tool_id"]
        interface = tool["config"].get("interface_tool")
        if interface and tid not in connected:
            continue  # e.g. the macro's Tab tool: settings only, not part of the flow
        rule = tool_rules.get(tool["type"], {})
        name = rule.get("name") or INTERFACE_NAMES.get(tool["type"], tool["type"])
        level = "none" if interface else rule.get("difficulty", "medium")
        detail = tool_detail(tool)
        label = _safe(name) + (f"<br/>{_safe(_short(detail))}" if detail else "")
        shape = ('[("', '")]') if tool["type"] in ("DbFileInput", "DbFileOutput") else ('["', '"]')
        lines.append(f"    t{tid}{shape[0]}{label}{shape[1]}")
        classes[level].append(f"t{tid}")

    for c in parsed["connections"]:
        label = FROM_ANCHOR_LABELS.get(c["from_anchor"]) or TO_ANCHOR_LABELS.get(c["to_anchor"])
        # Dotted: hidden (wireless) links, and interface links that change settings rather than carry data
        settings_link = c["to_anchor"] in ("Action", "Question")
        arrow = "-.->" if c.get("wireless") or settings_link else "-->"
        if label:
            lines.append(f"    t{c['from_tool']} {arrow}|{label}| t{c['to_tool']}")
        else:
            lines.append(f"    t{c['from_tool']} {arrow} t{c['to_tool']}")

    for level, style in STYLES.items():
        lines.append(f"    classDef {level} {style}")
        if classes[level]:
            lines.append(f"    class {','.join(classes[level])} {level}")
    return "\n".join(lines)


if __name__ == "__main__":
    target = Path(sys.argv[1])
    save = "--save" in sys.argv[2:]
    with open(RULES_FILE, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    files = sorted(target.glob("*.json")) if target.is_dir() else [target]

    for f in files:
        parsed = json.loads(f.read_text(encoding="utf-8"))
        diagram = to_mermaid(parsed, rules)
        if save:
            out = Path("outputs/lineage") / (f.stem + ".md")
            out.parent.mkdir(parents=True, exist_ok=True)
            legend = ("Colors show migration difficulty: red = high, yellow = medium, "
                      "green = low, grey = nothing to migrate.")
            out.write_text(f"# Lineage: {parsed['file_name']}\n\n{legend}\n\n```mermaid\n{diagram}\n```\n",
                           encoding="utf-8")
            print(f"{parsed['file_name']} -> {out}")
        else:
            print(f"\n{parsed['file_name']}\n{diagram}")