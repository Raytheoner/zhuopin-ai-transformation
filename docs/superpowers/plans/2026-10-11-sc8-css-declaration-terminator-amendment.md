# SC8 CSS 最后一条声明校验修订与单次核验续跑

状态：具体供审批件；未批准、未执行新生成器或 Browser。

## 已消费与根因

原计划 SHA 7292EDEDB14914732E16EDE38BC8AB70683E4106693B9A3FB0016C342A450CE4 已获本轮第3项A。原生成器 D8AF058410A5D121652C4C90FBA0BAD0DEC89518341F0232EFC2D3F3C14D3F97 单次 exit1，失败发生在创建输出目录之前，Browser未启动。固定24文件闭包及webapp/baoguan pin通过；white-space:nowrap 和 display:none 在批准的CSS中均为规则最后一条声明，紧接右花括号，旧校验正则只接受分号，造成误拒。

新候选生成器 SHA 8969D351060E2C5F1DCBEF8B26F9481D09E951E63A7226E1CB5112DF6499009C。修改仅两条正则末端：`nowrap\s*;`、`none\s*;` 分别改为 `nowrap\s*(?:;|(?=\s*\}))`、`none\s*(?:;|(?=\s*\}))`。仍只接受原属性/原值，规则结束右括号前可省分号；不放宽选择器、属性、值、闭包、CSS顺序或安全HTML断言。静态AST仅两字符串常量变化、其余AST结构相同；未调用候选生成器。

## 请求的精确新增批准

1. 冻结正式新执行件 `docs/superpowers/plans/sc8-local-css-verification-1011/generate_synthetic_home.py` 为上述8969…009C字节；原D8执行件原样保留。只授权新生成器再调用一次，不修改UI源码、不跑pytest。
2. 继续使用原未创建UUID `f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02`、原SC8 cwd、原隔离Python -B、原固定24项源pin及原最多六件路径。执行前原目录必须仍不存在且ignored；存在即停，不清理或改UUID。
3. 新生成器PASS后，沿原已批准计划的单次CUA代码做320×844和390×844本地file核验；只把expectedHelperSha256改为8969…009C，复用browser id2和原检查/截图/cleanup边界。不访问线上、接口、缓存/快照，不声称线上已修复。
4. 新一次生成或CUA任一失败原地保留停止；没有第三次生成/第二次CUA许可。批准补件另建，原已消费记录不覆写。

唯一生成命令：在 `C:/Dev/zhuopin-ai/4-数字员工/采购部/SC8-客户订单交期智能承诺` cwd，运行 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-local-css-verification-1011/generate_synthetic_home.py' --run-id 'f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02'`。

## 证据与复核

旧失败事实 reports/four-approvals-1011/start-amendments-177cccee-382f-4679-9569-6a0b730e38d0/failure-facts.json，SHA 0B5808615A9E4E313E438FB00FE9330D9CC65D8E7C37A8DB667B8C25C24CF2C2。独立静审必须核逐字节仅两正则变化、AST结构不变、声明末尾分号可省而其它声明值不放宽；只做静审，不运行生成器/Browser或产品测试。本修订正式计划形成后绑定其实际SHA，由Shao Peishen明确答A才消费。

## 正式供审登记

2026-10-11T07:42:30.1635680+08:00（上海）由根逐字节搬入上文独立静审版本；上文输入SHA 2BF4F7EE53A89C4C62244CBF7B7A52A35D41AF535BE1BA18E6F07BFA70F908E3；独立静审 reports\four-approvals-1011\start-amendments-177cccee-382f-4679-9569-6a0b730e38d0/sc8-independent-review.json，SHA 5D9802A98DB73E4E9975C43929FCE5576FE9FEE8C9CFC15C7C19414A04486D74，passed/findings=[]。本登记段仅补身份，执行范围未变。仍待本人明确批准。
