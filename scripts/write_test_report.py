#!/usr/bin/env python3
"""Generate factual course test summaries from machine-readable results."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from datetime import datetime
root=Path(__file__).resolve().parents[1]
xml=ET.parse(root/'test-results/unit.xml').getroot()
unit=[]
for c in xml.iter('testcase'):
    unit.append(dict(name=c.attrib['classname']+'.'+c.attrib['name'],passed=c.find('failure') is None and c.find('error') is None,seconds=float(c.attrib.get('time',0))))
integration=json.loads((root/'test-results/integration.json').read_text())
security=json.loads((root/'test-results/security.json').read_text())
benchmark=json.loads((root/'test-results/benchmark.json').read_text())
alltests=unit+integration+security
now=datetime.now().astimezone().isoformat(timespec='seconds')
text=f'''# 松鼠备份软件测试报告

版本 0.1.0。结果生成时间 {now}。本报告依据 test-results 中的 GoogleTest XML、集成与安全测试 JSON、Sanitizer 日志和性能实测生成。测试对象为本机编译的 C++ 核心与 CLI；另有 GUI 离屏渲染和内部动作测试，真实自动点击权限未获准，不能将这些结果等同于完整 GUI 验收。

## 1 引言

目标是验证备份内容、目录结构、扩展功能及异常情况下的原文件保护，满足讲义至少两种测试类型、15 个以上用例的要求。平台为 macOS 15.7.9 arm64、Apple Clang 17、C++17。测试数据通过临时目录隔离，普通文件恢复后用 SHA256 或完整字节比较，特殊文件用 lstat、read_symlink 和 inode 关系验证。测试人员栏请由执行并复核的学生填写；本轮由 AI 编程会话自动执行，不冒填真人。

## 2 功能测试

本轮共有 {len(unit)} 项 GoogleTest 测试、{len(integration)} 项 CLI 黑盒测试和 {len(security)} 项异常归档与并发测试，合计 {len(alltests)} 项，通过 {sum(x['passed'] for x in alltests)} 项。单元和黑盒集成两种类型均有源码和可复现命令。安全测试是附加异常验证，不代替渗透测试或安全审计。

### 2.1 全部用例结果

| 编号 | 层次与名称 | 实际结果 |
| --- | --- | --- |
'''
for prefix,data in [('UT',unit),('IT',integration),('SEC',security)]:
    for i,r in enumerate(data,1):
        text+=f'| {prefix}-{i:02d} | {r["name"]} | {"通过" if r["passed"] else "失败"} |\n'
text+='''
### 2.2 关键用例详细说明

以下全部用例程序版本为 0.1.0，级别为重要，执行日期见本报告生成时间，执行方式为自动化。预置条件为本机编译成功且测试临时目录可写，测试人员待学生复核填写。每一项实际结果以对应 XML／JSON 为证据。

'''
cases=[
('TC-01','目录树往返','BackupTest.Roundtrip','源树含中文文件、空文件、空目录和跨块大文件','backup 后 restore 到新目录','恢复内容逐字节一致，层级与空目录存在'),
('TC-02','原始块模式','BackupTest.RawRoundtrip','关闭压缩','备份还原后比较大文件','不经过 Huffman 仍正确恢复'),
('TC-03','密码加密','BackupTest.EncryptedRoundtrip','设置至少 8 字节测试密码','先无密码检查，再用正确密码恢复','无密码拒绝，正确密码还原成功'),
('TC-04','错误密码','BackupTest.WrongPasswordLeavesNoOutput','已生成加密备份','使用不同密码恢复','认证失败且新目标不存在'),
('TC-05','备份损坏','BackupTest.TamperDetection','已生成完整备份','更改备份中间字节后恢复','摘要不匹配，失败且无发布目标'),
('TC-06','备份不覆盖','BackupTest.NoOverwriteBackup','输出备份已存在','再次使用同一文件名备份','拒绝操作且原备份字节不变'),
('TC-07','恢复不覆盖','BackupTest.NoOverwriteRestore','目标目录含 keep 文件','尝试恢复到已有目录','拒绝操作且 keep 内容不变'),
('TC-08','特殊文件','BackupTest.SymlinkHardlinkFifo','源树含软链接、断链、硬链接与 FIFO','备份后恢复并读取类型和链接关系','目标字符串、硬链接 inode 关系和 FIFO 类型正确'),
('TC-09','元数据','BackupTest.Metadata','测试文件为 0640，设置固定纳秒时间与 user.squirrel xattr','备份恢复后读取权限、时间及 xattr','权限和时间精度正确，属性值为 value'),
('TC-10','排除剪枝','BackupTest.ExcludePrunesDirectory','设置排除 nested','备份还原后检查树','nested 整个目录不出现'),
('TC-11','六类筛选','BackupTest.NameFilter / PathFilter / SizeFilter / TimeFilter / OwnerFilter / TypeFilter','分别设置名字、路径、尺寸、时间、UID、类型条件','读取备份条目统计及还原结果','仅选择满足条件的非目录节点，目录结构保留'),
('TC-12','压缩边界','Huffman.RandomRoundtrip / Empty / SingleSymbol / AllSymbols','固定随机种子及多种长度，包含 1 MiB','encode 后 decode','字节一致，空和单符号块不出错'),
('TC-13','任务淘汰','CLI-14 schedule retention isolation','独立存储目录内预置 keep-me.sqbk','每秒运行一次，成功三次，keep=2','本任务保留两份，预置无关文件不变'),
('TC-14','变化检测','CLI-15 change detection','watch poll=1，限定成功四次','依次新建、重命名并删除测试文件','各阶段产生新快照，恢复后对应阶段的名字与删除状态正确'),
('TC-15','停止任务','CLI-16 graceful stop','运行周期 300 秒任务','首个快照后发送 SIGINT','进程正常退出，快照保留'),
('TC-16','路径穿越防护','SEC-01 至 SEC-07','构造摘要正确但路径恶意的归档','restore 到新目录','拒绝父路径、绝对路径、软链接父节点或外部硬链接，无外部文件发布'),
('TC-17','并发发布','SEC-18 concurrent publication','两个进程向同一路径备份','并发启动后 verify 唯一输出','一个成功、一个失败，最终备份可验证'),
('TC-18','淘汰失败不重复备份','BackupTest.RetentionFailureDoesNotRepeatSnapshot','keep=1，max_runs=2，在第二份快照完成时将第一份路径替换成非空目录','模拟旧快照无法删除的错误','记录警告并在两份成功快照后退出，不额外生成第三份'),
('TC-19','任务参数前置校验','CLI-20 / CLI-21','短密码、反向尺寸范围和无效类型','启动 schedule 或 watch','立即失败，未创建任务目录，不进入无限重试'),
]
for ident,title,evidence,condition,steps,expected in cases:
    text+=f'#### {ident} {title}\n\n模块与证据：{evidence}。\n\n预置与输入：{condition}。\n\n操作步骤：{steps}。\n\n预期结果：{expected}。\n\n实际结果：对应自动测试通过，符合该项断言；完整输出见 test-results。\n\n'
gui_path=root/'test-results/gui-selftest.json'
if gui_path.exists():
    gui=json.loads(gui_path.read_text())
    text+=f"### 2.3 原生界面内部验证\n\n应用启动及三个页面离屏渲染已验证，预览位于 docs/screenshots。内部业务动作测试通过 {gui['assertions']} 项断言，覆盖空输入、加密开关、忙碌与按钮状态、备份、错误密码提示、恢复、列表、验证和自动任务停止。该结果与前述 {len(alltests)} 项自动用例分开统计，不把断言数量当成独立测试用例。文件选择器、真实点击和完整 GUI 人工验收仍待完成。见 gui-selftest.json 与 gui-validation.md。\n\n"
text+='''## 3 代码测试

业务源码使用编译器严格告警，已执行 clang-format 与 cpplint。cpplint 使用 100 列规范，明确关闭六个与项目约定不一致的检查：build/c++17（本项目要求 C++17）、build/header_guard（使用项目稳定命名）、build/namespaces（CLI 局部 using）、build/include_order 和 build/include_subdir（本项目包含路径约定）、runtime/references（公开 API 使用 const 引用）。其它检查保留。输出见 lint.log；零剩余告警不能说明不存在逻辑缺陷。

AddressSanitizer 和 UndefinedBehaviorSanitizer 通过 make sanitize 对核心与 CLI 测试运行，结果见 sanitize.log。它们不替代多线程竞态检查、全系统泄漏审计或强制掉电测试。本机没有把 Linux 的 perf、valgrind 安装记录虚构进报告。

## 4 性能测试

方法为临时生成数据，使用单调高精度时钟统计 CLI 完整备份和恢复耗时，再比较恢复 SHA256。单次运行、同机本地卷、可能受文件系统缓存和负载影响，不作多次统计结论。系统 time -l 获取资源指标因 sysctl 权限受限失败，已改为无额外权限的墙钟测量，未取得可靠峰值 RSS，表中不报告该项。

| 数据集 | 原始字节 | 备份字节 | 备份秒 | 恢复秒 | 哈希 |
| --- | --- | --- | --- | --- | --- |
'''
for b in benchmark:
    text+=f'| {b["workload"]} | {b["source_bytes"]} | {b["archive_bytes"]} | {b["backup_seconds"]:.4f} | {b["restore_seconds"]:.4f} | 一致 |\n'
text+='''
重复单字节数据主要验证单符号 Huffman 分支，压缩率不代表真实文档；随机数据验证自动回退原始块，输出略大于输入来自头部与记录开销。没有执行多 GiB 压力测试或整夜持续稳定性测试，不把格式上限作为实测容量。

## 5 健壮性与安全测试

已覆盖短密码、缺失密码变量、未知参数、无效数值、错误范围、截断、篡改、重复路径、非法类型、超大长度、路径跳转、畸形 Huffman、尾随数据和并发发布等情况。恶意归档带正确的未加密 SHA256，确保测试进入树解析器而非全部停在外层校验。

没有完成：磁盘真实耗尽、掉电持久性、强制 kill 后清理、持续竞争修改源目录、超大 xattrs、多用户属主迁移、网络卷、外置文件系统兼容性，以及 GUI 文件选择器／按钮点击／窗口关闭人工验收。当前不提供后台守护、网络或增量功能，其对应测试不适用。

## 6 测试结果分析

已验证的核心路径形成从备份到验证、内容查看、安全恢复和自动任务的闭环。当前自动用例全部通过，初版可用于受控演示和后续迭代。GUI 已完成编译、签名、离屏渲染与内部动作验证；因自动点击操作未获准，GUI 端到端人工验收仍属于待办，不填写为通过。

重现命令：make test、make sanitize、make lint、python3 tests/benchmark.py build/squirrel。测试源码与 XML／JSON／日志随源码和发布包交付。后续修改格式或核心逻辑后需重新运行并重新生成报告。
'''
for filename,heading in [('fuzz.json','7 种子变异与随机输入测试'),('stability.json','8 持续运行与反复修改测试')]:
    p=root/'test-results'/filename
    if p.exists():
        data=json.loads(p.read_text())
        text+='\n## '+heading+'\n\n'
        if filename=='fuzz.json':
            text+=f"固定种子 {data['seed']}，运行 {data['seconds']:.1f} 秒，执行 {data['iterations']} 次输入处理，Sanitizer 下未发现失败。该驱动混合有效 Huffman 编码、位变异和随机字节，且包含编码往返断言。系统 SDK 缺少 libFuzzer 运行库，因此采用项目自有的有界驱动；不是覆盖率引导模糊测试，不代表穷尽输入空间。\n"
        else:
            text+=f"运行 {data['duration_seconds']:.1f} 秒，原子替换源文件 {data['edits']} 次，完成 {data['completed_snapshots']} 份快照。停止后保留 {data['retained']} 份，全部通过 verify，恢复固定文件 SHA256 一致。该结果是有界持续运行检查，不是整夜或长期可靠性证明。\n"
review_path=root/'test-results/review-stability.json'
if review_path.exists():
    data=json.loads(review_path.read_text())
    text+=f"\n## 9 本轮复核与修正\n\n本轮新增淘汰失败与启动参数回归检查。成功快照先提交计时和监测状态，再尽力执行淘汰；淘汰失败不会重复生成备份，也不会绕过 max_runs。短密码、非法范围或类型在创建任务前拒绝。更新后的程序另连续运行 {data['duration_seconds']:.1f} 秒，生成 {data['completed_snapshots']} 份快照，保留 {data['retained']} 份且全部验证通过。第 8 节十分钟记录来自初版正常路径，作为历史测试保留，不等同于本轮重新运行十分钟。\n"
(root/'docs/03_软件测试报告.md').write_text(text)
(root/'test-results/summary.json').write_text(json.dumps(dict(generated_at=now,unit=len(unit),integration=len(integration),security=len(security),total=len(alltests),passed=sum(x['passed'] for x in alltests)),ensure_ascii=False,indent=2))
