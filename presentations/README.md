# 第3组答辩材料

第3组_松鼠备份_答辩.pptx是0.2.0的9页16:9可编辑演示稿，包含原生文本、表格、模块图、甘特图、实际应用截图和逐页讲者备注。配套PDF用于阅读，演示讲稿.md用于三分钟排练。中文字体为PingFang SC，换机器后需检查字体替换和实际放映。

视频video/松鼠备份_115秒演示.mp4为115.003秒、1440×1080的实际程序演示，含中文字幕，无音轨。后台定时调用生产按钮处理流程，直接渲染AppKit视图；不截取桌面，不移动鼠标，不操作系统选择器。13个实际事件、恢复比对及完整解码结果在test-results/gui-demo-evidence.json、gui-demo-events.txt和video-validation.json。视频包含演示目录路径与公开测试密码对应的密文，未使用个人工作文件。

## 重新生成

PPT使用托管的@oai/artifact-tool运行时生成：设置ARTIFACT_NODE_MODULES指向包含该包的node_modules，然后执行node scripts/build_presentation.mjs。默认输出在.preflight/ppt-build；PPT_BUILD_DIR可指定目录。构建结果是候选稿，仍需结构、渲染和人工逐页检查后放入本目录。

PDF使用scripts/render_presentation.sh，要求SOFFICE指向可用的LibreOffice命令行程序。脚本以独立配置目录无窗口转换，不启动桌面Office。导出成功不等于已在PowerPoint人工验收。

视频使用make gui-demo video-inspector；运行build/gui_demo /已存在父目录/新的演示目录，115秒左右生成MP4和JSON证据。再运行build/video_inspect /MP4绝对路径 /校验目录，完整解码并导出13张抽样帧。GUI运行需要图形登录会话，即使窗口不显示也受系统会话权限约束。

## 现场使用

三分钟讲稿、七分钟老师或助教操作步骤见docs/06_演示与答辩指南.md。三人职责按均衡安排，实际贡献和个人体会须本人确认。在线仓库和证书不包含虚构记录。持续运行测试状态只引用当前报告，尚未完成时不写通过。
