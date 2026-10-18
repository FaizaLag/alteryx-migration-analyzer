
"""Ask Claude to explain a workflow's migration assessment in plain English.

Code extracts the facts (parser, score, gotchas); the AI only explains them.
Every tool ID the AI cites is checked against the facts afterwards.

Usage:
    python src/ai_summary.py <workflow-name> --dry-run   show the facts, no API call (free)
    python src/ai_summary.py <workflow-name>             call the API and print the result
    python src/ai_summary.py <workflow-name> --save      ...and save to outputs/ai/
    python src/ai_summary.py all --save                  every parsed workflow

<workflow-name> is the file name without extension, e.g. wf2_cases_by_member

Needs ANTHROPIC_API_KEY in a .env file (never committed).
"""
import json
import os
import re
import sys
from pathlib import Path

from lineage import tool_detail

PARSED, SCORES, GOTCHAS = Path("outputs/parsed"), Path("outputs/scores"), Path("outputs/gotchas")
PROMPT_FILE = Path("prompts/assessment.md")
DEFAULT_MODEL = "claude-sonnet-5"


def _load(folder, name):
    return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))


def build_facts(name):
    """Facts for a workflow already processed into the outputs/ folders."""
    return build_facts_from(_load(PARSED, name), _load(SCORES, name), _load(GOTCHAS, name))


def build_facts_from(parsed, score, gotchas):
    """The compact, privacy-safe package of facts the AI is allowed to use."""

    details = {t["tool_id"]: tool_detail(t) for t in parsed["tools"]}
    tools = []
    for t in score["tools"]:
        if t.get("interface"):
            continue
        tools.append({"id": t["tool_id"], "tool": t["name"], "does": details.get(t["tool_id"], ""),
                      "difficulty": t["difficulty"], "redshift_equivalent": t.get("redshift")})

    # Group repeated gotchas: one entry per check, listing every tool it applies to
    grouped = {}
    for g in gotchas["findings"]:
        entry = grouped.setdefault(g["check"], {
            "check": g["check"], "severity": g["severity"], "message": g["message"],
            "redshift_advice": g["redshift"], "tools": [], "evidence": []})
        if g["tool_id"] not in entry["tools"]:
            entry["tools"].append(g["tool_id"])
        if g["evidence"] not in entry["evidence"] and len(entry["evidence"]) < 3:
            entry["evidence"].append(g["evidence"])

    return {
        "workflow": parsed["file_name"],
        "kind": parsed["file_kind"],
        "difficulty_score": f"{score['score']}/10",
        "score_scale": "1-2 direct translation; 3-4 a few rewrites; 5-6 design decisions needed; "
                       "7-8 some logic has no SQL equivalent; 9-10 major rework",
        "top_score_drivers": score["top_drivers"],
        "structural_factors": [m["note"] for m in score["modifiers"]],
        "tools": tools,
        "data_flow": [f"{c['from_tool']} -> {c['to_tool']}" for c in parsed["connections"]],
        "macros_used": [m["file"] for m in parsed.get("macros_used", [])],
        "gotchas": list(grouped.values()),
        "developer_comments": [c["text"] for c in parsed.get("comments", [])],
    }


def parse_reply(text):
    """Read the AI's JSON, tolerating stray code fences."""
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(clean)


def check_citations(result, facts):
    """Every tool ID the AI cites must exist in the facts; anything else is flagged."""
    valid = {t["id"] for t in facts["tools"]}
    cited = set()
    for part in result.get("key_components", []) + result.get("risks", []):
        cited.update(str(i) for i in part.get("tools", []))
    for text in [result.get("summary", "")] + [r.get("detail", "") for r in result.get("risks", [])] \
            + result.get("next_steps", []):
        cited.update(re.findall(r"\[(\d+)\]", text))
    return sorted(cited - valid, key=int)


def ask_claude(facts, model):
    from anthropic import Anthropic
    from dotenv import load_dotenv

    load_dotenv()
    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    message = client.messages.create(
        model=model,
        max_tokens=4000,
        system=PROMPT_FILE.read_text(encoding="utf-8"),
        messages=[{"role": "user", "content": "FACTS:\n" + json.dumps(facts, indent=2)}],
    )
    if message.stop_reason == "max_tokens":
        print("  warning: the reply was cut off (max_tokens reached)")
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}
    return text, usage


if __name__ == "__main__":
    name = sys.argv[1]
    flags = sys.argv[2:]
    names = sorted(p.stem for p in PARSED.glob("*.json")) if name == "all" else [name]

    from dotenv import load_dotenv
    load_dotenv()
    model = os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)

    for n in names:
        facts = build_facts(n)
        if "--dry-run" in flags:
            print(json.dumps(facts, indent=2))
            continue

        print(f"\n{facts['workflow']} (model {model})")
        text, usage = ask_claude(facts, model)
        try:
            result = parse_reply(text)
        except json.JSONDecodeError:
            print("  The reply was not valid JSON. Raw reply:\n" + text)
            continue

        unknown = check_citations(result, facts)
        result["_check"] = {"model": model, "usage": usage, "uncited_or_invented_tool_ids": unknown}
        print(json.dumps(result, indent=2))
        print(f"  tokens: {usage['input_tokens']} in, {usage['output_tokens']} out")
        print("  citation check: " + ("OK, every cited tool exists" if not unknown
                                      else f"PROBLEM, cites tools not in the workflow: {unknown}"))
        if "--save" in flags:
            out = Path("outputs/ai") / f"{n}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")           