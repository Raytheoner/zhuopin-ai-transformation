# skill 归属正本（队列 #585，2026-09-16 立）

> 判据：**CC 执行的 skill** 以仓库 `.claude/skills/<名>/` 为唯一正本（随仓库走、CC 泳道自动可见）；**Cowork 执行的 skill** 以本目录 `0-学习与工具/skills源码/<名>/` 为源码正本，Cowork 账号级安装目录为安装版（源码↔安装版同步纪律见各 skill 自身 SKILL.md，不同 skill 写法不一，不在本表统一）。

| skill | 归属 | 说明 |
|---|---|---|
| `zhuopin-lane-watch` | Cowork | 泳道看护模式（吸收 `zhuopin-lane-clearpool`） |
| `zhuopin-lan-closeout` | Cowork | 回 LAN 一句话收口，专管 `.51` 部署与 LAN 留步 |
| `zhuopin-send-followup` | Cowork | 跟进信一句话发送器 |
| `zhuopin-kickoff-prompt` | Cowork | 交接/转场开场 prompt 生成器 |
| `zhuopin-rebaseline` | Cowork | 全景路线图重组循环执行清单 |
| `zhuopin-需求grill` | Cowork | 新场景开工前需求收敛第一道把关 |
| `zhuopin-queue-audit` | Cowork | 跨会话对账审计。🆕 **本次（#585）盘点补入**——队列 #585 立行时的枚举漏计了本 skill（源码目录客观存在，但未列入原定 6 条 Cowork 清单），依"以文件系统真身为准"补齐，无归属分歧、不改变结论 |
| `zhuopin-followup-letter` | CC | 建造类，CC worktree 会话内调用过（统一门户设计 worktree 1 次）。**已迁**至 `.claude/skills/zhuopin-followup-letter/`（`git mv` 保留历史，#585 续三 OP-0916-O 执行），本目录不再有该 skill |
| `huijian-chaijian-patrol` | 不安装 | 正文由 `check_patrol_signal.py`／调度 Dispatch 直读源码，不走 Cowork `save_skill` 或 CC `.claude/skills/` 安装机制 |
| `zhuopin-lane-clearpool` | 已退休·已下架 | 2026-09-02 `OP-0902-C` 被 `zhuopin-lane-watch` 吸收；Shao Peishen 已于 2026-09-16 在 Cowork 手动关闭（§四 `#204` 销）。**历史记录不追改**：其 SKILL.md description 原文（含已归档说明）按项目纪律保留不压缩 |

## 续棒（#585 第二棒，2026-09-16 `OP-0916-M`）已做

- ✅ `0-学习与工具/skills源码/*/SKILL.md` description ≤200 字压缩 ＋ 触发词对照表已完成（7 个文件：`huijian-chaijian-patrol`／`zhuopin-followup-letter`／`zhuopin-lan-closeout`／`zhuopin-lane-watch`／`zhuopin-queue-audit`／`zhuopin-send-followup`／`zhuopin-需求grill`）。压缩前后逐条触发词对照表写回队列 §一 `#585`；被压缩掉的机制细节一律以「触发与机制细节」段原文迁入各文件正文首段，不丢信息。

## 续三（#585 续三，2026-09-16 `OP-0916-O`）已做

- ✅ `zhuopin-followup-letter` `git mv` 迁移至 `.claude/skills/zhuopin-followup-letter/`（保留历史）＋全仓引用改点：仅改「当下生效的指针」（openspec 未合入变更包 `followup-decision-point-gate` 的 tasks.md／proposal.md 两处未来路径、skill 自身脚本内的用法示例路径、本 README 归属表与未完成事项）；历史叙事件（CHANGELOG／队列归档／队列行日志／看护件／取证件／session 接力归档／队列 §二 批次历史）依「历史记录不追改」原样不动。

## 本表之外未完成事项（#585 续三交接，2026-09-16）

- `工具-仓库外载体扫描.py` 载体③ 拆分（CC 侧库内即正本免扫／Cowork 侧账号级安装路径先取证、取不到输出"未核验"）未做，单测三态覆盖未做。

详情与承接见队列 §一 `#585`。
