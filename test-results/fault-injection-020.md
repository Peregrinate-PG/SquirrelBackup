# 写入故障与强制终止补测

2026年10月29日，在0.2.0的冻结CLI副本上执行24个补充场景，全部满足各自断言。结果独立于97项核心命名用例，也不替代仍在运行的20小时长测。原始结果为fault-injection-020.json，逐场景日志为fault-injection-020.log。

| 场景 | 明文与加密合计 | 实际检查 |
| --- | --- | --- |
| 打包、封装、解码或恢复写入返回ENOSPC | 8 | 返回失败，不发布目标；清理暂存，原备份未变 |
| 备份fsync返回EIO，备份发布返回EACCES | 4 | 不发布归档；原备份未变；同名目标可正常重试 |
| 恢复发布返回EIO，文件权限恢复返回EPERM | 4 | 不发布恢复目录；暂存清理，原备份未变 |
| 恢复写入出现一次EINTR或连续短写入 | 4 | 正常完成，恢复内容SHA256一致 |
| 备份或恢复期间实际发送SIGKILL | 4 | 未发布目标；原文件和原备份未变；同名重试成功 |

每种可处理故障结束后，都关闭故障注入，再用同一个目标名称重试，核对新结果。这样同时检查错误处理与下一次正常操作，避免只验证退出码。

强制终止另用256MiB文件，在观察到至少4MiB实际写入后发送SIGKILL。四次均留下权限为0700的私有暂存根目录，这是进程无法执行清理代码的结果。随后重试不会删除这些旧目录，也不会把旧目录当作成功备份。本轮测试结束后，由测试脚本清理自己创建的全部临时数据。

本轮没有占满真实磁盘，也没有切断电源。ENOSPC等错误由仅加载到测试子进程的动态库返回；SIGKILL是实际操作系统信号。结论适用于所列故障位置和输入，不能扩展为任意磁盘故障、断电持久性或所有元数据异常均已验证。

复现命令在项目根目录运行，最后一个参数必须是尚不存在的结果目录，所在磁盘需至少4GiB可用空间：

```sh
make cli
clang -dynamiclib -O2 -Wall -Wextra -Werror -mmacosx-version-min=13.0 \
  tests/fault_injection_macos.c -o build/fault-injection.dylib
python3 tests/fault_injection.py build/squirrel build/fault-injection.dylib \
  /已有父目录/新的补测目录
```

动态库只根据明确的测试目录前缀和目标后缀选择调用，并在stderr留下触发标记；没有触发标记的场景不能计为通过。测试不更改生产程序、系统设置或桌面输入。其Mach-O函数替换接口参考[Apple公开的dyld声明](https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld-interposing.h)。
