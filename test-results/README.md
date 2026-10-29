# 测试证据索引

当前版本0.2.0。summary.json给出本轮核心用例数量、整理时间和构建CLI的SHA256；test-matrix.csv可逐项核对97个命名用例。一次测试程序重复运行不增加用例数量。

| 证据 | 范围 |
| --- | --- |
| unit.xml、integration.json、security.json、workflow-regression.json | 52项单元、21项CLI、18项异常归档与并发、6项工作流，共97项 |
| final-build-test-020.log、sanitize-020.log | 普通构建与ASan/UBSan复跑日志 |
| gui-selftest.json、gui-events.txt | 53项原生GUI内部断言；未操作鼠标与系统选择器 |
| signals-020.json、signals-020.log | 20种实际SIGINT／SIGTERM中断组合，另行统计 |
| fault-injection-020.json、fault-injection-020.log、fault-injection-020.pdf | 24种写入故障、重试和SIGKILL补测，独立于97项；复现见同名Markdown |
| acceptance-tools-020.json、acceptance-guide-020.json | 验收辅助工具13个正反例及操作单检查；不代表真人GUI验收 |
| compatibility-020.json | 0.1.0与0.2.0明文、加密双向恢复4种组合 |
| benchmark.json、benchmark-020.log | 单次本机性能测量及内容哈希检查 |
| lint-020.json、lint-020.log | cpplint实际运行结果，不包括Objective-C++ |
| fuzz.json、fuzz.log | 60秒Huffman随机输入测试；不是覆盖率引导的fuzzer |
| archive-fuzz-020.json、archive-fuzz-020.log、archive-fuzz-020.pdf | 10分钟libFuzzer覆盖率引导测试，119,844次输入；范围为SQTREE解析与Huffman，次数不并入97项 |
| archive-fuzz-reproduction-020.json | 随包脚本与LLVM源码重新构建后1000次短检查，独立于十分钟原始结果 |
| archive-fuzz-corpus-020.json | 结束后实际保存813份语料的逐文件校验；原驱动最后一次轮询计数812保留原样 |
| soak-interrupted-20261029.json | 第一次长测中断观察；52次正常检查不等于20小时通过，不与重跑时长相加 |
| lint-rebuild-comparison.json | 长测冻结CLI与最后一次lint重建CLI的映射节逐字节比较 |
| gui-demo-evidence.json、gui-demo-events.txt、video-validation.json | 实际应用演示事件、完整视频解码与时长 |
| uml-validation.json | StarUML模型引用、官方CLI导出结果及模型哈希 |
| presentation-validation.json | PPTX字体、表格结构和重新导入检查 |
| presentation-course-coverage.json、presentation-render-validation.json | 第9讲六项必讲内容逐项核对、11页新版逐页视觉检查；按成员要求不安排前台放映，实际朗读另由小组排练 |

连续20小时测试安排已取消，不再运行或等待。最后有效观察为5.76小时、69次检查；第一次4.34小时中断记录另存，不合并时长。两次均不认定20小时通过。取消说明及原始快照见soak-cancelled-20261029.json和soak-observation-20261029.raw.json。

baseline-0.1.0.log用于追溯原版72项测试；history-0.1.1中的文件属于82项用例时期的旧结果，不代表0.2.0验证。revision-test.log记录0.2.0修订期间的一次执行。空的运行日志只表示该程序成功时不向控制台输出；应结合对应JSON判断。

复现核心：make test、make sanitize。信号补测：python3 tests/signals.py build/squirrel /已有父目录/新的结果目录。长测、GUI及视频的命令见README和各测试源码。运行新测试会覆盖部分结果文件，保留交付证据时请使用源码副本。

## 报告生成输入核对

report-build-inputs.json绑定报告DOCX及生成时的正文、插图、原模板、构建脚本和实验环境字段。正式课程包使用check_report_artifacts.py的--require-current-inputs检查，拒绝正文更新后仍沿用旧报告；Markdown阅读稿同时校验。report-input-guard-020.json记录该辅助检查的实际正反例，不并入97项产品用例。视觉检查仍由report-visual-qa.json记录，输入哈希一致不代表排版已检查。

桌面验收12项见gui-desktop-acceptance.json；恢复独立核对见desktop-restore-comparison.json。验收工具13项正反例见acceptance-tools-020.json。

StarUML七张图实际打开见native-model-acceptance.json；QuickTime播放至结尾及13张关键帧检查见video-visual-qa.json。
