#!/usr/bin/env python3
from pathlib import Path
from datetime import date, timedelta
import csv, html

root = Path(__file__).resolve().parents[1]
out = root / "docs/planning"
out.mkdir(exist_ok=True)
tasks = [
    ("接手与复现", "2026-10-29", "2026-10-31", "三人分别完成"),
    ("功能与异常验收", "2026-11-01", "2026-11-05", "各自测试，交叉复核"),
    ("文档和模型复核", "2026-11-06", "2026-11-09", "按模块主责"),
    ("视频与答辩排练", "2026-11-10", "2026-11-14", "三人共同"),
    ("最终检查", "2026-11-15", "2026-11-17", "杨梦宇汇总，三人核对"),
    ("答辩与提交", "2026-11-18", "2026-11-18", "上午答辩，23:59截止"),
]
with (out / "后续计划.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["任务", "计划开始", "计划结束", "责任", "状态"])
    w.writerows([list(t) + ["计划，非历史完成记录"] for t in tasks])
a = date(2026, 10, 29)
W = 1130
H = 550
left = 265
cw = 38
s = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="white"/><g font-family="PingFang SC,Microsoft YaHei,sans-serif" fill="#182d32">',
    '<text x="30" y="42" font-size="26" font-weight="600">答辩前实施计划</text><text x="30" y="74" font-size="15">2026年10月29日至11月18日 · 计划日期，完成后另记实际进度</text>',
]
for i in range(21):
    d = a + timedelta(days=i)
    x = left + i * cw
    if d.weekday() > 4:
        s.append(f'<rect x="{x}" y="100" width="{cw}" height="390" fill="#f1f3f3"/>')
    s.append(
        f'<text x="{x+cw/2}" y="124" text-anchor="middle" font-size="13">{d.month}/{d.day}</text>'
    )
for i, (name, start, end, owner) in enumerate(tasks):
    y = 155 + i * 54
    x = left + (date.fromisoformat(start) - a).days * cw
    width = ((date.fromisoformat(end) - date.fromisoformat(start)).days + 1) * cw
    s.append(
        f'<text x="30" y="{y+15}" font-size="17" font-weight="600">{name}</text><text x="30" y="{y+35}" font-size="12">{owner}</text><path d="M{left},{y+45}H1063" stroke="#d7dede"/><rect x="{x+3}" y="{y+3}" width="{width-6}" height="26" fill="#35686d"/>'
    )
s.append(
    '<text x="30" y="525" font-size="14">个人学习证书由三人分别办理；在线仓库与成员复核记录需在提交前补齐。</text></g></svg>'
)
(out / "gantt.svg").write_text("".join(s))
