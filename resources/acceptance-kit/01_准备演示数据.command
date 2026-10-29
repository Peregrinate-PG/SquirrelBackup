#!/bin/zsh
set -u
acceptance_package_root="${0:A:h}"
acceptance_target="$acceptance_package_root/验收数据-$(date +%Y%m%d-%H%M%S)-$RANDOM"
if ! command -v python3 >/dev/null 2>&1; then
  print '需要本机已有的Python 3。此工具不会自动安装软件。'
  read -r 'acceptance_pause?按回车结束：'
  exit 1
fi
python3 "$acceptance_package_root/tools/prepare_acceptance.py" "$acceptance_target"
acceptance_result=$?
if [[ "$acceptance_result" == 0 ]]; then
  print '\n准备完成。请用松鼠备份创建备份，再恢复到新目录。'
  print '完成后运行“02_核对恢复结果.command”。'
fi
read -r 'acceptance_pause?按回车结束：'
exit "$acceptance_result"
