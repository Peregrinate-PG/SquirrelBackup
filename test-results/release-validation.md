# 发布验证

0.1.0 原生发布包完成以下检查：

- 从 ZIP 解压的 source 目录在没有 .tools 虚拟环境的情况下，使用随包 vendor/GoogleTest 离线 make all test 成功。日志见 final-offline-rebuild.log。
- 经 strip 去调试符号并重新签名后的 CLI 可执行 --version 与 verify，验证演示备份成功。
- 发布 .app 的 codesign --verify --deep --strict 检查通过。
- 发布 .app 内部业务动作测试通过 12 项断言，见 release-gui-selftest.json；真实点击和文件选择器仍待人工验收。
- 包内 SHA256SUMS 完整校验和 ZIP 外部校验通过。源代码历史 bundle 经 git bundle verify 验证为完整历史。

文档排版已渲染检查，未发现文字越界。PDF/HTML/Markdown 为同一内容的三种版本，不是原 Word 模板的直接填充副本。
