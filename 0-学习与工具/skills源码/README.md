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
| `zhuopin-followup-letter` | CC | 建造类，CC worktree 会话内调用过（统一门户设计 worktree 1 次）。**拟迁**至 `.claude/skills/zhuopin-followup-letter/`（`git mv` 保留历史）——**本次（#585 第一棒）尚未执行迁移**，仍在本目录，下一棒续做时以本行状态为准，不得假设已迁 |
| `huijian-chaijian-patrol` | 不安装 | 正文由 `check_patrol_signal.py`／调度 Dispatch 直读源码，不走 Cowork `save_skill` 或 CC `.claude/skills/` 安装机制 |
| `zhuopin-lane-clearpool` | 已退休·已下架 | 2026-09-02 `OP-0902-C` 被 `zhuopin-lane-watch` 吸收；Shao Peishen 已于 2026-09-16 在 Cowork 手动关闭（§四 `#204` 销）。**历史记录不追改**：其 SKILL.md description 原文（含已归档说明）按项目纪律保留不压缩 |

## 本表之外未完成事项（#585 第一棒交接，2026-09-16）

- `zhuopin-followup-letter` 迁移（`git mv` ＋ 全仓 grep 引用改点）未做。
- `工具-仓库外载体扫描.py` 载体③ 拆分（CC 侧库内即正本免扫／Cowork 侧账号级安装路径先取证、取不到输出"未核验"）未做，单测三态覆盖未做。
- `0-学习与工具/skills源码/*/SKILL.md` description ≤200 字压缩 ＋ 触发词对照表未做（已测得现状：`huijian-chaijian-patrol` 210／`zhuopin-followup-letter` 266／`zhuopin-lan-closeout` 327／`zhuopin-lane-watch` 631／`zhuopin-queue-audit` 212／`zhuopin-send-followup` 227／`zhuopin-需求grill` 205 字，均 >200；`zhuopin-kickoff-prompt` 132／`zhuopin-rebaseline` 138 已达标、`zhuopin-lane-clearpool` 383 因历史记录不追改而豁免）。经逐文件通读核实：以上 7 个待压文件的详细行为描述**已在各自正文中完整存在**，压缩描述字段不会丢失信息，只需保留触发短语＋极简摘要＋指向正文的指针。

详情与承接见队列 §一 `#585`。
