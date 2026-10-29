#!/usr/bin/env python3
"""Assemble the reading copy from the same sections used in the DOCX template."""
import argparse
import json
import re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true',help='Reject a stale reading copy without changing it')
args=parser.parse_args()
docs=root/'docs'
start="""# 软件开发综合实验小组报告

电子科技大学 计算机科学与工程学院 · 第3组 · 松鼠备份0.2.0

组长：杨梦宇 2023150901002；组员：郭畅 2023040904017、李想 2023150901012。

本阅读稿与课程Word报告共用需求、设计、测试和总结正文；封面、原表格和教师评分栏保留在Word版本。个人职责按模块划分，技术总结以项目实现与测试记录为依据。

## 一 实验室名称

________________（按实际填写）

## 二 实验项目名称

文件备份软件 松鼠备份 Squirrel Backup。

## 三 实验目的

综合运用C/C++、数据结构、软件工程和操作系统文件接口，完成需求分析、设计、实现、测试与发布。练习文件树表示、自定义格式、无损压缩、密码封装和资源管理，并用实际结果核对需求。

## 四 实验内容

实现macOS单机备份与恢复，提供GUI和CLI，共用C++业务核心。选做功能包括软硬链接、FIFO、基础元数据、六类筛选、打包压缩、密码加密、定时、变化检测和任务内保留策略。网络备份、增量备份与系统守护未实现。系统密码库和Cocoa的使用如实说明，不将库算法申报为自研。

## 五 实验器材

macOS13.0、Apple Silicon、Apple Clang14.0.3、Command Line Tools、make、git、GoogleTest与Python；Cocoa/AppKit用于GUI。StarUML7.1.1用于模型读取与导出校验。

## 六 实验步骤及操作

"""
profile=json.loads((root/'resources/submission-readiness.json').read_text())
start=start.replace('________________（按实际填写）',profile['laboratory'])
parts=[start]
for name in ['01_需求分析说明书.md','02_系统设计文档.md','03_软件测试报告.md']:
    text=(docs/name).read_text()
    text=re.sub(r'^(#{1,5}) ',r'#\1 ',text,flags=re.M)
    parts.append(text)
sections=json.loads((root/'resources/report-sections.json').read_text())
titles=['七 AI开发工具使用总结','八 实验结论','九 总结及心得体会','十 对实验过程与方法的改进建议']
for row,title in zip(range(13,17),titles):
    parts.append('## '+title+'\n')
    for kind,text in sections[str(row)]:parts.append(('### ' if kind=='h2' else '')+text+'\n')
parts.append('报告评分、指导教师签字：由教师填写。\n')
expected='\n'.join(parts)
target=docs/'05_实验报告.md'
if args.check:
    if not target.exists() or target.read_text()!=expected:
        raise SystemExit('Reading report is stale; regenerate from the current sections')
else:
    target.write_text(expected)
