"""Find Alteryx logic that doesn't translate cleanly to Redshift ("gotchas").

Reads parsed workflows (from parser.py) and the checks in rules/formula_gotchas.yaml.

Usage:
    python src/gotchas.py outputs/parsed               check every parsed file
    python src/gotchas.py outputs/parsed/<file>.json   check one file
    add --save to write results to outputs/gotchas/
"""
import json
import re
import sys
from pathlib import Path

import yaml

RULES_FILE = Path("rules/formula_gotchas.yaml")
INTEGER_TYPES = {"Byte", "Int16", "Int32", "Int64"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def load_rules(path=RULES_FILE):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_expressions(parsed):
    """Every piece of formula text in the workflow, with where it came from."""
    found = []
    for tool in parsed["tools"]:
        cfg = tool["config"]
        if tool["type"] == "Formula":
            for f in cfg.get("formulas", []):
                found.append({"tool_id": tool["tool_id"], "tool": "Formula",
                              "field": f.get("field"), "text": f.get("expression") or ""})
        elif tool["type"] == "Filter" and cfg.get("expression"):
            found.append({"tool_id": tool["tool_id"], "tool": "Filter",
                          "field": None, "text": cfg["expression"]})
        elif tool["type"] == "MultiRowFormula" and cfg.get("expression"):
            found.append({"tool_id": tool["tool_id"], "tool": "Multi-Row Formula",
                          "field": cfg.get("new_field"), "text": cfg["expression"]})
    return found


def _finding(check_id, rule, tool_id, where, evidence):
    return {"check": check_id, "severity": rule["severity"], "tool_id": tool_id,
            "where": where, "evidence": evidence,
            "message": rule["message"], "redshift": rule["redshift"]}


def formula_findings(parsed, rules):
    findings = []
    for expr in collect_expressions(parsed):
        text = expr["text"]
        where = f"{expr['tool']} (tool {expr['tool_id']})" + (f", field {expr['field']}" if expr["field"] else "")
        for check_id, rule in rules["formula_checks"].items():
            matches = re.findall(rule["pattern"], text, flags=re.IGNORECASE)
            if len(matches) >= rule.get("min_count", 1):
                evidence = " ".join(text.split())  # one line, extra spaces removed
                findings.append(_finding(check_id, rule, expr["tool_id"], where, evidence[:300]))
    return findings


def _python_logic(code):
    """Python lines that do real work, skipping comments and Alteryx's template lines."""
    keep = []
    for line in (code or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s == "from ayx import Package":
            continue
        keep.append(s)
    return keep


def structure_findings(parsed, rules):
    checks = rules["structure_checks"]
    tools = {t["tool_id"]: t for t in parsed["tools"]}
    findings = []

    # Field types created by Formula tools, so we know which fields hold whole numbers
    field_types = {}
    for t in parsed["tools"]:
        if t["type"] == "Formula":
            for f in t["config"].get("formulas", []):
                field_types[f.get("field")] = f.get("type")

    for t in parsed["tools"]:
        cfg, tid = t["config"], t["tool_id"]
        where = f"{t['type']} (tool {tid})"

        if t["type"] == "DbFileInput" and (cfg.get("file") or "").lower().endswith(".csv"):
            findings.append(_finding("csv_input", checks["csv_input"], tid, where,
                                     Path(cfg["file"].replace("\\", "/")).name))

        if t["type"] == "Union" and cfg.get("mode") == "ByName":
            findings.append(_finding("union_by_name", checks["union_by_name"], tid, where, "Mode: ByName"))

        if t["type"] == "Unique":
            findings.append(_finding("unique_keep_first", checks["unique_keep_first"], tid, where,
                                     "Unique on: " + ", ".join(cfg.get("unique_on", []))))

        if t["type"] == "Summarize":
            for a in cfg.get("actions", []):
                if a.get("action") == "Avg" and field_types.get(a.get("field")) in INTEGER_TYPES:
                    findings.append(_finding("avg_of_integer", checks["avg_of_integer"], tid, where,
                                             f"Avg of {a['field']} ({field_types[a['field']]})"))

        if t["type"] == "RegEx":
            pattern = cfg.get("expression") or ""
            findings.append(_finding("regex_tool", checks["regex_tool"], tid, where, pattern))
            if cfg.get("case_insensitive") == "True":
                findings.append(_finding("regex_case_insensitive", checks["regex_case_insensitive"],
                                         tid, where, "Case insensitive: True"))
            if "Parse" in (cfg.get("method") or "") and "(" in pattern:
                findings.append(_finding("regex_parse_group", checks["regex_parse_group"], tid, where,
                                         f"Method: {cfg.get('method')}"))

        if t["type"] == "JupyterCode":
            logic = _python_logic(cfg.get("python_code"))
            findings.append(_finding("python_tool", checks["python_tool"], tid, where, " | ".join(logic)[:300]))

        if t["type"] == "Macro":
            findings.append(_finding("macro_dependency", checks["macro_dependency"], tid, where,
                                     t.get("macro") or "unknown macro file"))

    for c in parsed["connections"]:
        src = tools.get(c["from_tool"], {})
        dst = tools.get(c["to_tool"], {})
        if src.get("type") == "Join" and c["from_anchor"] in ("Left", "Right"):
            findings.append(_finding("join_unmatched_used", checks["join_unmatched_used"], c["from_tool"],
                                     f"Join (tool {c['from_tool']})", f"Unmatched {c['from_anchor']} output used"))
        if src.get("type") == "AlteryxSelect" and dst.get("type") == "Union" and src["config"].get("renamed"):
            renames = ", ".join(f"{a} -> {b}" for a, b in src["config"]["renamed"].items())
            findings.append(_finding("rename_before_union", checks["rename_before_union"], c["from_tool"],
                                     f"Select (tool {c['from_tool']})", renames))
    return findings


def check_workflow(parsed, rules):
    findings = formula_findings(parsed, rules) + structure_findings(parsed, rules)
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["check"]))
    return {
        "file_name": parsed["file_name"],
        "counts": {s: sum(1 for f in findings if f["severity"] == s) for s in ("high", "medium", "low")},
        "findings": findings,
    }


if __name__ == "__main__":
    target = Path(sys.argv[1])
    save = "--save" in sys.argv[2:]
    rules = load_rules()
    files = sorted(target.glob("*.json")) if target.is_dir() else [target]

    for f in files:
        result = check_workflow(json.loads(f.read_text(encoding="utf-8")), rules)
        c = result["counts"]
        print(f"\n{result['file_name']}: {len(result['findings'])} gotchas "
              f"(high {c['high']}, medium {c['medium']}, low {c['low']})")
        for g in result["findings"]:
            print(f"  [{g['severity'].upper():6}] {g['check']:<26} {g['where']}")
        if save:
            out = Path("outputs/gotchas") / f.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")