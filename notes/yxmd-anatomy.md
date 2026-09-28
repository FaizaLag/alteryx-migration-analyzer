# Anatomy of an Alteryx .yxmd file

Notes from Step 2. Reference file: `samples/learning_sample.yxmd` (hand-written, simplified, made-up data).

## What a .yxmd file is

A .yxmd workflow is plain XML text. Information sits inside labeled tags that open and close (`<Node>` ... `</Node>`) and nest inside each other like folders. Any text editor can read it, which is what makes automated analysis possible.

## The three main sections

| Section | What it holds |
| --- | --- |
| `<Nodes>` | The tools. One `<Node>` per tool on the canvas. |
| `<Connections>` | The arrows between tools. |
| `<Properties>` (at the bottom) | Information about the workflow itself, such as its name and description. |

## Inside a tool (`<Node>`)

| Element | What it tells me |
| --- | --- |
| `ToolID="…"` | The tool's unique number. Connections refer to tools by this ID. |
| `<GuiSettings Plugin="…">` | The tool type. The end of the name gives it away, e.g. `…Filter.Filter`, `…Formula.Formula`. |
| `<Position x="…" y="…">` | Where the tool sits on the canvas. Useful for the lineage diagram (Step 7). |
| `<Configuration>` | The tool's settings: file names, filter rules, formulas. This is where the real logic lives. |
| `<Annotation>` | The label shown under the tool on the canvas. |
| `<EngineSettings>` | The engine component that runs the tool. Mostly ignorable. |

Where the logic sits for each tool type in the sample:

| Tool | Plugin name ends in | Logic found in |
| --- | --- | --- |
| Input | `DbFileInput.DbFileInput` | `<File>` (file name) |
| Formula | `Formula.Formula` | `<FormulaField>`: `field` = new column, `expression` = formula |
| Filter | `Filter.Filter` | `<Expression>` (the rule) and `<Mode>` |
| Output | `DbFileOutput.DbFileOutput` | `<File>` (file name) |

## Connections

Each `<Connection>` has an `<Origin>` and a `<Destination>`, each with a ToolID and a named anchor:

```xml
<Origin ToolID="3" Connection="True" />
<Destination ToolID="4" Connection="Input" />
```

- Most tools exit through `Output` and enter through `Input`.
- The Filter has two exits, `True` and `False`. Only connected exits appear here.
- Records leaving an unconnected exit are dropped without warning.

## Escaped characters

Inside XML attributes, some characters are written as codes:

| In the file | Means |
| --- | --- |
| `&gt;` | `>` |
| `&lt;` | `<` |
| `&quot;` | `"` |
| `&amp;` | `&` |

Python's XML library converts these back automatically.

## The sample workflow, read from the XML alone

1. **Input (ToolID 1)** reads `members.csv`.
2. **Formula (ToolID 2)** creates `AgeBand` = `IIF([Age] >= 65, "Senior", "Adult")` and `FollowUpDate` = `DateTimeAdd([EnrollDate], 30, "days")`.
3. **Filter (ToolID 3)** keeps `[Region] = "North"`. Only True is connected, so other regions are dropped.
4. **Output (ToolID 4)** writes `north_members.csv`.

## Translated to Redshift SQL

```sql
SELECT *,
       CASE WHEN age >= 65 THEN 'Senior' ELSE 'Adult' END AS age_band,
       DATEADD(day, 30, enroll_date) AS follow_up_date
FROM members
WHERE region = 'North';
```

## Key insight: "needs rewriting" is not the same as "hard"

| Alteryx | Redshift | Risk | Why |
| --- | --- | --- | --- |
| `IIF(...)` | `CASE WHEN ... END` | Low | Redshift has no `IIF`. A mechanical syntax swap. |
| `DateTimeAdd(date, n, "days")` | `DATEADD(day, n, date)` | Medium | Argument order is flipped. The real risk is the data type: if the date came from a CSV as text, it needs converting first. |
| Filter | `WHERE` | Low | Direct equivalent. |
| CSV input | Load to a table first (usually `COPY` from S3) | Medium | Files don't exist in Redshift; a loading step is needed. |
| CSV output | `UNLOAD` to S3, or create a table | Medium | Where the output goes has to be redesigned. |

Scoring (Step 5) and gotcha checks (Step 6) should treat syntax swaps as cheap and behavior or type differences as risky.

## What this means for the parser (Step 4)

The parser needs to pull, for every tool: ToolID, tool type (from `Plugin`), position, and the key settings in `<Configuration>`. For every connection: origin ToolID and anchor, destination ToolID and anchor.

## Caveat

The sample is simplified. Files saved from real Alteryx share this skeleton but contain much more (field lists in `<MetaInfo>`, layout and runtime settings). To confirm in Step 3: compare against a real saved file.