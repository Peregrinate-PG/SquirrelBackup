#!/bin/zsh
set -u
acceptance_package_root="${0:A:h}"
python3 "$acceptance_package_root/tools/verify_acceptance.py" --interactive
acceptance_result=$?
read -r 'acceptance_pause?按回车结束：'
exit "$acceptance_result"
