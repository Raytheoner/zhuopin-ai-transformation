# 智能门户公共框架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `.agents/skills/executing-plans/SKILL.md`；本人选择分任务实施后使用 `.agents/skills/subagent-driven-development/SKILL.md`，派生模型显式 `gpt-6-luna`。按用户纯编号偏好执行步骤。本件待正式实施审核，不自动开始代码改动。

**Goal:** 在既有静态门户中实现批准的浅色公共框架、六部门入口和场景检索，保持原业务链接及销售脱敏数据能力。

**Architecture:** 保持单文件部署形态；JS模型的开发源单独保存，打包时内联进原HTML。场景服务、serve.py、门禁和网关不改变。未接入的待办/统一复核页面给出说明与返回，不复制模拟执行。

**Tech Stack:** 原生HTML/CSS/JavaScript、Node内置test、现有Python隔离环境及浏览器；无新增运行依赖。

**Spec:** 本目录 `2026-10-08-portal-ui-rollout.md` 及设计目录 `审核说明与统一UI规范.md`。以批准效果图P02/P03/P06/P07–P12/M01和设计变量为视觉基线。

## Global Constraints

1. 仅仓内实施；无ff、.51部署、启用、外发、真实取数、上传或重算授权。
2. 单文件可由8092服务托管，不改变SSO/cookie/API/权限，网关业务收编另审。
3. 不以原型模拟数字替换销售真实脱敏源；数据时间与失败状态明确；已有入口保留。
4. UI不得新增业务写请求；未知/未接入能力不显示模拟签认成功。品牌先用“卓品智能”文字。
5. 1440×1024、390×844，补320和1024检查；长中文可换行，表格容器滚动，所有控件有键盘焦点。
6. 场景阶段采用库内确认事实，不预判生产健康；服务健康、技术验收、业务验收分开。
7. 本任务按批准隔离树实施，不改主仓业务代码；不动原SC8隔离树。

## Review Focus

1. 中文带空格检索/无匹配：返回正确结果或可重置的空态，任务1、3测试。
2. 规划/待确认/未接入：无模拟业务提交，任务1、2检查。
3. 销售fetch失败：快照明示失败与源日期，不显示“实时”，任务3检查。
4. 隐藏侧栏/未知hash：焦点恢复且可回首页，任务2、4检查。
5. HTML样式文本和长中文：textContent显示原文不执行，窄屏不整页溢出，任务2、4检查。

## 文件边界与接口

根相对基目录 `1-转型规划/AI运营指挥中心/`，以下路径相对于它。

| 文件 | 动作与责任 |
|---|---|
| `AI运营指挥中心-框架原型-v0.1.html` | 更新展示与导航，内联模型，保持现有销售DOM锚点和数据源 |
| `ui/portal-model.mjs` | 新建纯函数：检索、hash解析、数据时态；不请求网络 |
| `ui/apps.json` | 新建入口清单；保持实际服务路径，规划项href=null |
| `ui/portal-theme.css` | 新建批准设计变量与公共组件样式；最终内联HTML |
| `scripts/inline-portal-ui.mjs` | 新建确定性内联构建，只替换有明确标记的模型/样式，不碰业务数据 |
| `tests/test_portal_model.mjs` | 新建纯模型用例 |
| `tests/test_portal_ui_contract.py` | 新建静态HTML契约，避免引入浏览器测试包 |
| `UI设计评审-2026-10-07/实施证据/公共框架-验收.md` | 实施后记录定向命令、浏览器证据和Lunareview；不预填通过 |

消费：现有入口和同源 `data/sales_dashboard_data.json`。产出：`parseView(hash): string`、`filterApps(apps,{query,department}): App[]`、`salesState({ok,syncTime}): {label,sourceTime}`；App=`{id,name,department,stage,href}`，href为字符串或null，stage描述能力阶段而非健康状态。

## 任务1：入口清单与纯模型

