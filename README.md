# 松鼠备份 Squirrel Backup

面向 macOS Apple Silicon 的数据备份课程设计初版。C++17 实现业务核心，Objective-C++ 与 Cocoa 实现原生 GUI，提供可独立使用的命令行。

## 先运行

双击 `build/SquirrelBackup.app`。发布版本位于 `dist/SquirrelBackup-0.1.0-macOS-arm64/`，其中的 `.app` 可直接在本机打开。

```sh
make -j4 all
open build/SquirrelBackup.app
bash scripts/demo.sh
```

只需 macOS Command Line Tools。若尚未安装，系统可能要求用户运行 `xcode-select --install`；本机已经具备。无需 Homebrew、Qt、Python 后端或云账号。GUI 需要图形登录会话，命令行可独立使用。

## 命令行

以下源目录和目标父目录须已存在；备份文件与恢复文件夹都须尚不存在。恢复操作不合并已有目录。

```sh
./build/squirrel backup /路径/源目录 /另一位置/备份.sqbk
./build/squirrel verify /另一位置/备份.sqbk
./build/squirrel list /另一位置/备份.sqbk
./build/squirrel restore /另一位置/备份.sqbk /另一位置/新的恢复目录
./build/squirrel backup /路径/源目录 /另一位置/筛选.sqbk --exclude '*.tmp' --name '*.txt'
./build/squirrel schedule /路径/源目录 /备份存储目录 --every 300 --keep 5
./build/squirrel watch /路径/源目录 /备份存储目录 --poll 2 --keep 5
```

加密使用环境变量读取密码，避免出现在命令行参数中。在 zsh 中可先用 `read -rs 'SQUIRREL_PASSWORD?备份密码：'`，再执行 `export SQUIRREL_PASSWORD`。备份、验证、还原时追加 `--password-env SQUIRREL_PASSWORD`，结束后 `unset SQUIRREL_PASSWORD`。环境变量仍可能被同权限的进程检查；GUI 密码框更适合普通演示。密码丢失无法恢复。

`--help` 列出路径、文件名、类型、时间、大小、UID 六类筛选参数。多条筛选按 AND 组合；排除规则优先，排除目录会剪枝。目录作为结构节点始终保留，符号链接不跟随。

## 开发与测试

```sh
bash scripts/bootstrap.sh
make test
make sanitize
bash scripts/bootstrap.sh --docs-tools
make lint
make fuzz
python3 tests/benchmark.py build/squirrel
.tools/venv/bin/python scripts/build_docs.py
make package
```

测试框架仅供开发：当前工作区已经准备好 GoogleTest；发布源码内附 vendor 副本，`make test` 可以离线运行。文档和 lint 工具为可选开发依赖，首次安装需要网络。VS Code 构建与测试任务已提供，LLDB 启动配置需要另装 CodeLLDB 扩展；也可直接使用终端 `lldb build/squirrel`。

## 文档与提交

- `docs/01_需求分析说明书.md`：编号需求、用例、约束和规划。
- `docs/02_系统设计文档.md`：真实类设计、格式和算法、动态流程。
- `docs/03_软件测试报告.md`：自动生成的真实测试结果及验收边界。
- `docs/04_StarUML绘图指导.md`：手工绘图步骤、元素与关系清单，不包含 UML 图。
- `docs/05_实验报告.md`：按给定模板栏目整合；姓名学号等保留待填写。
- `docs/06_演示与答辩指南.md`：演示步骤、讲稿、提交清单。
- 同目录 `html/`、`pdf/` 为阅读及打印版本；测试证据位于 `test-results/`。

## 初版边界

支持普通文件、空目录、软链接、硬链接、FIFO，以及权限、atime/mtime 纳秒时间、UID/GID 记录和 xattrs。不同属主恢复可能无权限，会记录警告；不支持设备节点、socket、ACL、文件 flags 和创建时间。去掉 setuid/setgid/sticky 位以避免恢复特权权限。

定时与实时任务只在应用或进程运行期间有效，轮询按元数据判断变化，连续变化会延迟；不保证捕获保留相同元数据的内容替换。每个任务独立目录，淘汰只作用于本次任务已生成的快照。网络、增量、断点续传与开机自启没有实现。

临时数据写在 0700 私有目录，文件为 0600，正常异常路径会清理；不承诺 APFS 上的安全擦除。备份文件是完整性校验和加密后的格式，未加密的 SHA256 只检测损坏，不抵抗主动篡改者重新计算摘要。

GUI 已编译和签名，三个页面通过离屏渲染检查，内部业务动作测试通过 12 项断言；自动点击权限未获准，因此文件选择器及实际点击操作需人工复核。当前通过的核心自动测试不代表已完成所有产品验收。详细限制见测试报告。


## GUI 内部验证

`SquirrelBackup.app/Contents/MacOS/SquirrelBackup --render-preview 输出目录 页面编号` 可在图形登录环境导出指定页面的 PDF（页面 0、1、2）。`--self-test 新测试目录` 可运行不显示窗口的业务动作测试，结果输出为 gui-selftest.json。该测试不操作其他应用，不验证真实文件选择器与鼠标点击；沙箱限制 AppKit 初始化时需要允许本地测试进程访问图形会话。离屏预览见 docs/screenshots。
