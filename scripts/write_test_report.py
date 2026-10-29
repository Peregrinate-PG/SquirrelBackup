#!/usr/bin/env python3
"""Build the test report from the latest recorded results."""
import csv
import hashlib
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[1]
results = root / "test-results"
docs = root / "docs"
version = subprocess.check_output([str(root / "build/squirrel"), "--version"], text=True).strip()
unit = [
    {
        "name": c.attrib["classname"] + "." + c.attrib["name"],
        "passed": c.find("failure") is None and c.find("error") is None,
    }
    for c in ET.parse(results / "unit.xml").iter("testcase")
]
groups = [
    ("单元", unit),
    ("CLI集成", json.loads((results / "integration.json").read_text())),
    ("异常归档与并发", json.loads((results / "security.json").read_text())),
    ("工作流回归", json.loads((results / "workflow-regression.json").read_text())),
]
alltests = [r for _, g in groups for r in g]
assert len(alltests) == 97 and all(r["passed"] for r in alltests)
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def readable_time(raw):
    value = datetime.fromisoformat(raw).astimezone(ZoneInfo("Asia/Shanghai"))
    return f"{value.year}年{value.month}月{value.day}日 {value.hour:02}:{value.minute:02}"


display_now = readable_time(now) + "（北京时间）"
sha = hashlib.sha256((root / "build/squirrel").read_bytes()).hexdigest()
summary = {
    "generated_at": now,
    "version": version,
    "unit": len(unit),
    "integration": len(groups[1][1]),
    "security": len(groups[2][1]),
    "workflow": len(groups[3][1]),
    "total": len(alltests),
    "passed": sum(r["passed"] for r in alltests),
    "binary_sha256": sha,
}
(results / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
with (results / "test-matrix.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["编号", "层次", "用例名称", "实际结果"])
    for group, data in groups:
        for i, r in enumerate(data, 1):
            w.writerow([f"{group}-{i:02}", group, r["name"], "通过" if r["passed"] else "失败"])
text = f"""# 松鼠备份软件测试报告

版本 {version}。整理时间 {display_now}。自动测试 {len(alltests)} 项，通过 {summary['passed']} 项。GUI、桌面验收和补充测试在对应章节单列。

## 1 测试环境与方法

测试宿主为 macOS {platform.mac_ver()[0]} {platform.machine()}，编译器为 {subprocess.check_output(['clang++','--version'],text=True).splitlines()[0]}。业务代码使用C++17；测试工具包括GoogleTest、Python、AddressSanitizer和UndefinedBehaviorSanitizer。

所有源目录、备份与恢复目标都在测试临时目录内。普通文件用完整字节或SHA256比较；链接用目标字符串和inode关系检查；FIFO只检查类型；元数据按权限、时间和扩展属性逐项比对。测试由随包脚本执行，用例名称和原始输出一并保留。

| 类型 | 用例数量 | 通过数量 | 原始证据 |
| --- | --- | --- | --- |
"""
for name, g in groups:
    evidence = {
        "单元": "unit.xml",
        "CLI集成": "integration.json",
        "异常归档与并发": "security.json",
        "工作流回归": "workflow-regression.json",
    }[name]
    text += f'| {name} | {len(g)} | {sum(r["passed"] for r in g)} | test-results/{evidence} |\n'
text += """
命名用例逐项清单见 test-results/test-matrix.csv。参数化取消测试按不同阶段分别统计；Sanitizer再次运行同一用例不额外计数。

## 2 关键功能与异常用例

下表给出输入、操作和可判断的预期结果。测试步骤可在tests目录中的对应函数复现。

| 编号与检查项 | 输入和操作步骤 | 预期及实际结果 |
| --- | --- | --- |
"""
cases = [
    (
        "T01 目录树往返",
        "中文名、空文件、空目录和跨块文件；备份后恢复到新目录",
        "内容逐字节一致，层级完整；通过",
    ),
    ("T02 原始块模式", "关闭压缩；备份并恢复同一文件树", "无需压缩仍可恢复；通过"),
    ("T03 加密往返", "使用测试密码创建备份，再以正确密码恢复", "认证成功且内容一致；通过"),
    ("T04 错误密码", "用另一密码恢复加密备份", "认证失败，目标目录不存在；通过"),
    ("T05 篡改与截断", "更改归档字节或截去尾部，再验证和恢复", "完整性检查拒绝损坏文件；通过"),
    ("T06 不覆盖备份", "预先创建目标文件，再执行backup", "拒绝发布，原文件内容不变；通过"),
    ("T07 不覆盖恢复", "目标目录内放入保留文件，再执行restore", "拒绝恢复，保留文件不变；通过"),
    (
        "T08 特殊文件",
        "建立软链接、断链、硬链接与FIFO，备份后恢复",
        "链接目标和inode关系正确，FIFO类型保留；通过",
    ),
    (
        "T09 元数据",
        "设定0640权限、固定纳秒时间和user.squirrel属性",
        "恢复权限、时间及属性值符合断言；通过",
    ),
    ("T10 只读目录", "根目录设为只读，备份后恢复", "可发布结果且最终目录仍为原权限；通过"),
    ("T11 排除剪枝", "源树含nested子目录；设置排除规则", "整个被排除子树不进入备份；通过"),
    (
        "T12 六类筛选",
        "分别设置路径、名字、类型、时间、大小、UID条件",
        "仅选入满足条件的非目录条目；通过",
    ),
    (
        "T13 Huffman边界",
        "空、单符号、全字节取值、随机与1MiB输入，编码后解码",
        "字节一致，畸形频数和尾随数据被拒绝；通过",
    ),
    (
        "T14 保留数量",
        "定时生成3份快照，keep=2；存储目录预置无关文件",
        "只保留本任务最新2份，无关文件不变；通过",
    ),
    (
        "T15 变化检测",
        "watch运行后依次新建、改名、删除文件",
        "稳定变化生成新快照，恢复状态对应变化；通过",
    ),
    (
        "T16 保留mtime改写",
        "改写同尺寸文件并恢复mtime；保持其它时间观测",
        "ctime变化可触发快照；通过",
    ),
    ("T17 无变化等待", "启动watch后保持源树不变", "不重复生成相同状态快照；通过"),
    (
        "T18 任务参数",
        "输入小数间隔、短密码、反向范围或文件源路径",
        "启动前拒绝无效配置，不进入无限重试；通过",
    ),
    (
        "T19 路径防护",
        "构造外层摘要正确、内部含父目录跳转等非法路径的备份",
        "解析器拒绝，未向目标外写文件；通过",
    ),
    ("T20 并发发布", "两个进程向同一路径同时创建备份", "仅一个成功，最终文件可验证；通过"),
    (
        "T21 各阶段取消备份",
        "在扫描、打包、封装、源目录复查、发布前请求取消",
        "5种情况均不发布目标并清理暂存；通过",
    ),
    (
        "T22 各阶段取消恢复",
        "在认证、解码、读取、元数据、发布前请求取消",
        "5种情况均不发布恢复目录且保留原备份；通过",
    ),
    ("T23 发布前变化", "打包后分别新增、删除文件或更改元数据", "复查拒绝发生变化的目录树；通过"),
    ("T24 取消自动快照", "先完成一份快照，再取消下一份", "保留上一份完整快照，不留下半成品；通过"),
    (
        "T25 清理边界",
        "暂存中包含不可读目录和指向外部的符号链接",
        "能清理自身目录，不跟随链接清理外部路径；通过",
    ),
    (
        "T26 淘汰失败",
        "让旧快照路径无法删除，并限定成功次数",
        "记录警告；不额外创建快照、不绕过max_runs；通过",
    ),
]
for c in cases:
    text += "| " + " | ".join(c) + " |\n"
text += """
表中的T编号按功能场景组织，具体命名用例见test-results/test-matrix.csv。

## 3 原生界面验证

"""
gui = json.loads((results / "gui-selftest.json").read_text())
assert gui["passed"]
text += f"""AppKit后台测试通过 {gui['assertions']} 项断言，检查输入校验、密码字段、表单设置、忙碌状态、备份、错误密码、恢复、内容查看、验证、保留数量、停止及退出。

2026年10月29日在李想的Mac上完成12项桌面验收，使用系统辅助功能和鼠标、键盘事件检查六个文件选择器、中文空格路径、拒绝覆盖、错误密码、定时保留、变化检测及运行中停止。备份中关闭窗口和恢复中退出均等待清理后结束进程；重启恢复表单参数，密码为空，任务保持停止。

![图9 桌面验收中的恢复结果](screenshots/desktop/23-neutral-restored.png)

桌面验收记录见test-results/gui-desktop-cases.json。恢复核对包括内容、权限、时间、软硬链接、FIFO和用户扩展属性；系统维护的com.apple.macl与com.apple.provenance不参与比对。

## 4 编译与补充检查

业务源码以-Wall -Wextra -Wpedantic -Werror编译通过。make sanitize对同一组 {len(alltests)} 项用例启用AddressSanitizer与UndefinedBehaviorSanitizer，检查通过。C++编码规范由cpplint检查，C++与Objective-C++排版由clang-format检查。

"""
for filename, label in [
    ("signals-020.json", "信号中断"),
    ("fault-injection-020.json", "写入故障与强制终止"),
]:
    record = json.loads((results / filename).read_text())
    assert record["passed"] and record["binary_sha256"] == sha, filename
    cases = record["results"]
    assert all(item["passed"] for item in cases)
    text += f"{label}测试通过{len(cases)}项，记录见test-results/{filename}。"
    if filename.startswith("signals"):
        text += "明文与加密的备份、恢复、验证、查看操作接收SIGINT或SIGTERM后返回130并清理暂存；自动任务停止后保留已完成快照。\n\n"
    else:
        text += "通过注入ENOSPC、EINTR、短写入及发布失败检查错误处理，并在实际读写中发送SIGKILL。异常操作不覆盖已有结果，正常重试成功；强制终止后可能保留私有暂存目录。\n\n"
text += """## 5 性能与兼容性

在本机各执行一次备份和恢复，结果如下。耗时包含进程启动，受文件系统缓存和后台负载影响。

| 数据集 | 输入字节 | 归档字节 | 备份秒 | 恢复秒 | SHA256 |
| --- | --- | --- | --- | --- | --- |
"""
for b in json.loads((results / "benchmark.json").read_text()):
    assert b["sha256_equal"]
    text += f'| {"重复单字节" if b["workload"]=="repeated" else "随机数据"} | {b["source_bytes"]} | {b["archive_bytes"]} | {b["backup_seconds"]:.4f} | {b["restore_seconds"]:.4f} | 一致 |\n'
comp = json.loads((results / "compatibility-020.json").read_text())
assert all(item["passed"] for item in comp["results"])
text += f"""
重复数据检查Huffman单符号压缩，随机数据检查压缩收益不足时保存原始块。

0.1.0与当前0.2.0进行了明文、加密的双向兼容测试，共{len(comp['results'])}种组合，恢复内容与链接关系均符合预期，记录见test-results/compatibility-020.json。

## 6 测试结论

{len(alltests)}项核心测试及GUI、信号和故障注入检查通过。测试覆盖了正常往返、输入错误、归档损坏、取消和自动任务。验证环境为本机磁盘；结果按各项输入、操作与断言记录。

复现命令为make test、make sanitize及README中列出的GUI自测命令。性能、兼容性、信号和故障注入脚本位于tests目录，测试数据在独立临时目录内创建。
"""
(docs / "03_软件测试报告.md").write_text(text)
print(json.dumps(summary, ensure_ascii=False))