1. 在上述模型测试文件加入以下最小行为用例，再执行Node测试，确认缺模块失败而非路径错误。

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import {parseView, filterApps, salesState} from '../ui/portal-model.mjs';
test('未知路由与中文组合检索', () => {
  assert.equal(parseView('#unknown'), 'overview');
  assert.equal(parseView('#quality'), 'quality');
  const apps = [{id:'sc8',name:'SC8 客户订单交期',department:'采购',stage:'试用',href:'http://192.168.100.51:8091/'}];
  assert.equal(filterApps(apps,{query:'  SC8  交期 ',department:'采购'}).length,1);
  assert.equal(filterApps(apps,{query:'无匹配',department:'采购'}).length,0);
});
test('销售加载失败与缺少时间不能标实时', () => {
  assert.deepEqual(salesState({ok:false,syncTime:'2026-06-25'}),{label:'加载失败 · 历史快照',sourceTime:'2026-06-25'});
  assert.equal(salesState({ok:true,syncTime:null}).label,'更新时间缺失');
  assert.equal(salesState({ok:true,syncTime:'2026-10-07T16:00:00+08:00'}).label,'已加载 · 请核对更新时间');
});
```

2. 在隔离树内基目录执行 `node --test "tests/test_portal_model.mjs"`；首次预期ERR_MODULE_NOT_FOUND指向ui/portal-model.mjs。不要创建新package.json或安装包。
3. 写入以下完整纯模型，重跑同一命令，预期全部用例通过。

```js
const views = new Set(['overview','apps','tasks','review','system','procurement','quality','finance','sales','operations','engineering']);
export function parseView(hash) {
  const value = String(hash || '').replace(/^#\/?/, '');
  return views.has(value) ? value : 'overview';
}
export function filterApps(apps, {query = '', department = '全部'} = {}) {
  const words = query.trim().toLocaleLowerCase('zh-CN').split(/\s+/).filter(Boolean);
  return apps.filter(app => (department === '全部' || app.department === department)
    && words.every(word => `${app.id} ${app.name} ${app.department}`.toLocaleLowerCase('zh-CN').includes(word)));
}
export function salesState({ok, syncTime}) {
  const sourceTime = syncTime || '来源未提供更新时间';
  return {label: !ok ? '加载失败 · 历史快照' : !syncTime ? '更新时间缺失' : '已加载 · 请核对更新时间', sourceTime};
}
```

4. apps.json按现有路径登记SC8 `http://192.168.100.51:8091/`、QD-B `http://192.168.100.51:8093/`、SC2 `http://192.168.100.51:8096/procurement/sc2/`、Q2 `http://192.168.100.51:8098/`；FI2/FI3保留8094/8097既有入口并显示需求待确认。招聘等旧门户已有入口须先逐项提取，不能丢失；新规划项href=null。入口清单不代表当次在线核验。
5. 独立审查入口差异表与模型测试；按官方锁登记本任务批次，不手工commit，不登记他线脏文件。

## 任务2：浅色壳层与导航

1. 静态契约测试用标准库HTMLParser收集id/链接，在 `tests/test_portal_ui_contract.py` 写入以下断言。新增标记前应失败。

```python
from pathlib import Path
from html.parser import HTMLParser
ROOT = Path(__file__).resolve().parent.parent
class Elements(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = []; self.links = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'id' in values: self.ids.append(values['id'])
        if tag in ('a', 'iframe'):
            self.links.append(values.get('href', values.get('src', '')))
def test_portal_keeps_business_entry_and_unique_ids():
    html = (ROOT / 'AI运营指挥中心-框架原型-v0.1.html').read_text(encoding='utf-8-sig')
    parser = Elements(); parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids))
    for view in ('overview','apps','tasks','review','system','procurement','quality','finance','sales','operations','engineering'):
        assert 'view-' + view in parser.ids
    for url in ('http://192.168.100.51:8091/', 'http://192.168.100.51:8093/', 'http://192.168.100.51:8094/'):
        assert url in parser.links
    assert 'data/sales_dashboard_data.json' in html
    assert 'PORTAL_UI_MODEL_BEGIN' in html
```

2. 在基目录执行 `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "tests/test_portal_ui_contract.py" -q`；预期新增视图/标记断言失败。原有链接和销售锚点是必须保持的回归条件。
3. 以批准styles.css和设计变量为参照，在portal-theme.css建立公共样式；其起点为：

```css
:root{--brand:#1677ff;--action:#126bd9;--text:#18253b;--secondary:#63738b;--canvas:#f5f8fc;--surface:#fff;--border:#e7edf5}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--text);font:14px/1.6 'Microsoft YaHei','Segoe UI',sans-serif}
button,input,select{font:inherit}button,a,input,select{touch-action:manipulation}
:focus-visible{outline:3px solid var(--brand);outline-offset:3px}
.view{display:none}.view.active{display:block}
.content{min-width:0;overflow:auto}.table-scroll{max-width:100%;overflow-x:auto}
.department-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.card{min-width:0;overflow-wrap:anywhere;border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:20px}
@media(max-width:760px){.department-grid{grid-template-columns:1fr}.content{padding:17px}.sidebar:not(.open){visibility:hidden}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
```

4. 更新原HTML侧栏/顶栏/首页/部门/应用目录，保持salesKpis/salesFunnel/salesScore/salesTopCust/salesRisk/salesBadge/salesSync和采购iframe。使用真实button及label；JS填入来源文字时用textContent。创建 `view-tasks` 与 `view-review`，仅显示“尚未接入统一接口，业务处理请进入原场景”及返回入口，不创建决定提交按钮。
5. 调整 `go(view)`：调用parseView，同步hash、active与aria-current、标题及面包屑，未知hash回overview；不得使用未经清洗的hash拼接innerHTML。导航测试新增重复点击、hashchange和浏览器后退实际验证。
6. 在HTML中加入 `<!-- PORTAL_UI_MODEL_BEGIN -->`/`<!-- PORTAL_UI_MODEL_END -->` 和 `<!-- PORTAL_UI_THEME_BEGIN -->`/`<!-- PORTAL_UI_THEME_END -->` 两对独占标记。以下脚本保存为 `scripts/inline-portal-ui.mjs`，在基目录执行 `node "scripts/inline-portal-ui.mjs"`。开发源不是生产远程资源。重跑静态契约及模型测试。

```js
import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const file = path.join(root, 'AI运营指挥中心-框架原型-v0.1.html');
let html = await readFile(file, 'utf8');
for (const [name, source, tag] of [
  ['MODEL','ui/portal-model.mjs','script'],
  ['THEME','ui/portal-theme.css','style']
]) {
  const begin = `<!-- PORTAL_UI_${name}_BEGIN -->`;
  const end = `<!-- PORTAL_UI_${name}_END -->`;
  if (html.split(begin).length !== 2 || html.split(end).length !== 2 || html.indexOf(begin) >= html.indexOf(end)) {
    throw new Error(`内联标记缺失、重复或次序错误：${name}`);
  }
  let body = await readFile(path.join(root, source), 'utf8');
  if (name === 'MODEL') body = body.replace(/^export /gm, '');
  if (body.toLowerCase().includes(`</${tag}`)) throw new Error(`源文件含提前结束标签：${name}`);
  const start = html.indexOf(begin) + begin.length;
  const finish = html.indexOf(end);
  html = html.slice(0,start) + `\n<${tag}>\n${body}\n</${tag}>\n` + html.slice(finish);
}
await writeFile(file, html, 'utf8');
```
7. 按P02/M01参考截图检查间距、浅色层级、六部门和中文字体。独立审查后登记任务批次，不能把CSS通过作为业务上线通过。

## 任务3：检索、现有数据与状态

1. 添加部门过滤/中文无结果测试，以及salesState失败、成功但无sync_time的模型用例；模型只消费文本，不捏造新KPI。重跑任务1的完整测试命令。
2. 将检索结果通过DOM createElement/textContent渲染；href=null呈现规划标签，财务需求待确认加就近说明，旧真实入口保持链接。检索按钮可Enter提交，重置恢复全部。
3. 替换现有销售静默catch：失败保留现有历史展示但将salesBadge置为salesState({ok:false,syncTime:原快照日期}).label，同时salesSync写明来源日期；成功也不标“实时”，按数据sync_time显示。未知时间标缺失，不使用本机时钟填来源时间。
4. 浏览器只拦截本地同源销售请求来验证成功、失败及无sync_time；不访问生产销售库、不调用同步脚本。缺数据和请求失败分别表达。
5. 系统页三列分别为运行状态、技术验收、业务验收；没有可追溯证据则显示未接入，不复制原型绿色数字。独立审查后登记批次。

## 任务4：响应式与键盘

1. 浏览器检查1440×1024/1024×768/390×844/320×844，记录scrollWidth≤clientWidth（表格容器自身允许横滚）。使用长中文应用名、很长来源文本与 `<img src=x onerror=alert(1)>` 字符串检查DOM纯文本及布局。
2. 在现有openDrawer上同步hidden/inert或等价focus隔离、aria-expanded；移动时Escape/遮罩/点导航关闭，返回触发按钮；PC常驻侧栏不误设inert。底部导航aria-current与hash一致。
3. 用Tab/Shift+Tab/Enter/Escape走完整导航与检索；隐藏侧栏无焦点停留，空结果可重置。复核占位没有模拟成功或实际POST。
4. 保留长表格滚动容器；检查移动文字、触控区域不小于44px、prefers-reduced-motion；截图对照批准P02/P03/M01。
5. 将发现、修复及对应回验写实施证据，未检查实际企微WebView不写已验收。独立审查后登记批次。

## 任务5：定向验收、review与发布准备

1. 仅执行以下命令，不跑根矩阵、业务fixture或真实服务操作：

```powershell
node --test "tests/test_portal_model.mjs"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "tests/test_portal_ui_contract.py" -q
git diff --check -- "1-转型规划/AI运营指挥中心"
```

前两条在基目录执行；diff在隔离树根执行。各命令必须独立确认退出0。若serve.py/门禁未改，不为此次静态改版重跑既有HTTP服务测试；发现实际认证回归再查相应子项目测试。

2. 核对打包后的单文件不依赖外置mjs/CSS、无新增业务POST/PUT/DELETE、无原型DEMO审计或模拟提交；所有旧入口和销售数据契约有对照证据。
3. 在本人批准的执行方式内安排显式gpt-6-luna只读review，范围限本次diff与证据；不给业务矩阵/fixture权限。发现问题按严重程度修复并定向回验。
4. 生成发布申请，列明commit、服务8092、仅候选HTML字节及哈希、备份/回滚清单、当次门禁/销售/业务入口冒烟。不得直接执行sync-to-server.ps1，其销售同步和服务文件推送超出纯UI范围。
5. 官方锁回填#661与§二精确文件，释放后回读。未获ff/生产部署批准时停在发布准备；不将所有UI或机器人/队列全链标记完成。

## 自检结论

### 2026-10-08 已批准技术差异补充（差异处理：A）

授权：Shao Peishen已批准增量补齐，不另建技术设计；既有公共框架commit/ff/push及单HTML部署授权继续有效。测试通过直接commit，Sweep作为兜底；不强推、不删除数据、不扩展后端或其他场景范围。

1. 真实入口契约：Q2使用8098/quality/q2/，FI3使用8097/finance/fi3/。从各场景config.ROUTE_PREFIX及Blueprint首页读取契约；不导入场景引擎，不访问会触发评估/审计的mock首页。修改apps.json并重建内联HTML；新增定向测试须先失败再通过。
2. 需求与版本索引：总体架构依据2026-07-29统一门户架构决策件；UI依据2026-10-08整套审核结论；技术栈仍为原生HTML/CSS/JS与独立场景服务。正式总PRD版本指针尚未绑定，不能把历史Q2旗舰PRD当作当前判定规则；当前Q2以场景intent、规则注册表和已签认覆盖层为准。
3. Q2规则版本q2-v3.2-chenchen-2026-08-28+signoff-2026-09-14、L2；FI3规则版本fi3-v1-tangyanping-2026-07-10、L3且仍只给付款建议。QD-B保持EQQR8082 A2.1与现有评分/报告。未签认项、财务变更和AI建议不能由UI冻结或代签。
4. 发布前后核验未登录首页及销售JSON门禁、文件哈希、源/目标一致性、备份与回滚路径、服务PID/任务状态、登录后实际页面。直接8092的共享口令不能证明部门角色权限已完成；不扩大人员访问或敏感数据范围。网关可信身份头、销售路径服务端权限另列底座工作，不自动纳入本次UI。
5. 统一待办/复核/任务执行仍为未接入；SC8缓存刷新、重算、判例批改各自保持原接口含义。接口失败、数据时间和规则版本逐场景适配；QD-B错误堆栈、陈旧阈值与真实企微WebView在后续子计划处理。
6. 原冻结8文件及一次Luna审阅保留；320px修复为作者回验。此次路由补核为作者RED→GREEN验证，未追加独立review。新候选另存修订清单及ZIP，不覆盖原冻结字节。

入口模型类型与调用一致；五项Review Focus分别归属任务1–4；部署副作用被列为禁止直接执行项。批准设计的全部业务页面由总体计划分阶段承接。本技术计划只实施公共框架，业务渲染由独立子计划审核后执行。当前未开始任何上述代码任务或新增测试文件。
