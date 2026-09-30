"""Score parsed Alteryx workflows for Redshift migration difficulty.

Reads the JSON made by parser.py and the rules in rules/tool_rules.yaml.

Usage:
    python src/score.py outputs/parsed               score every parsed file
    python src/score.py outputs/parsed/<file>.json   score one file
    add --save to write results to outputs/scores/
"""
import json
import sys
from pathlib import Path

import yaml

RULES_FILE = Path("rules/tool_rules.yaml")


def load_rules(path=RULES_FILE):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def score_tool(tool, rules):
    """Points, difficulty, and advice for one tool."""
    if tool["config"].get("interface_tool"):
        return {"tool_id": tool["tool_id"], "type": tool["type"], "name": tool["type"],
                "difficulty": "none", "points": rules["interface_points"], "interface": True}
    rule = rules["tools"].get(tool["type"])
    known = rule is not None
    if not known:
        rule = rules["unknown_tool"]
    return {
        "tool_id": tool["tool_id"],
        "type": tool["type"],
        "name": rule.get("name", tool["type"]),
        "difficulty": rule["difficulty"],
        "points": rule["points"],
        "redshift": rule.get("redshift"),
        "note": rule.get("note"),
        "known": known,
    }


def find_modifiers(parsed, rules):
    """Structural features that add work beyond the tools themselves."""
    mods = rules["modifiers"]
    tool_types = {t["tool_id"]: t["type"] for t in parsed["tools"]}
    found = []

    outputs = [t for t in parsed["tools"] if t["type"] == "DbFileOutput"]
    for _ in outputs[1:]:
        found.append({"modifier": "extra_output", **mods["extra_output"]})

    for c in parsed["connections"]:
        # A Join sends unmatched records out through its "Left" or "Right" anchor
        if tool_types.get(c["from_tool"]) == "Join" and c["from_anchor"] in ("Left", "Right"):
            found.append({"modifier": "unmatched_join_output", "tool_id": c["from_tool"],
                          **mods["unmatched_join_output"]})
        if c.get("wireless"):
            found.append({"modifier": "wireless_connection", **mods["wireless_connection"]})
    return found


def points_to_score(points, bands):
    """Highest score whose minimum points the workflow reaches."""
    return max(score for score, minimum in bands.items() if points >= minimum)


def score_workflow(parsed, rules):
    tools = [score_tool(t, rules) for t in parsed["tools"]]
    modifiers = find_modifiers(parsed, rules)
    total = sum(t["points"] for t in tools) + sum(m["points"] for m in modifiers)
    drivers = sorted((t for t in tools if t["points"] > 0), key=lambda t: -t["points"])
    return {
        "file_name": parsed["file_name"],
        "file_kind": parsed["file_kind"],
        "score": points_to_score(total, rules["score_bands"]),
        "total_points": total,
        "difficulty_counts": {level: sum(1 for t in tools if t["difficulty"] == level)
                              for level in ("high", "medium", "low", "none")},
        "unknown_tools": [t["type"] for t in tools if t.get("known") is False],
        "top_drivers": [f"{t['name']} ({t['difficulty']}, {t['points']} pts)" for t in drivers[:5]],
        "tools": tools,
        "modifiers": modifiers,
    }


if __name__ == "__main__":
    target = Path(sys.argv[1])
    save = "--save" in sys.argv[2:]
    rules = load_rules()
    files = sorted(target.glob("*.json")) if target.is_dir() else [target]

    for f in files:
        result = score_workflow(json.loads(f.read_text(encoding="utf-8")), rules)
        counts = result["difficulty_counts"]
        print(f"{result['file_name']}: score {result['score']}/10 "
              f"({result['total_points']} pts; high {counts['high']}, medium {counts['medium']}, "
              f"low {counts['low']}; {len(result['modifiers'])} modifiers)")
        print(f"    drivers: {', '.join(result['top_drivers'])}")
        if result["unknown_tools"]:
            print(f"    UNKNOWN tools, review: {', '.join(result['unknown_tools'])}")
        if save:
            out = Path("outputs/scores") / f.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")