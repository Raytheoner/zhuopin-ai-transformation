# zhuopin-lane-watch · 沿革

> `SKILL.md` §版本约定：正文只留当前版，历史沿革写本文件。

## 2026-09-02（`OP-0902-C`，v1.0 → v2.0，架构收敛重写）

- **背景**：本包（`OP-0902-B`）首版按「三模式并存」设计出件——`zhuopin-lane-clearpool`
  （人不在／零确认）、`zhuopin-lan-closeout`（人在／逐项串行）、本包（人在／停下等他）。
  同日 Shao Peishen 提出反问：「【offlan清池】这个我想改一下范围，我做这个动作 100%
  也在 loop 的，所以需要我决策不用绕过」——坐实清池「人不在」的设计前提写错了：清池是
  他手动触发的，触发那一刻他必然在场。前提一改，清池与本包的差别只剩网络范围，而那是
  机器跑一次探针就知道的。`OP-0902-B` 收到叫停指示，停手保全已完成的 §3 状态机核心，
  未擅自按新前提改写（详见队列 `#452` 该轮回写）。
- **架构收敛**：三个 workflow 收敛为两个——本包吸收 `zhuopin-lane-clearpool` 全部职能
  （D1 白名单／触碰区排波／看护件落档／心跳看护），该 skill 退休（description 改指
  向本包，见 `zhuopin-lane-clearpool/SKILL.md`）；`zhuopin-lan-closeout` 保持独立，
  专管 `.51` 部署与 LAN 留步（description 补边界指向，正本红线段未动）。
- **D1 新增第四档 ⏭️「不做，转出」**：`OP-0902-B` 初稿把 `.51` 部署列进 🟡（他答完就
  做），而 proposal 影响面与 D7 都写「本包不碰 `.51`」——二者矛盾。改法：`.51` 部署
  单独设档，命中即停下标注「须走 `zhuopin-lan-closeout`」、本包不执行，且**不进
  pause/resume 问答循环**（答案恒定，塞进问答只会制造不必要等待）。`工具-泳道看护
  状态机.py` 新增 `TIER_TRANSFER`/`TRANSFER_ACTIONS`/`transfer_out_lane()`/
  `transfer-out` CLI 子命令；`YELLOW_ACTIONS` 移除 `deploy_51` 并重新编号 ①-④，
  与 design.md D1 表逐字对齐。
- **3.5 新增 LAN 探针**：开跑先判 on/off-LAN 定候选范围——只读引用
  `0-学习与工具/工具-未闭合产出扫描.py::probe_lan`（不复制 ping/HTTP 判据代码），
  新增 `lan_status()`/`lan-status` CLI 子命令；`unknown`（探针没跑起来）与 `off`
  一律按 off-LAN 处理（fail-safe：宁可少做几项，不可对着不可达的内网瞎跑）。
- **5.6 新增波间看门狗（承接清池 2.3）**：`check_heartbeat()`/`check-heartbeat`
  CLI 子命令——心跳文件超过 30 分钟未更新即暂停等人，`tier` 标 🐕（看门狗），
  不进 `criteria` 现取的 D1 四档列表（管信号有无，不是动作分类）；已在 `paused`
  态的泳道不重复触发。D6 `summary` 同步新增「本批转出 N 项」一行（`build_transfer_
  summary`/`format_transfer_line`），与既有「本批停 N 次」并列输出。
- **5bis 承接 `lane-clearpool-skill` 变更包 4 项未完成**：2.1/2.2 已被本包 4.1/4.2
  覆盖（同一件事，不重复列）；2.3→本包 5.6（波间看门狗）；3.3→本包 5.7（队列 `#312`
  子项回写＋该包归档）。避免一个未归档的变更包连同其 skill 一起静默消失。
- **回归**：`test_工具-泳道看护状态机.py` 由 25 例增至 51 例，全绿；`criteria` 命令
  实测正确输出四档（🟢🟡⏭️🔴，🐕 不在其中）。
- **不改动**：D2 并发与排波、D3 失败处置、D4 停/续机制、D6 六要素基本形态、D7 首跑
  灰度上限 6 均未变——本轮只动 D1 表结构（三档→四档）与新增 3.5/5.6 两项能力。
