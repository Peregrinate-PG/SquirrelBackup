# 归档解析器模糊输入补测

2026年10月29日14:38至14:48，在macOS 13.0 arm64上对SQTREE内部归档解析器进行覆盖率引导测试。进程运行602.286秒；libFuzzer记录119,844次输入执行，正常退出，没有产生崩溃样本，也没有报告AddressSanitizer或UndefinedBehaviorSanitizer错误。

| 项目 | 本次记录 |
| --- | --- |
| 工具 | LLVM libFuzzer 14.0.6，Apple Clang 14.0.3，ASan与UBSan |
| 初始样本 | 4份经过CLI备份、完整性验证后提取的内部归档 |
| 输入边界 | 最大64KiB，每份输入超时5秒，内存限制512MiB |
| 执行次数与时间 | 119,844次；工具计时601秒，驱动计时602.286秒 |
| 运行资源 | nice 15；工具记录峰值RSS 339MiB |
| 最后覆盖计数 | cov=2037、ft=9940；是工具计数，不是代码覆盖百分比 |
| 结果 | 退出码0，无错误标记，无崩溃工件；最终保存813份输入样本 |

测试直接把输入交给ArchiveReader，跳过外层摘要或加密认证，以便变异输入能够到达内部字段、条目及Huffman解码逻辑。恢复目标始终为空，不按输入里的路径创建文件；测试框架只反复写入自己创建的0600临时输入文件。解析器主动拒绝坏格式属于正常结果，其他异常没有被统一吞掉。

四份原始样本包含空目录树，以及普通文件、中文名、软硬链接、FIFO、原始块和单符号压缩块。固定随机种子为20261029。libFuzzer会保留带来新执行特征的输入，并继续变异；次数包括重复路径和被快速拒绝的输入，不能视为119,844个独立功能用例。本轮独立于97项核心命名测试统计。

结论只适用于所记录源码、样本和边界。没有覆盖GUI、密码封装、恢复文件写入、所有系统调用，也不能据此断言不存在缺陷。最大输入64KiB不代表已验证任意大小归档。

复现时使用macOS Command Line Tools，在项目根目录执行：

```sh
python3 scripts/build_archive_fuzzer.py
python3 tests/archive_fuzz.py build/archive-fuzzer/archive-reader-fuzz \
  /已有父目录/新的解析器测试目录 --seconds 600
```

输出目录必须尚不存在。默认使用随源码附带的四份初始样本；结果、日志、演化语料和失败样本分别保存在status.json、fuzzer.log、corpus和artifacts。短检查可将最后的参数改为--runs 1000；短检查不代替十分钟结果。交付脚本已在新的构建目录中重建，并实际完成1000次短检查。

Apple工具链没有随附libFuzzer链接库，因此包内保留了LLVM 14.0.6所需的未修改运行时源码、原许可证和逐文件SHA256；构建不需要联网，也不把该工具链接进正式应用。来源与许可见vendor/libfuzzer/UPSTREAM.json和LICENSE.TXT。原始记录见archive-fuzz-020.json与archive-fuzz-020.log；复现脚本的单独检查见archive-fuzz-reproduction-020.json。

方法参考：[LLVM官方LibFuzzer文档](https://llvm.org/docs/LibFuzzer.html)；源码版本：[LLVM 14.0.6发布](https://github.com/llvm/llvm-project/releases/tag/llvmorg-14.0.6)。
