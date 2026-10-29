# 依赖与算法来源

目录树格式、Huffman编解码、筛选和调度由本项目实现。密码封装和图形界面使用macOS系统库。

| 依赖 | 用途 | 来源与许可 |
| --- | --- | --- |
| Cocoa / AppKit | 原生图形界面 | macOS SDK |
| CommonCrypto / Security | AES-256-CBC、HMAC-SHA256、PBKDF2、SHA256和安全随机数 | macOS SDK |
| POSIX / C++17标准库 | 文件系统、线程和系统调用 | 系统开发工具链 |
| GoogleTest v1.15.2 | 单元测试 | BSD-3-Clause，许可证位于vendor/googletest/LICENSE |
| LLVM libFuzzer 14.0.6 | 归档解析器模糊测试 | Apache-2.0 WITH LLVM-exception，源码与许可位于vendor/libfuzzer |
| AVFoundation / CoreVideo / CoreMedia | 演示视频编码与解码检查 | macOS SDK，仅测试和演示工具使用 |

GoogleTest和libFuzzer不链接到备份程序。cpplint 2.0.2、clang-format 18.1.8用于代码检查与排版；Python用于测试和辅助脚本。

## UML模型

StarUML模型的视图数据结构参考官方staruml-samples项目。相关MIT许可证保存在scripts/LICENSE-StarUML-Samples.txt，提交包另随模型附带。模型中的类、用例、调用和布局按本项目组织。

## 发布工具

交付ZIP由Python标准库zipfile生成，软件备份使用自定义.sqbk格式。系统库及开发工具遵循其各自许可证。
