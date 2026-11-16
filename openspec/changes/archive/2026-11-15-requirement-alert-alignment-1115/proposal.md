## Why
11-15真实预警暴露四态已整理但sweep未消费、KH新包漏准入、全景只有场景存在性检查未绑定原队列及验收边界。
## What Changes
复用INDEX、原triage报告、既有lint与sweep，完成四态受守读取、全景逐场景队列映射与现时核查。只修机制，不改业务，不触碰1115KH产品/包文件/#670状态，不新增执行器/巡逻，不批量ACK/放宽阈值/自动合并删除。
## Capabilities
Modified: sweep-alert-lifecycle-guard。既有守卫保留，读取失败/内容漂移重新报；不新增gitignore规则，证据沿docs/codex原目录。
