#!/usr/bin/env python3
"""Parse a package's QUERIES.md, SETUP.md and TESTS.md into the units test mode works on.

check_annotations.py checks ONTOLOGY.json against the CSVs and parses no Markdown, so this is the one
parser for the @-annotation blocks (PACKAGE_FORMAT.md, VALIDATION.md section 5). Used by run_queries.py
and probe_cypherlite.py.

Usage: python3 annotations.py <package-dir>   (prints what it parsed). Standard library only."""
import json, re, sys, pathlib

FENCE = re.compile(r"^```cypher[^\n]*\n(.*?)^```", re.S | re.M)
TAG = re.compile(r"^@(\w+)\s*(.*)$")
PARAM_LINE = re.compile(r"^\$?([A-Za-z_]\w*)\s*(?:-|–|—|:)\s*(.*)$")


def sections(text):
    """Split Markdown into (heading, body, line) on level-2 headings; text before the first is ''."""
    out, cur, body, start = [], "", [], 1
    for i, line in enumerate(text.splitlines(keepends=True), 1):
        if line.startswith("## "):
            out.append((cur, "".join(body), start))
            cur, body, start = line[3:].strip(), [], i
        else:
            body.append(line)
    out.append((cur, "".join(body), start))
    return out


def split_comment(block):
    """Return (annotation text, cypher after it) when the block opens with a /* ... */ comment."""
    s = block.lstrip()
    if not s.startswith("/*") or "*/" not in s:
        return None, block
    end = s.index("*/")
    return s[2:end], s[end + 2:]


def parse_annotations(comment):
    """Map each @tag to its text. @params also keeps its raw lines so the one-line-per-parameter rule
    can be applied: a line starting at the value column is a new parameter, deeper lines continue it."""
    tags, raw, cur = {}, {}, None
    for line in comment.splitlines():
        body = re.sub(r"^\s*\*?", "", line, count=1)
        stripped = body.strip()
        m = TAG.match(stripped)
        if m:
            cur = m.group(1)
            col = len(body) - len(body.lstrip()) + len(stripped) - len(m.group(2)) if m.group(2) else None
            tags[cur] = m.group(2).strip()
            raw[cur] = [(col, m.group(2))]
        elif cur and stripped:
            tags[cur] += " " + stripped
            raw[cur].append((len(body) - len(body.lstrip()), stripped))
    return tags, raw


def parse_params(raw_lines):
    """Turn @params raw lines into {name: description}; returns {} for 'None'."""
    if not raw_lines or raw_lines[0][1].strip().lower().startswith("none"):
        return {}
    first_col = raw_lines[0][0]
    params, name = {}, None
    for col, text in raw_lines:
        m = PARAM_LINE.match(text.strip())
        if m and (col is None or first_col is None or col <= first_col):
            name = m.group(1)
            params[name] = m.group(2).strip()
        elif name:
            params[name] += " " + text.strip()
    return params


def strip_cypher_noise(cypher):
    """Remove comments and string literals, for scanning Cypher for $parameters and constructs."""
    out, i, n = [], 0, len(cypher)
    while i < n:
        c = cypher[i]
        if cypher.startswith("/*", i):
            j = cypher.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
        elif cypher.startswith("//", i):
            j = cypher.find("\n", i)
            i = n if j < 0 else j
        elif c in "'\"`":
            j = i + 1
            while j < n and cypher[j] != c:
                j += 2 if cypher[j] == "\\" else 1
            out.append(c + c if c != "`" else cypher[i:j + 1])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def cypher_params(cypher):
    return sorted(set(re.findall(r"\$([A-Za-z_]\w*)", strip_cypher_noise(cypher))))


def parse_statements(path):
    """Every ```cypher block in file order with its section heading. A block whose opening comment
    carries @name is an annotated statement; other blocks (the node-key reference list) are kept with
    annotated=False so callers can skip them."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    out = []
    for heading, body, start in sections(text):
        for m in FENCE.finditer(body):
            block = m.group(1)
            line = start + body[:m.start()].count("\n") + 1
            comment, cypher = split_comment(block)
            tags, raw = parse_annotations(comment) if comment else ({}, {})
            out.append({
                "heading": heading, "line": line, "block": block.strip(), "cypher": cypher.strip(),
                "annotated": "name" in tags, "tags": tags,
                "declared_params": parse_params(raw.get("params")),
                "params": cypher_params(cypher),
            })
    return out


def parse_tests(path):
    """TESTS.md sections keyed by heading, with the conventional fields pulled out where present
    (Parameters, Invariant, Expected, Sensitivity), in either **Field:** or table-row form."""
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    out = {}
    for heading, body, start in sections(path.read_text(encoding="utf-8")):
        if not heading:
            continue
        fields, cur = {}, None
        for line in body.splitlines():
            m = re.match(r"^\s*(?:[-*]\s*)?\*\*(Parameters|Invariant|Expected|Sensitivity)\*\*\s*:?\s*(.*)$", line) \
                or re.match(r"^\s*\|\s*\**(Parameters|Invariant|Expected|Sensitivity)\**\s*\|\s*(.*?)\s*\|?\s*$", line)
            if m:
                cur = m.group(1)
                fields[cur] = m.group(2).strip()
            elif re.match(r"^\s*(?:[-*]\s*)?\*\*\w[\w -]*\*\*\s*:?", line) or line.startswith("#"):
                cur = None
            elif cur and line.strip():
                fields[cur] += "\n" + line.rstrip()
        out[heading] = {"line": start, "body": body, "fields": fields}
    return out


if __name__ == "__main__":
    pkg = pathlib.Path(sys.argv[1])
    for name in ("SETUP.md", "QUERIES.md"):
        for s in parse_statements(pkg / name):
            print(json.dumps({"file": name, "heading": s["heading"], "annotated": s["annotated"],
                              "params": s["params"], "declared": list(s["declared_params"]),
                              "sample": s["tags"].get("sample", "")[:80]}))
    tests = parse_tests(pkg / "TESTS.md")
    print(json.dumps({h: sorted(t["fields"]) for h, t in tests.items()}, indent=1))
