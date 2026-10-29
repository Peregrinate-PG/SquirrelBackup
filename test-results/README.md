# 测试证据索引

当前版本0.2.0。summary.json给出本轮核心用例数量、整理时间和构建CLI的SHA256；test-matrix.csv可逐项核对97个命名用例。一次测试程序重复运行不增加用例数量。

| 证据 | 范围 |
| --- | --- |
| unit.xml、integration.json、security.json、workflow-regression.json | 52项单元、21项CLI、18项异常归档与并发、6项工作流，共97项 |
| final-build-test-020.log、sanitize-020.log | 普通构建与ASan/UBSan复跑日志 |
| gui-selftest.json、gui-events.txt | 53项原生GUI内部断言；未操作鼠标与系统选择器 |
| signals-020.json、signals-020.log | 20种实际SIGINT／SIGTERM中断组合，另行统计 |
| fault-injection-020.json、fault-injection-020.log、fault-injection-020.pdf | 24种写入故障、重试和SIGKILL补测，独立于97项；复现见同名Markdown |
| acceptance-tools-020.json、acceptance-guide-020.json | 验收辅助工具12个正反例及操作单检查；不代表真人GUI验收 |
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

20小时长测在独立后台进程中进行。只有完成后的soak-20h.json明确记录status=passed，才能认定通过；soak-in-progress.json为打包前的中途快照。如果交付包只有报告里的中途快照，就仍属运行中。长测冻结CLI和最终构建CLI分别记录哈希，二者完整文件并不相同，映射节比较证据解释其对应关系。

baseline-0.1.0.log用于追溯原版72项测试；history-0.1.1中的文件属于82项用例时期的旧结果，不代表0.2.0验证。revision-test.log记录0.2.0修订期间的一次执行。空的运行日志只表示该程序成功时不向控制台输出；应结合对应JSON判断。

复现核心：make test、make sanitize。信号补测：python3 tests/signals.py build/squirrel /已有父目录/新的结果目录。长测、GUI及视频的命令见README和各测试源码。运行新测试会覆盖部分结果文件，保留交付证据时请使用源码副本。
