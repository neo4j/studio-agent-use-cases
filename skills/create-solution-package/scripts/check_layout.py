#!/usr/bin/env python3
"""Check that a package's ONTOLOGY.json node layout is compact enough to read (VALIDATION.md section 3b).

Usage: python3 check_layout.py <package-dir>                  check, print metrics and findings
       python3 check_layout.py <package-dir> --rescale [N]    create mode only: scale every node's
                                                              extensions.display about the origin so the
                                                              median edge is N (default 130), round to
                                                              multiples of 5, rewrite ONTOLOGY.json in place

Import fits the whole reference ontology to the screen, and node labels are drawn at a fixed size in
layout units. A spread-out layout therefore opens zoomed far out with labels too small to read. The
metrics, all in display units:
  median edge   - median distance between two nodes a relationship joins (self-loops and repeated node
                  pairs counted once)
  longest edge  - the longest such distance
  extent        - the larger side of the bounding box around every node
  closest pair  - the smallest distance between any two nodes, so tightening never makes them overlap

Thresholds are calibrated against the catalogued packages whose layout was checked by eye in Import:
every one has a median edge of 120-200, a longest edge of at most 325, an extent of at most 520 and a
closest pair of at least 70. The four tightened by hand before this check existed sat at medians of
376-449 and longest edges up to 841. Test mode never runs --rescale: it reports, it does not fix.

Prints METRIC lines, then BLOCKER / WARN lines, and ends with "done". Exit status is 0 either way;
callers read the lines. Standard library only."""
import json, math, pathlib, re, statistics, sys

TARGET_MEDIAN = 130
LIMITS = {
    # metric: (warn above, blocker above) - or (warn below, blocker below) for closest pair
    "median edge": (200, 250),
    "longest edge": (330, 450),
    "extent": (550, 800),
}
CLOSEST_WARN, CLOSEST_BLOCKER = 60, 30
GUIDE = (f"aim for a median edge near {TARGET_MEDIAN} and keep every pair of nodes at least 70 apart; "
         "scale the layout with check_layout.py --rescale, then move any node that ends up crowded")


def positions(m):
    pos = {}
    for k, n in (m.get("nodes") or {}).items():
        d = (n.get("extensions") or {}).get("display") or {}
        if isinstance(d.get("x"), (int, float)) and isinstance(d.get("y"), (int, float)):
            pos[k] = (d["x"], d["y"])
    return pos


def metrics(m):
    """{metric: value} for the layout; edge metrics are absent when no relationship joins two nodes."""
    pos = positions(m)
    out = {}
    if len(pos) < 2:
        return out
    keys = list(pos)
    out["closest pair"] = min(math.dist(pos[a], pos[b]) for i, a in enumerate(keys) for b in keys[i + 1:])
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    out["extent"] = max(max(xs) - min(xs), max(ys) - min(ys))
    pairs = set()
    for r in (m.get("relationships") or {}).values():
        a, b = (r.get("from") or {}).get("node"), (r.get("to") or {}).get("node")
        if a in pos and b in pos and a != b:
            pairs.add(tuple(sorted((a, b))))
    if pairs:
        lengths = [math.dist(pos[a], pos[b]) for a, b in pairs]
        out["median edge"] = statistics.median(lengths)
        out["longest edge"] = max(lengths)
        out["_longest pair"] = max(pairs, key=lambda e: math.dist(pos[e[0]], pos[e[1]]))
    return out


def findings(m):
    """[(level, message)] for the layout. Levels are BLOCKER and WARN."""
    mt, res = metrics(m), []
    for name, (warn, block) in LIMITS.items():
        v = mt.get(name)
        if v is None:
            continue
        extra = f" ({' - '.join(mt['_longest pair'])})" if name == "longest edge" else ""
        if v > block:
            res.append(("BLOCKER", f"layout {name} {v:.0f}{extra} is above {block}: Import opens zoomed out too far "
                                   f"to read labels; {GUIDE}"))
        elif v > warn:
            res.append(("WARN", f"layout {name} {v:.0f}{extra} is above {warn}; {GUIDE}"))
    c = mt.get("closest pair")
    if c is not None:
        if c < CLOSEST_BLOCKER:
            res.append(("BLOCKER", f"layout closest pair {c:.0f} is below {CLOSEST_BLOCKER}: nodes overlap"))
        elif c < CLOSEST_WARN:
            res.append(("WARN", f"layout closest pair {c:.0f} is below {CLOSEST_WARN}: labels may overlap"))
    return res


DISPLAY = re.compile(r'("display"\s*:\s*\{)([^{}]*)(\})')
NUM = r"-?\d+(?:\.\d+)?"


def rescale(path, target):
    """Scale every node's display position about the origin so the median edge becomes `target`.
    Edits only the numbers inside each node's display object, so the file's formatting is kept."""
    text = path.read_text(encoding="utf-8")
    m = json.loads(text)
    mt = metrics(m)
    if "median edge" not in mt:
        sys.exit("no relationship joins two different nodes; nothing to scale by")
    f = target / mt["median edge"]
    nodes = list((m.get("nodes") or {}).items())
    spans = [s for s in DISPLAY.finditer(text) if re.search(r'"x"\s*:', s.group(2)) and re.search(r'"y"\s*:', s.group(2))]
    if len(spans) != len(nodes):
        sys.exit(f"found {len(spans)} display objects for {len(nodes)} nodes; edit the coordinates by hand")
    pieces, last = [], 0
    for span, (k, n) in zip(spans, nodes):
        d = n["extensions"]["display"]
        inner = span.group(2)
        got = {a: float(re.search(rf'"{a}"\s*:\s*({NUM})', inner).group(1)) for a in ("x", "y")}
        if got != {"x": float(d["x"]), "y": float(d["y"])}:
            sys.exit(f"display objects are not in node order (at {k}); edit the coordinates by hand")
        for a in ("x", "y"):
            v = int(5 * round(d[a] * f / 5)) or 0
            inner = re.sub(rf'("{a}"\s*:\s*){NUM}', rf"\g<1>{v}", inner, count=1)
        pieces += [text[last:span.start(2)], inner]
        last = span.end(2)
    pieces.append(text[last:])
    new = "".join(pieces)
    assert json.loads(new)["nodes"].keys() == m["nodes"].keys()
    path.write_text(new, encoding="utf-8")
    print(f"RESCALED by {f:.3f}: median edge {mt['median edge']:.0f} -> about {target:g}")


def report(m):
    mt = metrics(m)
    for name in ("median edge", "longest edge", "extent", "closest pair"):
        if name in mt:
            print(f"METRIC {name} {mt[name]:.0f}")
    for level, msg in findings(m):
        print(f"{level} {msg}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    onto = pathlib.Path(args[0]) / "ONTOLOGY.json"
    if "--rescale" in args:
        i = args.index("--rescale")
        target = float(args[i + 1]) if i + 1 < len(args) else TARGET_MEDIAN
        rescale(onto, target)
    report(json.loads(onto.read_text(encoding="utf-8")))
    print("done")
