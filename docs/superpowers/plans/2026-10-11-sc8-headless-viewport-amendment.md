# SC8：本地合成页面 headless 几何核验补充计划

状态：具体供审；尚未获本次 Node/Playwright API 启动批准，未运行浏览器、CLI或测试。CUA原失败为 create-local-tab/Error、viewports=[]，原因未知；该次不重试。

## 固定审批对象与唯一调用

正式计划目标 `C:/Dev/zhuopin-ai/docs/superpowers/plans/2026-10-11-sc8-headless-viewport-amendment.md`。正式脚本目标 `C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-headless-viewport-1011/sc8-headless-viewport.cjs`，SHA256 `7AA029A67418E3E4677DCB7105BB05CFDF2AC7CB07EF9F884C35869C91F615A4`。候选原字节登记后根再次核正式SHA；批准绑定该路径/字节。本次方法为 Node 命令启动 Playwright JS API；Q2授权不覆盖本任务。

获新明确A并绑定本正式计划、脚本SHA和直接人批证据后，根仅调用一次：

```powershell
if ($env:NODE_OPTIONS -or $env:NODE_PATH -or $env:NODE_REDIRECT_WARNINGS) { throw 'Inherited Node injection/output environment requires separate review; stop without clearing it' }
if ((Get-FileHash -LiteralPath 'C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-headless-viewport-1011/sc8-headless-viewport.cjs' -Algorithm SHA256).Hash -cne '7AA029A67418E3E4677DCB7105BB05CFDF2AC7CB07EF9F884C35869C91F615A4') { throw 'Formal script SHA drift; stop before Node' }
& 'C:/Users/Paul Shao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-headless-viewport-1011/sc8-headless-viewport.cjs'
```

工作目录 `C:/Dev/zhuopin-ai`。失败保留并停止，不换UUID、不重试、不重生成输入、不复用旧CUA预算；必要sandbox启动提升只为本固定命令和下列副作用。

## 输入与运行时身份门

1. 固定已有合成目录 `reports/sc8-live-readonly-1010/local-css-f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02/`：mock-home.html SHA `EC0886DA76451CE5926BF858979BC38F635F43C9E2BE2A65B176896BA1DA7106`；generator-manifest.json SHA `DA91BCC2078C6B3E0EBD08FAF6343AD87D3047652BDB16E2FDE8C3DCEC609283`；css-order-check.json SHA `CC668A173859ABC6BCC1F36FF2DAD1038C41B6EB8E70339A35989C84DC8B8604`。逐字节核SHA、manifest字段/来源pins/marker、CSS静态检查后才建输出。不得改输入。
2. 原八条件计划SHA `7292EDEDB14914732E16EDE38BC8AB70683E4106693B9A3FB0016C342A450CE4`；webapp/baoguan来源pins分别 `1CB27E63F548B72A6D36A69CB4FCB50158FA2B04B2C5F83716AEE8856286240E` / `19D443EA46BEA534FCC0469053D361883AE08D22FA802A75ACE8C4FBC0DCFBF9`。不导入或执行产品模块。
3. 脚本先确认正式自身路径与 process.execPath；Node v24.19.0 SHA `3602F2BB1A10F2CBAB4C36886218A33C1AB3DB87290E73B033C46C77147D0237`。Playwright及core包固定1.62.1，package.json/两index.js/cli.js逐SHA在脚本内固定校验，之后才require。完整路径及pins保留同目录runtime-identity-v3.json（v1历史记录不改）；新增index pins为 `4E98F65F0A9D9BCAB8CFFC0C5CFDD87FD3F5B0BE74FC494FF166A466B204CD44` / `A58FB2CEC4293E7DCF73C58A179898A4F3986666451A19DA4E731FA3AF63265B`。
4. Chrome `C:/Program Files/Google/Chrome/Application/chrome.exe` SHA `6849D2982038DE9F9489A7B3858F3B785B7FEC06A842C93C517281D21995C8CA`，启动前核SHA，启动后要求版本154.0.8037.98。任何身份不符停止；不安装、不刷新pin、不改全局配置。

## 浏览器操作与证据范围

headless、chromiumSandbox=true、非持久context、JavaScript禁用、serviceWorkers=block，deviceScaleFactor=1/colorScheme=light；分别320×844与390×844。只打开固定本地file URL，读取DOM geometry/computed style并各截图一次；不开链接、不抓正文/DOM snapshot、不读profiles/隐藏状态、不调用真实服务。

八项逐项必须true：local_file（协议file且实际URL精确）；nav_before_wrap；links_same_row(top差≤1)；no_page_horizontal_overflow；nav_horizontal_scroll(overflow-x auto)；nav_nowrap；brand_hidden；document_metrics_positive。额外要求实际window尺寸匹配。任一失败不报通过。

page.route只放行固定HTML与data URL，其他页面请求abort并计数；出现被阻断请求就停止。此计数仅为页面路由观察，不能据此宣称Chrome进程级零网络。启动使用原有 `--disable-background-networking` 等参数；不以该参数声称操作系统网络隔离。此项授权覆盖隔离本机Chrome正常启动；不主动请求任何业务地址或读取真实数据。

## 新UUID与副作用

固定新UUID `95a30c80-333f-4f81-bb9d-17c015ff1657`，输出根 `C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/playwright-headless-95a30c80-333f-4f81-bb9d-17c015ff1657/`，必须不存在。最终核验产物只有viewport-320.jpg、viewport-390.jpg、viewport-check.json，CreateNew写入；JSON记录inputs/runtime SHA、版本、两视口几何/八断言、JPEG SHA、page-route计数、输入未变、自有浏览器关闭及结束状态。

另列启动必要临时副作用：输出根内新建browser-temp子目录，仅本Node进程的TEMP/TMP指向该目录，且在require/launch之前设置；Playwright新建的临时profile/artifacts及Chrome子进程继承此范围。Playwright自身关闭时可删除自己新建临时目录；根不另递归删除，失败残留保留。此临时目录不属于三份验收产物，不能声称整个UUID只有三件文件。不开用户现有profile，不改用户环境变量。关闭仅由该脚本创建的context/browser；关闭失败写stopped，不能报complete。

## 审查与后续

v1未通过报告/身份记录保留；v2由根及独立Luna核四修。新方法和临时副作用需本补件明确A。推荐A：批准固定脚本一次启动和上述新UUID三产物/临时profile范围；B：保留停止。无pytest、产品修改、提交、ff、生产部署或现网修复宣称；#671保持partial，真实手机现网闭环另接已授权边界。

## v3 完整包身份与启动前检查

启动命令明确先拒绝非空NODE_OPTIONS/NODE_PATH/NODE_REDIRECT_WARNINGS，不清空既有配置；在Node启动前精确核正式脚本SHA。脚本在require前对Playwright和core目录的全部普通文件作只读树摘要，拒绝符号链接/非普通项；方法为按POSIX相对path排序、每行path TAB byte-length TAB uppercase SHA256 LF，再取UTF8摘要。Playwright62件树SHA F081C07ACD2DCE682F187DF71BED0E1DB63DB18F3346D351132A7A6CC8E7C68E；core111件树SHA 19A3BCFAC18B8596A419139C2C415D323EEC6298468B4245755A1C756E4A4C8C。原字节只读树清点证据package-tree-identity.json SHA BE772307ED76CE9CBB9D1C9320F50EF03849A71DDD362143FA7CA1D4D96E529E；清点不导入Node/Playwright或启动浏览器。阶段字段分别在创建自有输出/TMP、加载核验包之前更新。原v2未通过报告保留，v3修正需独立闭环后送新A。
