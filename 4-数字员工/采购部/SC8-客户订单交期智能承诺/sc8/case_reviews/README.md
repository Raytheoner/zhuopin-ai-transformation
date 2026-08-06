# 判例包定义目录（队列 #110 Feature B）

本目录存放判例批改法的"判例包"结构化定义，供 `.51` 保供看板网页表单
（`/cases/review/<package_id>`）读取渲染。**由 Cowork 起草**（现状判定/拟改判定
是业务判断），CC 只负责网页渲染与提交落盘（见 `sc8/case_review.py` 顶部说明）。

## 新建一个判例包

新建 `<package_id>.json`（package_id 建议用 `sc8-YYYY-MM-DD-议题简称`），格式：

```json
{
  "package_id": "sc8-2026-08-06-example",
  "title": "批X · 议题标题",
  "recipient": "姚祖怡",
  "cases": [
    {
      "case_no": 1,
      "scenario": "真实场景描述（可含脱敏后的料号/单号/客户）",
      "current_verdict": "现状判定（已建造上线的行为）",
      "proposed_verdict": "拟改判定（若判 ❌ 会改成的行为）"
    }
  ]
}
```

提交后专员链接固定为 `http://192.168.100.51:8091/cases/review/<package_id>`，
可直接经企微机器人私信发送。

## 🔴 硬设计约束（2026-07-28，队列 #143 加跑轮实证，不得放宽）

判例包网页表单不得只做结构化三选一——专员回件常夹带推翻整个功能的自由文本、
或全新问题，若表单只提供 ✅/❌/✏️ 三选一，这些内容会无处可填、直接丢失。故：

1. 每条判例的 ✏️ 自由文本与 ✅/❌ 独立记录（`note_N` 与 `verdict_N` 是两个独立表单
   字段，✏️ 非空 ≠ 改判）；
2. 表单末尾有不受约束的自由补充区（`supplement`），汇总时须与结构化选项同等
   重视、不折叠；
3. 支持一次提交内追加"新增问题"条目（`new_issues`，编号可跳出本次判例体系）。

## 提交去哪了

`reports/case_review_submissions.jsonl`（gitignore，含真实业务信息），每次提交
一条完整记录（package_id/respondent/responses/supplement/new_issues）。目前无
自动汇总/回灌机制——由领取到判例包结果的一方（通常是 Cowork）手工读取回灌，
详见跨桌任务队列 `#110`。
