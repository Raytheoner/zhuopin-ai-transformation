---
title: 采购27与财务21业务草稿隔离渲染
version: v1
status: 待具体渲染例外确认；正文/Word已成件、尚未外发
---

# 两封业务草稿隔离渲染计划 · v1

## 1 已完成可审件

| 草稿 | 主件 | 冻结Word SHA256 |
|---|---|---|
| 采购27同一草稿修订 | 6-人才与组织/部门AI专员跟进/采购部-姚祖怡-跟进-2026-10-12-PC端MVP业务收敛.md/.docx | d25a079d4d53098e7928d1c36b8b7ca6cb3ce648e7fdd3647341cc9e4d52434a |
| 财务21新草稿 | 6-人才与组织/部门AI专员跟进/财务部-唐燕萍-跟进-2026-10-12-PC端MVP资料与阻碍收敛.md/.docx | 4d0f47507b324ea4633a26e4ddb928924cd28c8d64650b5ea432947e7c70198c |

两信决策点0，先归现有业务材料/处理记录，真实判例再确认规则；称谓核对0命中。采购新主件同步到原README目标文件，手机初稿快照保留；财务README正式登记21待审。当前均无对外发送授权。

## 2 能力证据及需确认原因

documents 26.1011.11113技能第474行要求只用bundled LibreOffice，禁止用户桌面LibreOffice。load_workspace_dependencies未提供bundled LO；本次canonical render_docx实际因`soffice.exe not found on PATH`退出1，未通过视觉核验。已只读核本机`C:/Program Files/LibreOffice/program/soffice.exe`存在。以前采购26的隔离渲染批准仅绑定那一封，本次不复用。

## 3 拟批准的具体例外范围

仅这两冻结Word，允许调用现有桌面LibreOffice绝对路径做headless PDF转换，之后使用bundled Python及已有Poppler生成逐页PNG并核每页。复制的canonical renderer从仓库可写reports运行；如需引导可执行文件，仅修改该子进程PATH，不修改系统/用户环境配置。所有输出、HOME以外的临时目录及LO专用profile放`C:/Dev/zhuopin-ai/reports/pc-mvp-1012/word-visual-<新UUID>/`，两个草稿分隔profile，防止复用现役LO进程；不安装、不升级、不改系统设置或原Word。只能清理本次UUID内临时profile，删除前核解析绝对路径在本次UUID根内；最终PDF/PNG、失败日志保留。若启动辅助进程则隐藏窗口，超时仅停止本次创建的进程。

完成每页视觉检查后，回读主件SHA确认原件未改，记录PDF页数/PNG落点。若有排版修正，只改这两草稿的排版并重新生成/称谓核对/逐页检查，保留初版及新SHA；采购旧目标路径同步相同新版。正文的业务范围、判据和外发未获新增批准。实际发送仍需另行明确“发”。
