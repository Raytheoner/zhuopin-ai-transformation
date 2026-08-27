# sweep-resident-hint-deploy-manifest Tasks

## 0. design 审（阻塞项，未过不得进 1.x）

- [ ] 0.1 Shao Peishen 过目 `design.md`，重点是**决策点 2**（部署清单在 Python 侧怎么承载：副本＋漂移守卫 vs 运行期解析 `.ps1`）与**决策点 3**（`deploy-server.ps1` 的文案要不要分档）
- [ ] 0.2 决策点 1（判据取部署清单）已于 2026-08-22 拍板，本步仅登记确认，无需再答
- [ ] 0.3 记录审查结论到本文件，未通过则改 design 后重审

## 1. 判据收窄（生产码）

- [ ] 1.1 `0-学习与工具/工具-落库sweep.py`：新增常量 `RESIDENT_SERVICE_DEPLOY_MANIFEST`（前缀 → 部署清单元组），`RESIDENT_SERVICE_PATH_PREFIXES` 改为由其键派生，不另写副本
- [ ] 1.2 `_touches_resident_service` 判据收窄：前缀命中后，取前缀之后的第一段，须落在该服务清单内；签名与 L2723 调用点不变
- [ ] 1.3 边界处理：路径恰等于前缀 / 前缀后为空串时判为不命中，不抛异常
- [ ] 1.4 在函数 docstring 内写明判据来源为 `sync-to-server.ps1` 的 `-AppFiles`，并指向本变更包与队列 §四 `#87` ⑶

## 2. 单测（反例优先）

- [ ] 2.1 **负判据**：批次在该前缀下只改 `CLAUDE.md` ⇒ 日志无「涉及常驻服务」、webhook 零投递（`B-0822_17` 最小复现）
- [ ] 2.2 **混合批次**：同批含 `CLAUDE.md` ＋ `aibot_service/*.py` ⇒ 提示照发
- [ ] 2.3 **非部署条目补充覆盖**：只改 `tests/` 下文件 ⇒ 不报（证明本包治的不止 `.md`）
- [ ] 2.4 **漂移守卫**：直读 `sync-to-server.ps1` 真身，正则取 `-AppFiles @(...)` 内全部双引号字面量，与 Python 常量比对为集合相等
- [ ] 2.5 漂移守卫**先断言解析到非空清单**再比对（防正则改坏后两侧同为空集而误绿）
- [ ] 2.6 既有两条用例（`aibot_service/foo.py` 报 / 目录外不报）复跑仍绿，语义不改

## 3. 回归与门禁

- [ ] 3.1 `0-学习与工具` 全量测试绿、零漂移
- [ ] 3.2 `openspec validate --all --strict` 全绿
- [ ] 3.3 队列结构 lint／引导样板 lint／凭据扫描三道既有门禁未回归

## 4. 收口

- [ ] 4.1 `/opsx:archive sweep-resident-hint-deploy-manifest -y`（tasks 全 [x] 后当场归档，不拖到下次 session）
- [ ] 4.2 ff 合入 master 并 push（`git rev-list --count master..<分支>` ＝ 0）
- [ ] 4.3 队列 §四 `#87` 回填：⑶ 销号；⑴ 一并销号并注明「派单时已完成，本次未重复实施，证据＝commit `d54abf2`／`c64a260` ＋ 现码 `_render_stock_backfill_pointer()`」
- [ ] 4.4 队列 §四 新立一行：「常驻服务部署提示的**漏报**面——改 `5-平台底座/zhuopin_platform/` 会影响常驻服务却不告警」，待总线派发
- [ ] 4.5 §二 待 commit 批次登记（文件清单须含队列文件自身）
