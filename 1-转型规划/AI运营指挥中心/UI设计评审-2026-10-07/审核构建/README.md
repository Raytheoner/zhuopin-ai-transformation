# 审核文档构建与渲染

build-word.py 从本目录上一级的screens及需求页面映射JSON生成同名Markdown和Word。使用Codex bundled Python/python-docx；不要在共享全局环境安装依赖。render-approved-word.py 使用已批准的仓内便携LibreOffice及managed documents renderer，仅在仓内.tmp输出QA。固定路径记录本次证据运行环境，迁移机器时先通过load_workspace_dependencies核对运行包路径。

最终交付来自word-render-1008-v4对应的同名DOCX。检查10页PNG已完成，渲染产物及哈希见Word渲染验证-2026-10-08.json。重建会覆盖审核文档，请按后续批准范围操作。
