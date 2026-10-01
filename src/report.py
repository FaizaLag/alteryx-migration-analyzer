"""Build the client-facing report for each workflow, plus an overview page.

Combines parsed facts, score, gotchas, lineage diagram, and AI summary.
Writes, per workflow:
  outputs/reports/<name>.html   the report (open in a browser; needs internet for the diagram)
  outputs/reports/<name>.md     the same content in Markdown, which GitHub renders, diagram included
and outputs/reports/index.html + README.md as an overview of all workflows.

Usage:
    python src/report.py
"""
import json
import re
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from lineage import to_mermaid, tool_detail

OUT = Path("outputs/reports")
BANDS = {1: "Direct translation", 2: "Direct translation", 3: "A few rewrites", 4: "A few rewrites",
         5: "Design decisions needed", 6: "Design decisions needed",
         7: "Some logic has no SQL equivalent", 8: "Some logic has no SQL equivalent",
         9: "Major rework", 10: "Major rework"}


def _load(folder, name):
    path = Path("outputs") / folder / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def score_level(score):
    return "low" if score <= 4 else "medium" if score <= 6 else "high"


def group_gotchas(findings):
    grouped = {}
    for f in findings:
        g = grouped.setdefault(f["check"], {**f, "tools": [], "evidence": []})
        if f["tool_id"] not in g["tools"]:
            g["tools"].append(f["tool_id"])
        if f["evidence"] not in g["evidence"] and len(g["evidence"]) < 3:
            g["evidence"].append(f["evidence"])
    return list(grouped.values())


def build(name, rules, env):
    parsed, score, gotchas, ai = (_load("parsed", name), _load("scores", name),
                                  _load("gotchas", name), _load("ai", name))
    details = {t["tool_id"]: tool_detail(t) for t in parsed["tools"]}
    tools = [{**t, "does": details.get(t["tool_id"], "")} for t in score["tools"] if not t.get("interface")]
    names = {t["tool_id"]: t["name"] for t in tools}

    def ref_chip(tool_id):
        tid = str(tool_id)
        return Markup(f'<span class="ref" title="{escape(names.get(tid, "tool"))} (tool {tid})">{tid}</span>')

    def refs(text):
        """Escape the AI's text, then turn [6] into a small labeled chip."""
        safe = str(escape(text))
        return Markup(re.sub(r"\[(\d+)\]", lambda m: ref_chip(m.group(1)), safe))

    macros = [{"file": m["file"], "link": Path(m["file"]).stem + ".html"} for m in parsed.get("macros_used", [])]
    context = dict(
        w={"file_name": parsed["file_name"], "kind": parsed["file_kind"]},
        s=score, g=gotchas, ai=ai, tools=tools, tool_count=len(tools),
        band=BANDS[score["score"]], level=score_level(score["score"]),
        gotcha_groups=group_gotchas(gotchas["findings"]), macros=macros,
        # Long workflows read better top to bottom on screens and paper
        mermaid=to_mermaid(parsed, rules, "TB" if len(tools) > 10 else "LR"), generated=date.today().strftime("%B %d, %Y"),
        refs=refs, ref_chip=ref_chip,
    )
    html = env.get_template("report.html.j2").render(**context)
    md = to_markdown(context)
    return html, md, context


def to_markdown(c):
    """GitHub-friendly version of the report (renders on the GitHub website and app)."""
    s, ai = c["s"], c["ai"]
    lines = [f"# {c['w']['file_name']}", "",
             f"**Redshift migration difficulty: {s['score']}/10**, {c['band'].lower()}. "
             f"{c['tool_count']} tools, {len(c['g']['findings'])} migration gotchas.", ""]
    for m in c["macros"]:
        lines += [f"> Calls the macro [{m['file']}]({Path(m['file']).stem}.md), assessed in its own report.", ""]
    if ai:
        lines += ["## In short", "", ai["summary"], "",
                  f"*Written by AI ({ai['_check']['model']}) from facts extracted by code; every cited tool was checked.*", ""]
    lines += ["## How data flows", "", "```mermaid", c["mermaid"], "```", ""]
    if ai:
        lines += ["## Main risks", ""]
        for r in ai["risks"]:
            lines += [f"**{r['title']}** ({r['severity']})  ", r["detail"], ""]
        lines += ["## Next steps", ""] + [f"{i}. {step}" for i, step in enumerate(ai["next_steps"], 1)] + [""]
    lines += ["## Every gotcha found", "", "| Severity | Issue | Tools | What to do in Redshift |", "|---|---|---|---|"]
    for x in c["gotcha_groups"]:
        lines.append(f"| {x['severity']} | {x['message']} | {', '.join(x['tools'])} | {x['redshift']} |")
    return "\n".join(lines) + "\n"


def overview(rows, env):
    html = env.get_template("index.html.j2").render(rows=rows, generated=date.today().strftime("%B %d, %Y"))
    md = ["# Alteryx to Redshift: migration assessments", "",
          "| Workflow | Score | Tools | Gotchas | Main risk |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| [{r['file']}]({r['stem']}.md) | {r['score']}/10 | {r['tools']} | {r['gotchas']} | {r['top_risk']} |")
    return html, "\n".join(md) + "\n"


if __name__ == "__main__":
    with open("rules/tool_rules.yaml", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for p in sorted(Path("outputs/parsed").glob("*.json")):
        html, md, c = build(p.stem, rules, env)
        (OUT / f"{p.stem}.html").write_text(html, encoding="utf-8")
        (OUT / f"{p.stem}.md").write_text(md, encoding="utf-8")
        top = c["ai"]["risks"][0]["title"] if c["ai"] and c["ai"]["risks"] else "(no AI summary yet)"
        rows.append({"file": c["w"]["file_name"], "stem": p.stem, "score": c["s"]["score"],
                     "level": c["level"], "band": c["band"], "tools": c["tool_count"],
                     "gotchas": len(c["g"]["findings"]), "top_risk": top})
        print(f"{c['w']['file_name']}: {c['s']['score']}/10 -> {OUT / p.stem}.html and .md"
              + ("" if c["ai"] else "  (no AI summary yet)"))

    rows.sort(key=lambda r: -r["score"])
    html, md = overview(rows, env)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "README.md").write_text(md, encoding="utf-8")
    print(f"Overview -> {OUT / 'index.html'} and README.md")