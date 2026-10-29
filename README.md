# 松鼠备份 Squirrel Backup

软件开发综合实验第3组项目，版本0.2.0。使用C++17实现目录树备份与恢复，提供macOS原生界面和命令行两种入口。

## 构建与运行

开发环境：macOS 13.0、Apple Silicon arm64、Apple Clang 14.0.3。构建需要macOS Command Line Tools中的clang++、SDK和make。

```sh
make -j4 all
open build/SquirrelBackup.app
./build/squirrel --help
```

应用使用Cocoa/AppKit，密码封装使用系统CommonCrypto/Security。构建不需要下载运行库。GoogleTest随源码提供，Python 3用于运行集成测试。

## 功能

- 备份和恢复目录树，保留空目录、软硬链接、FIFO、权限、时间及扩展属性。
- 自定义归档、分块Huffman压缩、密码加密和完整性验证。
- 按路径、文件名、类型、时间、大小和UID筛选文件，支持排除规则。
- 定时备份、目录变化检测及任务内快照保留。
- 界面显示进度，支持取消、关闭时清理和表单参数记忆。

备份文件和恢复目录都须使用新路径，目标父目录须已存在。备份位置放在源目录之外。界面密码不写入偏好设置或日志。

```sh
./build/squirrel backup /路径/源目录 /另一位置/备份.sqbk
./build/squirrel verify /另一位置/备份.sqbk
./build/squirrel list /另一位置/备份.sqbk
./build/squirrel restore /另一位置/备份.sqbk /另一位置/恢复目录
./build/squirrel backup /路径/源目录 /另一位置/筛选.sqbk --exclude '*.tmp' --name '*.txt'
./build/squirrel schedule /路径/源目录 /备份存储目录 --every 300 --keep 5
./build/squirrel watch /路径/源目录 /备份存储目录 --poll 2 --keep 5
```

CLI通过`--password-env`读取密码。在zsh中输入：

```sh
read -rs 'SQUIRREL_PASSWORD?备份密码：'
export SQUIRREL_PASSWORD
./build/squirrel backup /路径/源目录 /另一位置/加密.sqbk --password-env SQUIRREL_PASSWORD
unset SQUIRREL_PASSWORD
```

恢复加密备份时使用同一选项。密码由用户保存，程序没有找回功能。

## 源码结构

| 路径 | 职责 |
| --- | --- |
| include/squirrel/backup.h | 公共类型和服务接口 |
| src/scanner.cpp | 目录扫描、筛选与元数据读取 |
| src/archive.cpp | 树记录编码、解析和文件恢复 |
| src/huffman.cpp | 分块Huffman编码与解码 |
| src/crypto.cpp | 密码派生、加密和完整性认证 |
| src/service.cpp | 备份、检查和恢复流程 |
| src/scheduler.cpp | 定时、变化检测与快照保留 |
| src/cli.cpp | 命令行参数和命令执行 |
| src/gui*.mm、src/gui*.h | 应用入口、界面布局、控制器和辅助函数 |
| tests/ | 单元、集成及界面测试 |
| vendor/ | 测试依赖及其许可证 |

## 测试

```sh
make test
make sanitize
make lint CPPLINT=/本机工具目录/cpplint
make format-check CLANG_FORMAT=/本机工具目录/clang-format
./build/SquirrelBackup.app/Contents/MacOS/SquirrelBackup --self-test /已存在父目录/新测试目录
```

`make test`执行52项单元测试、21项CLI集成测试、18项异常归档与并发测试、6项工作流回归。GUI自测单独执行53项断言，需要图形登录会话，以后台窗口检查控件状态和操作结果。

`make sanitize`对核心测试启用AddressSanitizer与UndefinedBehaviorSanitizer。`.clang-format`规定源码排版，`make lint`检查C++编码规范。测试输出写入`test-results`。

## 文件系统约定

恢复使用私有暂存目录，在检查成功后发布到新路径。普通文件分块处理；扫描期间保留文件列表与元数据。对源树进行备份前后检查，使用中的数据库等需要一致性的数据应先停止写入。

自动任务在应用或CLI进程运行期间执行，电脑休眠时暂停。变化检测通过轮询确认稳定状态。取消在工作单元之间响应，完成的备份保留。

UID/GID按原值记录；当前用户无权恢复属主或扩展属性时输出警告。权限和时间恢复失败会中止。支持范围为普通文件、目录、软硬链接和FIFO；遇到设备节点或socket时报错。强制终止可能留下私有暂存目录。

## 项目信息

组长：杨梦宇（2023150901002）；组员：郭畅（2023040904017）、李想（2023150901012）。

仓库：https://github.com/Peregrinate-PG/SquirrelBackup

依赖来源与许可证见`THIRD_PARTY.md`和`LICENSE`。
