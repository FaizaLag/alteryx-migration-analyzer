"""Run the whole analysis on one workflow held in memory (used by the app).

The command-line scripts write to outputs/ step by step; this does the same
work in one call, without writing files, so an uploaded workflow can flow
straight through.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from gotchas import check_workflow, load_rules as load_gotcha_rules
from lineage import to_mermaid
from parser import get_comments, get_connections, get_tools
from report import build_from
from score import load_rules as load_tool_rules, score_workflow

MAX_BYTES = 20 * 1024 * 1024  # 20 MB is far beyond any normal workflow file


class WorkflowError(ValueError):
    """The file can't be analyzed; the message is safe to show the user."""


def load_all_rules():
    return {"tools": load_tool_rules(), "gotchas": load_gotcha_rules(),
            "env": Environment(loader=FileSystemLoader("templates"), autoescape=True)}


def parse_bytes(data, file_name):
    """Same output as parser.parse_workflow, but from file contents in memory."""
    if len(data) > MAX_BYTES:
        raise WorkflowError("The file is larger than 20 MB, which is unusual for a workflow.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise WorkflowError("This file isn't valid XML, so it doesn't look like an Alteryx workflow.")
    if root.tag != "AlteryxDocument" or root.find("Nodes") is None:
        raise WorkflowError("This XML file isn't an Alteryx workflow (no AlteryxDocument with tools).")

    tools = get_tools(root)
    return {
        "file_name": file_name,
        "file_kind": "macro" if Path(file_name).suffix.lower() == ".yxmc" else "workflow",
        "alteryx_version": root.get("yxmdVer"),
        "tool_count": sum(1 for t in tools if not t["config"].get("interface_tool")),
        "interface_tool_count": sum(1 for t in tools if t["config"].get("interface_tool")),
        "macros_used": [{"tool_id": t["tool_id"], "file": t["macro"]} for t in tools if t["macro"]],
        "tools": tools,
        "connections": get_connections(root),
        "comments": get_comments(root),
    }


def analyze(data, file_name, rules):
    """Parse, score, check, and draw one workflow. No AI call (that's separate, on request)."""
    parsed = parse_bytes(data, file_name)
    score = score_workflow(parsed, rules["tools"])
    gotchas = check_workflow(parsed, rules["gotchas"])
    direction = "TB" if parsed["tool_count"] > 10 else "LR"
    return {"parsed": parsed, "score": score, "gotchas": gotchas,
            "mermaid": to_mermaid(parsed, rules["tools"], direction)}


def render_report(result, ai, rules):
    """Full HTML and Markdown report, with or without the AI summary."""
    html, md, _ = build_from(result["parsed"], result["score"], result["gotchas"], ai,
                             rules["tools"], rules["env"])
    return html, md
