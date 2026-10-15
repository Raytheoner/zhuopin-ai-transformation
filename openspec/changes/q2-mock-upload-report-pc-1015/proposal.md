## Why

质量部16反馈不能上传文件并取得判定报告。当前主仓Q2只有GET固定mock汇总；旧8A离线语义8文件明确不含Web/上传且Workflow仍busy=true，不能拿离线来源实现代替PC闭环。沿原#612提出独立合成切片，先接文件输入与可回读单份报告；现网是否同版本未核，不宣称已复现或修复生产故障。

## What Changes

- 显式MOCK JSON上传/示例下载、单份既有引擎结果、版本来源、受控报告回读/导出及异常路径。
- 复用EightDInput、VerdictEngine、PendingSemantic、已签规则和详情渲染；两项PENDING、L2、安全分流及黄金预期不变。
- 新入口默认deny；显式本机合成演示配置与可信注入权限共同启用。真实WORD/PPT/PDF、真实模型、专业改判/签发和生产另闸。

## Capabilities

### New Capabilities
- `q2-mock-upload-report`: 合成结构化8D文件输入、不可变单份报告及同对象审计回读。

### Modified Capabilities
无。已读`q2-portal-display`，其汇总/逐报告/空值/PENDING及展示责任合同保持。

## Impact

仅Q2内4产品/测试路径：新`q2_8d_verdict/mock_upload.py`、既有`q2_8d_verdict/webapp.py`、新`tests/test_mock_upload.py`、既有`tests/test_webapp.py`。不触#652旧8个semantic_offline路径、engine/config/规则/语义、QD-A、共享门户或机制。#661展示18/18已归档；实施前再核现时归属与源hash，不覆盖新写者。

获批后副作用仅仓库内`reports/q2-mock-upload-pc-1015/`独立tree、源/结果/pending/audit/JUnit和临时loopback演示。`sources/*.json`、`objects/*.json`、`audit.jsonl`、`.control/*.pending`实际`git check-ignore -v`均命中`.gitignore:59:**/reports/`。不安装依赖，不开常驻端口，不修改仓库外文件。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

尺度沿已签Q2判例与CRITERIA；两项PENDING不由上传片补齐。业务持有人沿intent为陈忱，backup待人事指派（Q2-G-04），不代指派。提取方法沿AI起草·专家批改/历史判例及L2改判累积；本片只验合成操作与工程合同，不产生新专业签认。

## 验收与晋档条件（强制，四档口径）

仍为档1 MOCK PC本机候选。真实解析/验收、专业签字、可信身份、门户及生产各有后续闸，不因本片升档。操作验收：下载合成示例→上传→单份报告→来源/规则版本/待人工说明→导出/audit回读；畸形/非mock/跨客户/C-D/权限或audit失败不报成功。工时/质量价值基线待陈忱实际使用确认，不填虚构节省率。本片不能销掉质量部16的真实文件使用诉求。
