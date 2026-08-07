## 1. 摄取核心模块

- [x] 1.1 新建 `fi2/tax_export_ingest.py`：定义 `IngestDiagnostic`/`IngestResult` 等最小数据结构
- [x] 1.2 实现 Excel 解析：读取「信息汇总表」sheet，提取所需列，工作表缺失/字段缺失时明确报错
- [x] 1.3 实现已处理清单：sha256 内容哈希、JSON 存储、`is_processed`/`mark_processed` 函数
- [x] 1.4 实现 ap_no 反查：`resolve_ap_no(connector, digital_invoice_no)`——后 8 位查询 + suffix 客户端校验 + 去重到唯一 ap_no 集合
- [x] 1.5 实现 item_code 反查：`resolve_item_code(ap_lines, qty, untaxed_unit_price, tax_rate)`——含税单价换算 + 唯一匹配 AP 行项目
- [x] 1.6 实现编排函数 `ingest_directory(export_dir, ledger_path, connector, now=...)`：扫描→去重→解析→反查→产出行 + 诊断结果，未解析记录不写入产出物、写入诊断（含性能修正：同一发票号跨多行时 ap_no 反查按 digital_no 缓存，避免真实端点上对 182 行大票逐行重复发起网络请求——真实验证时首次触发超 2 分钟超时才发现，已修复）

## 2. CLI 入口

- [x] 2.1 新建 `scripts/ingest_tax_export.py`：命令行参数（导出目录/已处理清单路径/输出目录），复用既有 `ZpConnector.from_env()` 范式，并补 `.env` 自动加载（同 `run_fi2_web.py` 既有范式，供 `.51` 直接运行不依赖手工 source 环境变量）
- [x] 2.2 输出摘要（成功N条/未解析N条+逐条原因），比照 `dump_u9c_snapshot.py` 的输出风格

## 3. 单元测试（mock，不触网）

- [x] 3.1 Excel 解析正反例（含字段缺失/工作表缺失/空行跳过）
- [x] 3.2 已处理清单幂等（同内容跳过/同名内容变化重新处理）
- [x] 3.3 ap_no 反查正反例（唯一命中含全串/后8位两种存储形态、零命中、多命中歧义），含服务端 CONTAINS 语义噪声候选的过滤测试
- [x] 3.4 item_code 反查正反例（唯一命中、零命中含"多笔批次合并成一行"真实边界场景、多命中歧义）
- [x] 3.5 端到端编排：mock 全链路产出可写入 `invoice.csv` 的行、幂等重跑、未解析记录留痕不静默丢弃、文件级解析失败诊断、`write_invoice_csv` 追加写入
- 补充：新增 `ZpConnector.get_ap_lines_by_invoice_no` 连接器方法 + 3 个 mock 测试（平台库 `test_fi_connector.py`），供 `resolve_ap_no` 调用

## 4. 真实数据验证（真实门禁，同既有 `FI2_RUN_REAL=1` 范式）

- [x] 4.1 用真实 8 个导出样本 + 真实 `ZpConnector` 跑 `resolve_ap_no`：**8/8 唯一命中**，与已知真实 AP 单号（AP-2026070071/070036/070035/060073/060004/040083/2025120181/2026050057）逐一吻合（`tests/test_real_tax_export_ingest.py::test_real_ap_no_resolution_matches_known_ground_truth`）
- [x] 4.2 用真实数据跑 `resolve_item_code`：如实记录真实分布——40/198 唯一命中（约 20%），未命中集中在 sample_8（182 行的合并结算大票，AP-2026050057，151/182 未解析）；样本 1/3/4/5/6（正常大小发票）合计仅 6 行未解析、其余全部唯一命中（sample_2/7 100% 命中）。**不预设通过率，如实观察**（design.md 已登记的已知风险）
- [x] 4.3 用真实数据跑完整摄取，产出的 `invoice.csv` 接入 `FeedSource(data_source="u9c", invoice_sample_dir=...)`（直接调用，不经 `run.py`——`run.py` 从未接线 `invoice_sample_dir`，同 D19 现状，非本次范围）核实判定口径未受影响：`linked=40/orphaned=0`（ap_no 100% 有效，零孤立发票），报告正常产出（18 完全匹配/34 无发票支撑/12 数量金额不符，13 项价格超差告警）

## 5. 全量回归与收口

- [x] 5.1 FI2 全量测试套件跑通，零漂移：128 passed + 7 skipped（较改动前 +21：本模块 18 个 + 端到端场景验证，`match_engine.py`/`result_classify.py`/`price_check.py`/`recon_report.py`/`config.py`/`models.py`/`feed_source.py`/`webapp.py` 均未改动，字节级零 diff）
- [x] 5.2 平台底座测试套件跑通，零回归：262 passed + 1 skipped（+3，`get_ap_lines_by_invoice_no` 新增测试）
- [x] 5.3 部署 `.51:8094`：`sync-to-server.ps1` 推送成功（`fi2/`/`scripts/` 整目录含新文件、`pyproject.toml` 新增 `openpyxl` 依赖）+ 服务器 venv 手动补 `pip install openpyxl`（`sync-to-server.ps1` 不会自动重装依赖，仅 `deploy-server.ps1` 首次部署会——已登记，见场景 CLAUDE.md）
- [x] 5.4 `.51:8094` 冒烟三件套：`/api/ping` 200 ／ 首页（`X-Auth-Token`）200 ／ 真实 POST `/run`（mock）200 全链路渲染正常
- [x] 5.5 真实案例端到端复现（范围调整，如实记录）：**未改 `webapp.py`**（红线内不碰），故不涉及"面板展示"复现；改为在 `.51` 服务器本机（非笔记本、非本地拷贝）直接对真实 `D:\airead` 跑摄取 CLI，产出与本机验证完全一致（40 行解析成功，ap_no 100% 命中），并验证幂等（二次运行 0 新处理文件）+ 中文字段 UTF-8 字节级核验（`单位`="套" 字节 `e5a597` 正确，非乱码——仅 SSH 终端显示因编码差异呈现乱码，文件内容本身正确）
- [x] 5.6 更新场景 CLAUDE.md「部署状态」段
- [x] 5.7 起草跟进信（README 只写 `⏳ 待你审`），如实带上 item_code 反查歧义率发现
- [x] 5.8 commit + push，回写队列 #295／#249／#252，收工重跑文档台账
