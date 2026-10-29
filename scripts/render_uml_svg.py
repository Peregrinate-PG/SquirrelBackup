#!/usr/bin/env python3
"""Independent SVG renderer for this project's own UML model.

This does not read, alter, crop or remove marks from StarUML image exports.
The .mdj model is separately validated using the unmodified StarUML application.
"""
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT / "docs/uml/SquirrelBackup.mdj").read_text())


def objects(x):
    if isinstance(x, dict):
        if "_id" in x:
            yield x
        for v in x.values():
            yield from objects(v)
    elif isinstance(x, list):
        for v in x:
            yield from objects(v)


INDEX = {a["_id"]: a for a in objects(MODEL)}


def resolve(x):
    return INDEX[x["$ref"]]


def esc(x):
    return html.escape(str(x), quote=True)


def text(x, y, lines, size=18, anchor="middle", bold=False):
    if isinstance(lines, str):
        lines = lines.split("\n")
    return "".join(
        f'<text x="{x}" y="{y+i*(size+6)}" font-size="{size}" text-anchor="{anchor}"'
        f' font-weight="{600 if bold else 400}">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )


def rect(x, y, w, h, rx=0, fill="#ffffff"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="#263638" stroke-width="1.6"/>'


def points(v):
    return [tuple(map(float, t.split(":"))) for t in v["points"].split(";")]


def label_at(pts, label, position=None):
    if not label:
        return ""
    # Place label at the longest segment to avoid corner and node overlaps.
    a, b = max(zip(pts, pts[1:]), key=lambda ab: math.dist(*ab))
    x = (a[0] + b[0]) / 2
    y = (a[1] + b[1]) / 2 - 10
    if position:
        x, y = position
    lines = label.split("\n")
    width = max(sum(1 if ord(c) > 255 else 0.55 for c in s) for s in lines) * 16 + 14
    return rect(x - width / 2, y - 17, width, len(lines) * 22 + 4, fill="#ffffff").replace(
        'stroke="#263638"', 'stroke="none"'
    ) + text(x, y, lines, 16)


def render(d):
    vs = d["ownedViews"]
    nodes = [v for v in vs if "points" not in v]
    edges = [v for v in vs if "points" in v]
    maxx = (
        max(
            [v.get("left", 0) + v.get("width", 0) for v in nodes]
            + [x for v in edges for x, y in points(v)]
        )
        + 100
    )
    maxy = (
        max(
            [v.get("top", 0) + v.get("height", 0) for v in nodes]
            + [y for v in edges for x, y in points(v)]
        )
        + 45
    )
    title = d["name"].split("_", 1)[1]
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{maxx}" height="{maxy+75}" viewBox="0 0 {maxx} {maxy+75}">',
        '<defs><marker id="open" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#263638" stroke-width="1.2"/></marker>',
        '<marker id="solid" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M1 1L9 5L1 9Z" fill="#263638"/></marker>',
        '<marker id="diamond" markerWidth="15" markerHeight="10" refX="0" refY="5" orient="auto"><path d="M0 5L7 0L14 5L7 10Z" fill="#263638"/></marker></defs>',
        f'<rect width="100%" height="100%" fill="white"/><g font-family="PingFang SC, Microsoft YaHei, sans-serif" fill="#16252b">',
        text(35, 32, title, 26, "start", True),
        text(maxx - 30, 32, "Squirrel Backup 0.2.0", 14, "end"),
        '<g transform="translate(0 50)">',
    ]
    labels = []
    for v in edges:
        m = resolve(v["model"])
        p = points(v)
        typ = m["_type"]
        dash = ""
        marker = ""
        start = ""
        if typ in ("UMLDependency", "UMLInclude"):
            dash = ' stroke-dasharray="7 5"'
            marker = ' marker-end="url(#open)"'
        elif typ in ("UMLTransition", "UMLMessage"):
            marker = ' marker-end="url(#solid)"'
            if m.get("messageSort") == "reply":
                dash = ' stroke-dasharray="7 5"'
                marker = ' marker-end="url(#open)"'
        if typ == "UMLAssociation" and m["end1"].get("aggregation") == "composite":
            start = ' marker-start="url(#diamond)"'
            labels.append(text(p[0][0] + 22, p[0][1] - 12, "1", 16, "start"))
            labels.append(
                text(p[-1][0] - 12, p[-1][1] - 12, m["end2"].get("multiplicity", ""), 16, "end")
            )
        path = " ".join(("M" if i == 0 else "L") + f"{x},{y}" for i, (x, y) in enumerate(p))
        s.append(
            f'<path d="{path}" fill="none" stroke="#263638" stroke-width="1.6"{dash}{marker}{start}/>'
        )
        label = "«include»" if typ == "UMLInclude" else m.get("name", "")
        if typ == "UMLMessage":
            messages = resolve(m["_parent"])["messages"]
            number = next(i + 1 for i, a in enumerate(messages) if a["_id"] == m["_id"])
            label = f"{number}. {label}"
        position = None
        if d["_type"] == "UMLStatechartDiagram":
            position = {"成功且达到 max_runs": (300, 475), "等待后重试": (430, 315)}.get(label)
        labels.append(label_at(p, label, position))
    for v in nodes:
        m = resolve(v["model"])
        typ = m["_type"]
        x = v["left"]
        y = v["top"]
        w = v["width"]
        h = v["height"]
        name = m.get("name", "")
        if typ == "UMLUseCaseSubject":
            s.append(rect(x, y, w, h, fill="none"))
            s.append(text(x + 15, y + 25, name, 18, "start", True))
        elif typ == "UMLActor":
            cx = x + w / 2
            s.append(
                f'<circle cx="{cx}" cy="{y+15}" r="14" fill="white" stroke="#263638" stroke-width="1.8"/>'
            )
            s.append(
                f'<path d="M{cx},{y+29}v38 M{cx-28},{y+44}h56 M{cx},{y+67}l-26,30 M{cx},{y+67}l26,30" fill="none" stroke="#263638" stroke-width="1.8"/>'
            )
            s.append(text(cx, y + 122, name, 18))
        elif typ == "UMLUseCase":
            s.append(
                f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="white" stroke="#263638" stroke-width="1.6"/>'
            )
            s.append(text(x + w / 2, y + h / 2 + 6, name, 18, bold=True))
        elif typ == "UMLPseudostate":
            s.append(f'<circle cx="{x+w/2}" cy="{y+h/2}" r="{w/2}" fill="#263638"/>')
        elif typ == "UMLClass":
            s.append(rect(x, y, w, h))
            s.append(text(x + w / 2, y + 26, name, 20, bold=True))
            cursor = y + 40
            for group in ["attributes", "operations"]:
                items = m.get(group, [])
                if not items:
                    continue
                s.append(f'<path d="M{x},{cursor}h{w}" stroke="#263638"/>')
                cursor += 22
                for a in items:
                    if group == "attributes":
                        t = "+ " + a["name"] + ": " + a.get("type", "")
                    else:
                        ins = [
                            p.get("name", "")
                            for p in a.get("parameters", [])
                            if p.get("direction") != "return"
                        ]
                        returns = [
                            p.get("type", "")
                            for p in a.get("parameters", [])
                            if p.get("direction") == "return"
                        ]
                        t = (
                            "+ "
                            + a["name"]
                            + "("
                            + ", ".join(ins)
                            + ")"
                            + (": " + returns[0] if returns else "")
                        )
                    s.append(text(x + 9, cursor, t, 16, "start"))
                    if a.get("isStatic"):
                        s.append(
                            f'<path d="M{x+9},{cursor+3}h{min(w-18,len(t)*8)}" stroke="#263638" stroke-width=".7"/>'
                        )
                    cursor += 23
        elif typ == "UMLLifeline":
            s.append(f'<path d="M{x+w/2},{y+45}v{h-45}" stroke="#819091" stroke-dasharray="6 6"/>')
            s.append(rect(x, y, w, 45))
            s.append(text(x + w / 2, y + 28, name, 20, bold=True))
        else:
            s.append(rect(x, y, w, h, 12 if typ == "UMLState" else 0))
            lines = name.split("\n")
            s.append(text(x + w / 2, y + h / 2 - (len(lines) - 1) * 13 + 6, lines, 18, bold=True))
            if typ == "UMLComponent":
                s.append(rect(x + w - 30, y + 8, 20, 23))
                s.append(rect(x + w - 35, y + 11, 9, 6))
                s.append(rect(x + w - 35, y + 22, 9, 6))
    s += labels
    s.append("</g></g></svg>")
    return "".join(s)


out = ROOT / "docs/uml/svg"
out.mkdir(exist_ok=True)
for d in objects(MODEL):
    if d["_type"].endswith("Diagram"):
        (out / (d["name"] + ".svg")).write_text(render(d))
print("Rendered independent SVG diagrams:", out)
