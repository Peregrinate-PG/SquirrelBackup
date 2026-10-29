# 松鼠备份 Squirrel Backup

第3组软件开发综合实验项目，当前版本0.2.0。C++17实现备份核心，Objective-C++与Cocoa提供原生界面，同时提供命令行入口。

## 打开与构建

发布包根目录中双击SquirrelBackup.app；命令行运行./squirrel --help。支持macOS 13.0及以上的Apple Silicon，实际验证环境为macOS 13.0 arm64、Apple Clang 14.0.3。程序使用本地签名，未做Apple公证，其他电脑的启动需实测。

源码目录中执行：

```sh
make -j4 all
open build/SquirrelBackup.app
bash scripts/demo.sh
```

构建需要macOS Command Line Tools，无需Homebrew、Qt、Python后端或云服务。GUI需要图形登录会话；CLI可独立运行。发布源码附GoogleTest，make test可离线执行。

## 主要功能

- 目录树备份与恢复，保留普通文件、空目录、软硬链接、FIFO及声明范围内的元数据。
- 自定义归档、分块Huffman压缩、密码加密与完整性校验。
- 路径、文件名、类型、时间、大小、UID六类筛选，CLI完整提供，GUI提供常用项。
- 定时备份、目录变化检测、每个任务独立保留最近若干快照。
- 运行阶段与进度、协作取消、忙碌时关闭或退出清理、非密码设置记忆。

恢复目标必须尚不存在，程序不合并或覆盖已有目录。备份输出也必须是新文件。源目录和目标父目录须已存在。

```sh
./build/squirrel backup /路径/源目录 /另一位置/备份.sqbk
./build/squirrel verify /另一位置/备份.sqbk
./build/squirrel list /另一位置/备份.sqbk
./build/squirrel restore /另一位置/备份.sqbk /另一位置/新的恢复目录
./build/squirrel backup /路径/源目录 /另一位置/筛选.sqbk --exclude '*.tmp' --name '*.txt'
./build/squirrel schedule /路径/源目录 /备份存储目录 --every 300 --keep 5
./build/squirrel watch /路径/源目录 /备份存储目录 --poll 2 --keep 5
```

CLI密码通过环境变量传入。在zsh中先执行read -rs 'SQUIRREL_PASSWORD?备份密码：'和export SQUIRREL_PASSWORD，在备份、验证或恢复命令后加--password-env SQUIRREL_PASSWORD，结束后unset SQUIRREL_PASSWORD。环境变量可能被同权限进程读取；一般演示可直接使用GUI密码框。密码不写入设置或日志。

## 验证与复现

```sh
make test
make sanitize
bash scripts/bootstrap.sh --docs-tools
make lint
make fuzz
python3 tests/benchmark.py build/squirrel
python3 tests/signals.py build/squirrel /已存在父目录/新的信号测试目录
make gui-demo video-inspector
./build/gui_demo /已存在父目录/新的演示目录
./build/video_inspect /演示目录/松鼠备份_后台演示.mp4 /校验输出目录
```

GUI内部测试：build/SquirrelBackup.app/Contents/MacOS/SquirrelBackup --self-test /已存在父目录/新的测试目录。该模式不显示窗口、不读写用户偏好，不操作鼠标或系统选择器。后台演示同样调用真实按钮处理流程并渲染应用视图，不捕获桌面。

当前命名用例97项，GUI内部断言53项，兼容性4种组合，实际信号中断20种组合，分别统计。动态内存检查、随机输入与持续运行证据见docs/03_软件测试报告.md和test-results。持续运行状态按生成报告时的实际记录填写。

人工验收可用 `python3 scripts/package_acceptance.py /已存在父目录/新工具包目录` 生成辅助包。包内两个 `.command` 分别准备独立演示数据、核对实际恢复结果，另附操作单和空白真人记录表。核对覆盖内容、权限、软硬链接、FIFO及扩展属性；这不替代系统文件选择器和鼠标操作验收。工具自身12个正反例见test-results/acceptance-tools-020.json，不并入97项产品测试。

## 材料入口

| 文件 | 内容 |
| --- | --- |
| docs/01_需求分析说明书.md | 需求、用例、范围与有日期的计划 |
| docs/02_系统设计文档.md | 模块、真实接口、格式、算法与流程 |
| docs/03_软件测试报告.md | 本版结果、原始证据和验证范围 |
| docs/04_StarUML绘图指导.md | 7张可编辑UML图及打开、修改、导出方法 |
| docs/05_实验报告.md | 与Word主体一致的可编辑阅读稿 |
| docs/第3组_松鼠备份_实验报告.docx | 按课程原模板填写的Word报告，另附同名PDF |
| docs/06_演示与答辩指南.md | 三分钟讲解、七分钟操作及常见问题 |
| docs/07_三人分工与协作方案.md | 均衡主责、交叉复核与确认事项 |
| docs/08_提交前验收清单.md | 提交前尚需完成的具体检查 |
| docs/09_复核结论与后续安排.md | 原版问题、修订内容和后续安排 |
| docs/10_学习证书办理说明.md | 每人完成课程、实践与审核的步骤 |
| docs/uml/SquirrelBackup.mdj | StarUML模型，另附SVG、PNG和官方导出校验图 |
| presentations/第3组_松鼠备份_答辩.pptx | 9页答辩稿及讲者备注，另有PDF和讲稿 |
| presentations/video/松鼠备份_115秒演示.mp4 | 实际应用后台演示，含中文字幕，无音轨 |

组长杨梦宇2023150901002；郭畅2023040904017；李想2023150901012。身份信息已填，个人复核稿和均衡职责仍须本人确认。实验室名称、本人AI工具截图、学习证书、在线Git和课程在线分组信息由成员完成。

## 功能边界

权限、atime/mtime纳秒时间、UID/GID记录、xattrs按实现范围保存；异属主恢复可能因权限不足产生警告。不支持设备节点、socket、ACL、文件flags和创建时间；恢复时去除setuid/setgid/sticky权限位。

定时与变化检测只在程序运行期间有效，不是系统守护。变化检测采用元数据轮询与稳定判断，不能捕获两次观察之间产生又消失的变化。发布前复查能拒绝已测的源树变化，但不是文件系统原子快照。没有网络备份、增量备份、断点续传和开机自启。

取消在扫描、数据块、元数据和发布前检查停止标志；单次系统调用或密码派生完成后才能继续响应。未完成暂存会清理，已经发布的备份保留；强制终止和掉电不属于正常清理保证。临时目录0700、文件0600，不承诺APFS安全擦除。未加密摘要用于检测损坏，不能抵抗主动重算摘要。

课程第9讲要求PPT3分钟、现场操作7分钟、视频不超过2分钟；2026年11月18日23:59前由组长提交小组材料至成电慕课，证书每人单独提交。后续通知如有更新，以课程通知为准。
