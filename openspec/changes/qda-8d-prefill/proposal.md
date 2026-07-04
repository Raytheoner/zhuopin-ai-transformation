# 变更提案：8D预填脚本（qda-8d-prefill）

> 交付对象：陈忱团队（质量部），8/1前
> 用途：8D历史库归集提速——AI按§1.1模板从8D原文预填录入表，陈忱只校对/改判，预计单份工时降一半。

## 需求背景（《质量旗舰开工就绪包》§1.5 + 2026-07-04纠正方案§二）

历史8D库结构化是Q2场景（10月入轨）的前置，陈忱团队需在8月底完成30-50份。
首批7份已人工完成，可作黄金基准；剩余23-43份若全人工效率低。
本工具让AI预填，陈忱只校对/改判，同时记录改判原因（反哺Q1标注语料，与l2-override-reason-capture机制一致）。

## 方案要点（设计替代design.md要点清单）

详见 `design.md` — 本变更含doc_parser架构评估，design需Paul审。

## 验收标准

- `python run_prefill.py --input sample.docx --output result.json` 可正常运行
- 12字段均有提取结果（低置信标注LOW，不静默）
- 脱敏建议输出token映射表（OEM-A-01/电容-A/某车型平台-A等范式）
- `python run_prefill.py --input sample.docx --golden golden.csv --report report.md` 生成字段命中率报告
- 测试全绿（含合成docx夹具）；真实docx/PDF不入库（gitignore）
