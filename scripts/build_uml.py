#!/usr/bin/env python3
"""Build editable StarUML models from the implemented public API.

View serialization templates follow the MIT-licensed official StarUML sample.
No StarUML program files are modified. Use StarUML CLI to render this model.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = json.loads((Path(__file__).with_name("uml-view-templates.json")).read_text())
counter = 0


def uid():
    global counter
    counter += 1
    return "SQ" + hashlib.sha256(f"squirrel-020-{counter}".encode()).hexdigest()[:28]


def ref(obj):
    return {"$ref": obj["_id"]}


def element(type_name, parent=None, name=None, **props):
    o = {"_type": type_name, "_id": uid()}
    if parent:
        o["_parent"] = ref(parent)
    if name is not None:
        o["name"] = name
    return dict(o, **props)


def objects(o):
    if isinstance(o, dict):
        if "_id" in o:
            yield o
        for v in o.values():
            yield from objects(v)
    elif isinstance(o, list):
        for v in o:
            yield from objects(v)


def view(kind, model, diagram, x=0, y=0, w=200, h=70):
    o = copy.deepcopy(TEMPLATES[kind])
    # Keep only nested subviews; all foreign sample references are removed.
    oldmodel = o["model"]["$ref"]
    oldparent = o["_parent"]["$ref"]
    ids = {a["_id"]: uid() for a in objects(o)}
    ids[oldmodel], ids[oldparent] = model["_id"], diagram["_id"]

    def rewrite(a):
        if isinstance(a, list):
            return [
                rewrite(v)
                for v in a
                if not (isinstance(v, dict) and "$ref" in v and v["$ref"] not in ids)
            ]
        if not isinstance(a, dict):
            return a
        out = {}
        for k, v in a.items():
            if k in ("containedViews", "containerView"):
                continue
            if isinstance(v, dict) and "$ref" in v and v["$ref"] not in ids:
                continue
            if k == "_id":
                out[k] = ids[v]
            elif k == "$ref":
                out[k] = ids[v]
            elif k == "font":
                out[k] = "PingFang SC;14;" + v.split(";")[-1]
            elif k == "text":
                out[k] = ""
            else:
                out[k] = rewrite(v)
        return out

    o = rewrite(o)
    o.update(
        left=x,
        top=y,
        width=w,
        height=h,
        lineColor="#263638",
        fillColor="#FFFFFF",
        fontColor="#16252B",
        showShadow=False,
    )
    lookup = {a["_id"]: a for a in objects(o)}
    if "nameCompartment" in o:
        n = lookup[o["nameCompartment"]["$ref"]]
        n.update(left=x, top=y, width=w, height=36)
        lookup[n["nameLabel"]["$ref"]].update(
            text=model.get("name", ""), left=x + 5, top=y + 10, width=w - 10
        )
    if "linePart" in o:
        lookup[o["linePart"]["$ref"]].update(left=x + w / 2, top=y + 40, width=1, height=h - 40)
    diagram["ownedViews"].append(o)
    return o


project = element(
    "Project",
    name="松鼠备份 · 第3组 · 0.2.0",
    author="第3组（杨梦宇、郭畅、李想）",
    documentation="松鼠备份的用例、构件、核心类、操作顺序与任务状态模型。",
    ownedElements=[],
)


def model(name, kind="UMLModel"):
    m = element(kind, project, name, ownedElements=[])
    project["ownedElements"].append(m)
    return m


def diagram(parent, kind, name):
    d = element(kind, parent, name, ownedViews=[])
    parent["ownedElements"].append(d)
    return d


def node(m, d, kind, name, box, **props):
    n = element(kind, m, name, **props)
    m["ownedElements"].append(n)
    v = view(kind + "View", n, d, *box)
    return n, v


def edge(parent, d, kind, a, b, label="", points=None, **props):
    ma, va = a
    mb, vb = b
    e = element(kind, parent, label, source=ref(ma), target=ref(mb), **props)
    parent.setdefault("ownedElements", []).append(e)
    v = view(kind + "View", e, d)
    v.update(tail=ref(va), head=ref(vb), showVisibility=False)
    if not points:
        points = [
            (va["left"] + va["width"] / 2, va["top"] + va["height"]),
            (vb["left"] + vb["width"] / 2, vb["top"]),
        ]
    v["points"] = ";".join(f"{x}:{y}" for x, y in points)
    for a in objects(v):
        if a["_type"] == "EdgeLabelView":
            a.update(alpha=1.5707963267948966, distance=16)
    return e, v


def association(parent, d, a, b, points, composition=False, many="1"):
    e = element("UMLAssociation", parent)
    e["end1"] = element(
        "UMLAssociationEnd",
        e,
        reference=ref(a[0]),
        aggregation="composite" if composition else "none",
        multiplicity="1" if composition else "",
    )
    e["end2"] = element(
        "UMLAssociationEnd", e, reference=ref(b[0]), multiplicity=many if composition else ""
    )
    parent["ownedElements"].append(e)
    v = view("UMLAssociationView", e, d)
    v.update(
        tail=ref(a[1]),
        head=ref(b[1]),
        showVisibility=False,
        points=";".join(f"{x}:{y}" for x, y in points),
    )
    # Association-end labels reference their new endpoint models, not the sample.
    for key in (
        "tailRoleNameLabel",
        "tailPropertyLabel",
        "tailMultiplicityLabel",
        "tailQualifiersCompartment",
    ):
        for a2 in objects(v):
            if a2["_id"] == v[key]["$ref"]:
                a2["model"] = ref(e["end1"])
    for key in (
        "headRoleNameLabel",
        "headPropertyLabel",
        "headMultiplicityLabel",
        "headQualifiersCompartment",
    ):
        for a2 in objects(v):
            if a2["_id"] == v[key]["$ref"]:
                a2["model"] = ref(e["end2"])
    return e, v


# 1. Use cases. Optional algorithms are choices within the backup use case.
m = model("01 需求用例")
d = diagram(m, "UMLUseCaseDiagram", "01_系统用例图")
node(m, d, "UMLUseCaseSubject", "松鼠备份", (285, 0, 600, 985))
actor = node(m, d, "UMLActor", "使用者", (40, 245, 100, 110))
cases = {}
for key, title, y in [
    ("backup", "UC-01 创建备份", 50),
    ("restore", "UC-02 恢复到新目录", 170),
    ("inspect", "UC-03 验证完整性", 290),
    ("list", "UC-04 查看内容", 410),
    ("filter", "UC-05 配置筛选", 530),
    ("schedule", "UC-06 定时备份", 650),
    ("watch", "UC-07 目录变化后备份", 770),
    ("stop", "UC-08 取消或停止", 890),
]:
    cases[key] = node(m, d, "UMLUseCase", title, (340, y, 290, 64))
    association(m, d, actor, cases[key], [(140, 300), (340, y + 32)])
edge(
    m,
    d,
    "UMLInclude",
    cases["schedule"],
    cases["backup"],
    points=[(630, 682), (735, 682), (735, 82), (630, 82)],
)
edge(
    m,
    d,
    "UMLInclude",
    cases["watch"],
    cases["backup"],
    points=[(630, 802), (825, 802), (825, 65), (630, 65)],
)

# 2. Service classes, matching the public C++ interfaces.
m = model("02 核心静态模型")
d = diagram(m, "UMLClassDiagram", "02_核心服务类图")


def cls(name, x, y, w, h, ops=(), attrs=()):
    h = max(h, 40 + 23 * (len(ops) + len(attrs)) + 22 * (bool(ops) + bool(attrs)) + 12)
    c, v = node(m, d, "UMLClass", name, (x, y, w, h))
    c["operations"] = []
    for signature in ops:
        n = signature.split("(")[0]
        op = element(
            "UMLOperation",
            c,
            n,
            visibility="public",
            isStatic=name
            in (
                "Scheduler",
                "FileScanner",
                "ArchiveWriter",
                "ArchiveReader",
                "CryptoEnvelope",
                "HuffmanCodec",
            ),
            parameters=[],
        )
        if "..." in signature:
            op["parameters"].append(element("UMLParameter", op, "...", direction="in"))
        if " : " in signature:
            op["parameters"].append(
                element("UMLParameter", op, "", direction="return", type=signature.split(" : ")[1])
            )
        c["operations"].append(op)
    c["attributes"] = [element("UMLAttribute", c, n, type=t, visibility="public") for n, t in attrs]
    v.update(suppressAttributes=not attrs, suppressOperations=not ops)
    lookup = {a["_id"]: a for a in objects(v)}
    lookup[v["attributeCompartment"]["$ref"]]["visible"] = bool(attrs)
    lookup[v["operationCompartment"]["$ref"]]["visible"] = bool(ops)
    return c, v


cs = {
    "scheduler": cls("Scheduler", 30, 40, 260, 90, ["run(...)"]),
    "service": cls(
        "BackupService",
        380,
        40,
        270,
        125,
        ["backup(...) : Summary", "inspect(...) : Summary", "restore(...) : Summary"],
    ),
    "operation": cls(
        "Operation",
        770,
        40,
        280,
        125,
        ["check()", "checkpoint(...)"],
        [("stop", "const atomic<bool>*"), ("progress", "Progress")],
    ),
    "scan": cls("FileScanner", 30, 290, 255, 90, ["scan(...) : vector<Entry>"]),
    "write": cls("ArchiveWriter", 350, 290, 260, 90, ["write(...)"]),
    "read": cls("ArchiveReader", 680, 290, 260, 90, ["read(...) : Summary"]),
    "crypto": cls("CryptoEnvelope", 340, 530, 280, 100, ["seal(...)", "open(...)"]),
    "huffman": cls(
        "HuffmanCodec", 720, 530, 280, 100, ["encode(...) : Bytes", "decode(...) : Bytes"]
    ),
}
edge(m, d, "UMLDependency", cs["scheduler"], cs["service"], points=[(290, 85), (380, 85)])
edge(m, d, "UMLDependency", cs["service"], cs["operation"], "回调与取消", [(650, 90), (770, 90)])
for k in ["scan", "write", "read"]:
    target = cs[k][1]
    tx = target["left"] + target["width"] / 2
    edge(
        m,
        d,
        "UMLDependency",
        cs["service"],
        cs[k],
        points=[(515, 165), (515, 225), (tx, 225), (tx, 290)],
    )
edge(
    m,
    d,
    "UMLDependency",
    cs["service"],
    cs["crypto"],
    points=[(620, 165), (650, 195), (650, 480), (480, 480), (480, 530)],
)
edge(
    m,
    d,
    "UMLDependency",
    cs["write"],
    cs["huffman"],
    points=[(480, 380), (480, 440), (850, 440), (850, 530)],
)
edge(m, d, "UMLDependency", cs["read"], cs["huffman"], points=[(810, 380), (810, 530)])

# Value types with composition multiplicities, separated for readable print size.
d = diagram(m, "UMLClassDiagram", "03_配置与记录类图")
bo = cls("BackupOptions", 40, 40, 300, 130, attrs=[("compress", "bool"), ("password", "string")])
fi = cls(
    "Filter",
    540,
    40,
    400,
    255,
    ["excluded(path) : bool", "accepts(path, stat) : bool"],
    [
        ("excludes", "vector<string>"),
        ("path_pattern / name_pattern", "string"),
        ("types", "string"),
        ("min_size / max_size", "uint64_t"),
        ("since / until / owner", "int64_t"),
    ],
)
su = cls(
    "Summary",
    40,
    380,
    300,
    135,
    attrs=[("entries / files", "uint64_t"), ("bytes / archive_bytes", "uint64_t")],
)
en = cls(
    "Entry",
    540,
    380,
    400,
    245,
    attrs=[
        ("path / link", "string"),
        ("type", "FileType"),
        ("mode / uid / gid", "uint32_t"),
        ("mtime / atime (+ ns)", "time values"),
        ("size / device / inode", "uint64_t"),
        ("ctime (+ ns)", "scan-only"),
        ("xattrs", "vector<pair<string, Bytes>>"),
    ],
)
so = cls(
    "ScheduleOptions",
    40,
    650,
    370,
    150,
    attrs=[
        ("interval_seconds / poll_seconds", "uint32_t"),
        ("keep / max_runs", "uint32_t"),
        ("watch", "bool"),
    ],
)
association(m, d, bo, fi, [(340, 110), (540, 110)], composition=True)
association(m, d, su, en, [(340, 445), (540, 445)], composition=True, many="0..*")

# 4. Build components.
m = model("03 构件模型")
d = diagram(m, "UMLComponentDiagram", "04_系统构件图")
com = {}
for key, title, box in [
    ("gui", "Cocoa GUI\ngui.mm", (50, 45, 300, 100)),
    ("cli", "命令行入口\ncli.cpp", (620, 45, 300, 100)),
    ("core", "libsquirrel.a\nBackupService · Scheduler", (300, 245, 370, 105)),
    ("archive", "扫描与归档\nscanner / archive", (60, 455, 300, 100)),
    ("codec", "Huffman 编解码\nhuffman.cpp", (430, 455, 240, 100)),
    ("crypto", "密码封装\ncrypto.cpp", (740, 455, 240, 100)),
    ("fs", "macOS / POSIX 文件系统", (75, 690, 360, 80)),
    ("cc", "CommonCrypto / Security", (650, 690, 360, 80)),
]:
    com[key] = node(m, d, "UMLComponent", title, box)
for a, b, pts in [
    ("gui", "core", [(200, 145), (200, 195), (410, 195), (410, 245)]),
    ("cli", "core", [(770, 145), (770, 195), (560, 195), (560, 245)]),
    ("core", "archive", [(410, 350), (410, 405), (210, 405), (210, 455)]),
    ("core", "codec", [(550, 350), (550, 455)]),
    ("core", "crypto", [(650, 350), (650, 405), (860, 405), (860, 455)]),
    ("archive", "fs", [(210, 555), (210, 690)]),
    ("crypto", "cc", [(860, 555), (860, 690)]),
]:
    edge(m, d, "UMLDependency", com[a], com[b], points=pts)


# 5/6. Sequence diagrams. Each message models the real call/publication order.
def sequence(name, participants, messages):
    m = model(name, "UMLCollaboration")
    interaction = element("UMLInteraction", m, name, ownedElements=[], participants=[], messages=[])
    m["ownedElements"].append(interaction)
    d = diagram(interaction, "UMLSequenceDiagram", name)
    d.update(showSequenceNumber=True, showSignature=False)
    lifelines = []
    for i, n in enumerate(participants):
        # A named lifeline represents the actual participant, without invented classes.
        life = element("UMLLifeline", interaction, n, isMultiInstance=False)
        interaction["participants"].append(life)
        v = view("UMLSeqLifelineView", life, d, 40 + i * 245, 40, 205, 100 + len(messages) * 65)
        lifelines.append((life, v))
    for i, (a, b, text, reply) in enumerate(messages):
        l1, v1 = lifelines[a]
        l2, v2 = lifelines[b]
        y = 135 + i * 65
        msg = element(
            "UMLMessage",
            interaction,
            text,
            source=ref(l1),
            target=ref(l2),
            messageSort="reply" if reply else "synchCall",
        )
        interaction["messages"].append(msg)
        v = view("UMLSeqMessageView", msg, d)
        v.update(tail=v1["linePart"], head=v2["linePart"])
        x1 = v1["left"] + v1["width"] / 2
        x2 = v2["left"] + v2["width"] / 2
        pts = (
            [(x1, y), (x2, y)]
            if a != b
            else [(x1, y), (x1 + 130, y), (x1 + 130, y + 25), (x1, y + 25)]
        )
        v["points"] = ";".join(f"{x}:{y}" for x, y in pts)
        for obj in objects(v):
            if obj["_type"] == "UMLActivationView":
                obj.update(left=x2 - 7, top=y, width=14, height=30, visible=not reply)
            elif obj["_type"] == "EdgeLabelView":
                obj.update(alpha=1.5707963267948966, distance=15)
    return d


sequence(
    "05_创建备份顺序图",
    ["GUI / CLI", "BackupService", "FileScanner", "ArchiveWriter", "CryptoEnvelope"],
    [
        (0, 1, "backup(source, archive, options)", False),
        (1, 1, "检查路径和参数", False),
        (1, 2, "scan(...)；应用筛选", False),
        (2, 1, "返回条目列表", True),
        (1, 3, "在私有暂存区 write(...)；分块打包/压缩", False),
        (3, 1, "原始归档写入完成", True),
        (1, 4, "seal(...)；摘要或加密认证", False),
        (4, 1, "封装完成", True),
        (1, 2, "重新扫描并比较源目录状态", False),
        (2, 1, "条目和元数据未变化", True),
        (1, 1, "fsync → 最后检查取消 → 独占发布", False),
        (1, 0, "返回 Summary；GUI 显示结果", True),
    ],
)
sequence(
    "06_验证恢复顺序图",
    ["GUI / CLI", "BackupService", "CryptoEnvelope", "ArchiveReader", "文件系统"],
    [
        (0, 1, "restore(archive, newPath, password)", False),
        (1, 1, "拒绝已有目标；创建私有暂存区", False),
        (1, 2, "open(...)；完整认证通过后解密", False),
        (2, 1, "返回经验证的明文暂存文件", True),
        (1, 3, "read(...)；恢复条目", False),
        (3, 4, "校验路径；创建条目并恢复文件元数据", False),
        (3, 4, "验证结束标记后，逆序恢复目录元数据", False),
        (3, 1, "返回恢复条目统计", True),
        (1, 1, "最后检查取消", False),
        (1, 4, "renamex_np(RENAME_EXCL) 发布新目录", False),
        (4, 1, "发布成功", True),
        (1, 0, "返回 Summary", True),
    ],
)

# 7. Scheduler lifecycle (an implementation state model, not persisted state).
m = model("04 自动任务状态")
sm = element("UMLStateMachine", m, "Scheduler 运行状态", ownedElements=[], regions=[])
m["ownedElements"].append(sm)
region = element("UMLRegion", sm, vertices=[], transitions=[])
sm["regions"].append(region)
d = diagram(sm, "UMLStatechartDiagram", "07_自动任务状态图")
states = {}
for key, title, box in [
    ("initial", "", (45, 85, 20, 20)),
    ("checking", "校验与创建任务目录", (130, 60, 250, 70)),
    ("running", "生成完整快照", (500, 60, 250, 70)),
    ("waiting", "等待周期或稳定变化", (500, 315, 290, 70)),
    ("retry", "记录错误，稍后重试", (70, 315, 290, 70)),
    ("cancel", "取消请求 / 清理暂存", (500, 570, 290, 70)),
    ("end", "已停止；保留完成的快照", (65, 570, 330, 70)),
]:
    kind = "UMLPseudostate" if key == "initial" else "UMLState"
    n = element(kind, region, title, **({"kind": "initial"} if key == "initial" else {}))
    region["vertices"].append(n)
    v = view(kind + "View", n, d, *box)
    states[key] = (n, v)
for a, b, label, pts in [
    ("initial", "checking", "启动", [(65, 95), (130, 95)]),
    ("checking", "running", "参数有效", [(380, 95), (500, 95)]),
    ("running", "waiting", "成功：登记并按 keep 淘汰", [(650, 130), (650, 315)]),
    ("waiting", "running", "周期到达 / 变化稳定", [(790, 350), (900, 350), (900, 95), (750, 95)]),
    ("running", "retry", "本轮失败", [(500, 110), (410, 110), (410, 250), (220, 250), (220, 315)]),
    ("retry", "waiting", "等待后重试", [(360, 350), (500, 350)]),
    ("waiting", "cancel", "用户停止", [(650, 385), (650, 570)]),
    ("running", "cancel", "执行中取消", [(750, 110), (1020, 110), (1020, 605), (790, 605)]),
    ("cancel", "end", "清理完成", [(500, 605), (395, 605)]),
    (
        "running",
        "end",
        "成功且达到 max_runs",
        [(510, 130), (455, 190), (455, 495), (230, 495), (230, 570)],
    ),
]:
    e = element("UMLTransition", region, label, source=ref(states[a][0]), target=ref(states[b][0]))
    region["transitions"].append(e)
    v = view("UMLTransitionView", e, d)
    v.update(
        tail=ref(states[a][1]),
        head=ref(states[b][1]),
        showVisibility=False,
        points=";".join(f"{x}:{y}" for x, y in pts),
    )

# Ensure every id is unique and every serialized reference resolves in this project.
all_objects = list(objects(project))
ids = [o["_id"] for o in all_objects]
assert len(ids) == len(set(ids)), "Duplicate model/view id"
idset = set(ids)


def check_refs(o):
    if isinstance(o, dict):
        if "$ref" in o:
            assert o["$ref"] in idset, o
        for v in o.values():
            check_refs(v)
    elif isinstance(o, list):
        for v in o:
            check_refs(v)


check_refs(project)
out = ROOT / "docs/uml"
out.mkdir(exist_ok=True)
(out / "SquirrelBackup.mdj").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n")
(out / "model-validation.json").write_text(
    json.dumps(
        {
            "unique_ids": len(ids),
            "dangling_references": 0,
            "diagrams": [
                {"name": o["name"], "type": o["_type"], "views": len(o["ownedViews"])}
                for o in all_objects
                if o["_type"].endswith("Diagram")
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)
print("Wrote", out / "SquirrelBackup.mdj", "with", len(ids), "objects")
