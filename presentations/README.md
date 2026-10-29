# 第3组答辩材料

第3组_松鼠备份_答辩.pptx是0.2.0的11页16:9可编辑演示稿，包含目录、原生文本与表格、架构图、归档示意、甘特图和实际应用截图。正文使用PingFang SC，数字与英文使用Avenir Next。配套PDF用于阅读，讲者备注与演示讲稿.md用于三分钟讲解。

课程六项必讲内容对应：第5页开发环境、Git与代码规范，第6页算法与系统库，第8页测试层次与工具，第9页模块职责，第10页版本回顾与基于Git记录的甘特图。讲稿共180秒，三人各60秒。PPT按成员要求进行结构检查和逐页导出检查，不再安排桌面放映。

视频video/松鼠备份_115秒演示.mp4为115.028秒、1440×1080的真实程序演示，含中文字幕，无音轨。后台调用生产按钮处理流程并渲染AppKit视图，演示数据放在“文稿/松鼠备份演示”。13个实际事件、恢复比对及完整解码结果在test-results/gui-demo-evidence.json、gui-demo-events.txt和video-validation.json。QuickTime实际播放及抽样帧检查见video-visual-qa.json。

## 重新生成

PPT使用托管的@oai/artifact-tool运行时生成：设置ARTIFACT_NODE_MODULES指向包含该包的node_modules，然后执行node scripts/build_presentation.mjs。默认输出在.preflight/ppt-build；PPT_BUILD_DIR可指定目录。构建结果是候选稿，仍需结构、渲染和人工逐页检查后放入本目录。

PDF使用scripts/render_presentation.sh，要求SOFFICE指向可用的LibreOffice命令行程序。脚本以独立配置目录无窗口转换，不启动桌面Office。导出成功不等于已在PowerPoint人工验收。

视频使用make gui-demo video-inspector；运行build/gui_demo /已存在父目录/新的演示目录，115秒左右生成MP4和JSON证据。再运行build/video_inspect /MP4绝对路径 /校验目录，完整解码并导出13张抽样帧。GUI运行需要图形登录会话，即使窗口不显示也受系统会话权限约束。

## 现场使用

三分钟讲稿、七分钟老师或助教操作步骤见docs/06_演示与答辩指南.md。三人职责按均衡安排，实际贡献和个人体会须本人确认。在线仓库和证书不包含虚构记录。桌面验收记录与后台视频记录分别保留。
