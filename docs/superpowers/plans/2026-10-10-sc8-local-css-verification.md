# SC8 本地合成主页 CSS / viewport 具体核验计划（待本人批准）

状态：根正式登记供审，尚未获执行批准。原草案保留；正式生成器为本计划指定 pack 原字节副本。未运行生成器、测试、服务或 Browser。

## 目的和证据边界

在当前固定源码上生成 script-free 的合成主页壳，静态核验 base/nav/portal CSS 的拼接顺序及移动规则，再由现有 Browser/CUA 对本地 file 做 320×844、390×844 两个 viewport 的只读渲染。仅回答“当前源码生成的 SC8 主页壳在本地浏览器里是否满足几何条件”。不判断 .51/线上部署版本，不触碰页面行为、接口、数据、算法、业务口径、发布或 UI 源码。

已有依据：`current-css-verification-plan.md` 和 `css-verification-review.md` 位于 `C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/`；复核要求本动作单独具体审批，静态生成器与 Browser 截图不由旧 Browser 现网查看授权覆盖。旧候选 UUID `3bc702b9-dc9b-48da-97f9-68e0b86da4d4` 不复用。

## 固定输入与批准范围建议

- SC8 cwd：`C:/Dev/zhuopin-ai/4-数字员工/采购部/SC8-客户订单交期智能承诺`
- 运行时：`C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`，使用 `-B`；不调用 pytest。
- helper：`C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-local-css-verification-1010/generate_synthetic_home.py`
- 唯一建议 run UUID：`f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02`。执行前须验证精确输出目录不存在且仍被 `reports/` 忽略；若存在或忽略状态不确定，停止，不换路径。
- 输出根：`C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02/`
- helper 固定源身份：`sc8/webapp.py` SHA-256 `1CB27E63F548B72A6D36A69CB4FCB50158FA2B04B2C5F83716AEE8856286240E`；`sc8/baoguan.py` SHA-256 `19D443EA46BEA534FCC0469053D361883AE08D22FA802A75ACE8C4FBC0DCFBF9`。任一不符即停止，不更新 pin。
- 项目模块级导入闭包（保守上界，含模块级条件导入）：helper 在导入任何项目包之前，按以下 24 个精确仓库相对路径计算 SHA-256，并与代码内 `EXPECTED_IMPORT_CLOSURE_SHA256` 全量相等校验；新增、缺失或任意一项变化均停止，不能自动刷新 pin。哈希值同时写入 `css-order-check.json` 与 `generator-manifest.json`，作为导入身份证据。

| 仓库相对路径 | SHA-256 |
|---|---|
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/__init__.py` | `EADE92315E89755BADE152D6AE068E4529E13D01706B708FD03AEF89A4BEFE39` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/alert_dispatch.py` | `C3A1EFD3880929F6BDCBBB4783DF70E540A73F914DB76A593B618BAFE8A33DF0` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan.py` | `19D443EA46BEA534FCC0469053D361883AE08D22FA802A75ACE8C4FBC0DCFBF9` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan_service.py` | `996EA62447141807BDFF71D0DACD4ED2788B540B8131FA963D89F5647C10655C` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_draft.py` | `6E9BE1CCD797C365A2B75E7C57D4F4E37564443FD1AFD5D3D44F133D853EB103` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_review.py` | `441D73E79C64AF7DE07E6A197E7C8A584D4E3489CAC054F7A76D695B1A70FA73` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_store.py` | `DF38AFC0DCEAC1C606DB3DF5CE6248DC1095983604B4507433109BFA72CC68C6` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/config.py` | `94C3BB627733BE0635114484EA634D7841177443F8A6D53490E14FD6E71F8443` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/feedback_store.py` | `60071115EBBC0B41756223F0112C1A1D971351625967F24239080B11A2724343` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/forecast.py` | `4EF97B77F6D4F7F072413DFD014FC0B39AC7DF33E5112CED091CEA821B57A097` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/loaders.py` | `112337EA62B7BD402ECB67D0ACFF974F910015ECEB0CC4927C975F9AEC716D15` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/material_board.py` | `4F0FB3A9673CD7F128CECC59302EA46D2080189B9DACB188240E41511C7B42E2` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/models.py` | `9F7397B68165FA2E8456140E8CC47F5896DA3CB16598EC27BE35757B77FB65DE` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/period_match.py` | `24C96DDE2DF6E570568AAA561CB2A2BBA6A673D3FBE3AC1A21D1DF875D991063` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/sources.py` | `228B333913BEABCB01D6315A48A3276B2D2787E8B1C7118028BC03B5F69154DE` |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/webapp.py` | `1CB27E63F548B72A6D36A69CB4FCB50158FA2B04B2C5F83716AEE8856286240E` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py` | `E7BA40C8B09F5839D2189DDF1EE6372E6FA7EB435DD1CA2C4E902082E9F86621` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/agents/__init__.py` | `A2223541FE056551B69948945C13C37C21CCBF5EE3BF5D4296A4ABAD89D7BE86` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/agents/kit_engine.py` | `1A265B6DD2FDD818BC0BC7682526EE8395A22E319F355EAFB2A127674EB5FC15` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py` | `9F5853A630DAE9B75A52A811CD3CE1BD80A2B4751A4B6C87B993DA3C3ADB9C09` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/__init__.py` | `02F261359047CAE1E14C0ACBED5B52A11A955D3D745F328A15C95F78BCD7EB77` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/access_log.py` | `28035D00FD9E5DDAF039F2825817282A9CCD11C57AD0B51B76D725DF7504BA6F` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py` | `84D2FAA6E5FC8EB781A1411AE6F8E812844EF816F1DB0E7E12C642B9A5FA71A7` |
| `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/simple_gate.py` | `100CAB8D8101F69A600679704481E40D5368DFED3C5BE92AB70AE1425BD53C5C` |
- 生成器唯一命令（待批准后执行）：在上述 SC8 cwd 运行
  `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-local-css-verification-1010/generate_synthetic_home.py' --run-id 'f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02'`
- 生成器在任何项目包导入之前，对上表 24 个可能于模块导入期间加载的项目模块执行全量 SHA 校验；任何键集/路径/字节变化均停止，不刷新 pin。随后用项目 `ensure_paths(..., strict=True)` 接入当前 worktree 平台路径，导入 `sc8.webapp`，并再次核对主模块路径及 webapp/baoguan 两个既有身份 SHA。闭包中 `sc8.config` 的源码也被固定；当前审定源码仅在 `default_params()` 被调用时解析真实环境参数，生成器在调用 `_shell_page()` 前先用固定 synthetic lambda 替换该函数及图例 renderer，因此不会调用真实默认配置。不得调用 `create_app()`、测试 client、snapshot/store/cache、connectors、API 或网络。
- 生成前必须断言 CSS block 各唯一一次且顺序 `webapp._HTML_STYLE < webapp._NAV_CSS < webapp._PORTAL_CSS`；portal CSS 必须含 `.bg-nav` `overflow-x:auto`/`white-space:nowrap`、`max-width:600px`、`.bg-nav .brand{display:none}`。准确匹配一个 inline `<script>...</script>` 并只删除该块；删除后 fail-closed 验证无 script、`on*` handler、`javascript:` URL、resource tag/URL、CSS `@import` 或 `url(...)`。
- 生成成功唯一写入：`mock-home.html`、`css-order-check.json`、`generator-manifest.json`。不写产品/测试/场景正式文档，不改队列、Git 元数据、服务或全局环境。所有阶段失败均保留已有输出/部分证据并停，不清理、不改 UUID、不重试。

## 本地 Browser/CUA 步骤（必须另列同一具体批准动作）

仅在生成器 PASS 且新的具体审批同时包含本地 CUA 渲染后执行。API 依据为根已核验的当前 CUA 文档：浏览器 id 为 2；cua.createBrowserTab 新建隐藏 tab；agent.browsers.get('2') 取得同一 browser；viewport 能力经 browser.capabilities.get('viewport') 获得；tab 使用 playwright.domSnapshot()、playwright.evaluate() 和 screenshot({fullPage:false})；Tab 实例用 close() 关闭。截图返回 JPEG Uint8Array，因此文件扩展名为 .jpg。Node filesystem 只用于本 UUID 已批准生成件/证据件，不参与浏览器控制，不读任何其他路径。CUA 没有页面 request 观察 API，本步骤不声称观测到零请求；本地 HTML 的无外部资源条件由前置生成器 fail-closed 断言，且不得点击链接。

### 执行前绑定与停止门

使用唯一 URL file:///C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02/mock-home.html，输出目录是前述同一 UUID。只读取该目录中的 generator-manifest.json 与 mock-home.html：核 run_id、synthetic_only、outputs["mock-home.html"]、source_sha256、project_import_closure_sha256；计算 manifest 与 HTML 实际字节 SHA，必须与 manifest.outputs["mock-home.html"] 相等。helper SHA 固定为 D8AF058410A5D121652C4C90FBA0BAD0DEC89518341F0232EFC2D3F3C14D3F97。manifest 不匹配、截图/viewport JSON 目标已存在或身份字段缺失，均在创建 Browser tab 前停止。Browser 首次 DOM snapshot 仅暂存在内存，只核对 synthetic marker；AX snapshot 不保证展示 CSS class，selector 存在性由随后只读 evaluate 对 .bg-nav、.wrap、.bg-nav .brand 和 .bg-nav a 进行检查，并以 required_selector_missing 失败值停止。采样只针对该本地合成页面；不保存、不输出 snapshot，不读隐藏应用 state、页面文字、URL 或 profile。snapshot 不含 marker、页面非 file、viewport 不匹配、检查失败、截图不是非空 Uint8Array，立即停止；保留已生成/已写入件，不切换 tab、不重试、不导航。

### CUA 可复核代码

以下是审批后在已经初始化的 CUA JavaScript session 中执行的一段单次脚本。它只创建并关闭本段自己创建的 tab；不关闭 id 2 的原 browser/tab。任何失败只写入阶段名和异常类型，不把异常消息、snapshot、页面文字或 URL 写入证据。若进程硬中断，保留已落盘的 JPEG；不得重跑本 UUID。

```javascript
    const fs = await import('node:fs/promises');
    const { createHash } = await import('node:crypto');
    const runId = 'f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02';
    const runDir = 'C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-' + runId;
    const htmlPath = runDir + '/mock-home.html';
    const manifestPath = runDir + '/generator-manifest.json';
    const fileUrl = 'file:///C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-' + runId + '/mock-home.html';
    const expectedHelperSha256 = 'D8AF058410A5D121652C4C90FBA0BAD0DEC89518341F0232EFC2D3F3C14D3F97';
    const syntheticMarker = 'SYNTHETIC CSS CHECK — NO CUSTOMER OR SNAPSHOT DATA';
    const results = [];
    let manifest = null;
    let manifestSha256 = null;
    let stage = 'manifest-preflight';
    let failure = null;
    let tab = null;
    let viewport = null;
    let manifestBound = false;

    const exists = async (path) => {
      try { await fs.access(path); return true; }
      catch (error) { if (error?.code === 'ENOENT') return false; throw error; }
    };
    const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

    try {
      const manifestBytes = await fs.readFile(manifestPath);
      manifest = JSON.parse(manifestBytes.toString('utf8'));
      manifestSha256 = sha256(manifestBytes);
      if (manifest.run_id !== runId || manifest.synthetic_only !== true ||
          manifest.online_deployment_claim !== false ||
          !/^[A-F0-9]{64}$/.test(manifest.outputs?.['mock-home.html'] || '') ||
          !manifest.source_sha256 || !manifest.project_import_closure_sha256) {
        throw Object.assign(new Error(), { name: 'manifest_identity_mismatch' });
      }
      const htmlBytes = await fs.readFile(htmlPath);
      if (sha256(htmlBytes) !== manifest.outputs['mock-home.html']) {
        throw Object.assign(new Error(), { name: 'generated_html_sha_mismatch' });
      }
      const evidencePaths = [
        runDir + '/viewport-320.jpg',
        runDir + '/viewport-390.jpg',
        runDir + '/viewport-check.json',
      ];
      for (const path of evidencePaths) {
        if (await exists(path)) throw Object.assign(new Error(), { name: 'evidence_path_exists' });
      }
      manifestBound = true;

      stage = 'create-local-tab';
      tab = await cua.createBrowserTab('2', fileUrl, { visible: false });
      const browser = await agent.browsers.get('2');
      viewport = await browser.capabilities.get('viewport');

      for (const size of [{ width: 320, height: 844 }, { width: 390, height: 844 }]) {
        stage = 'viewport-' + size.width + '-set';
        await viewport.set(size);

        stage = 'viewport-' + size.width + '-snapshot-grounding';
        const snapshot = await tab.playwright.domSnapshot();
        if (typeof snapshot !== 'string' || !snapshot.includes(syntheticMarker)) {
          throw Object.assign(new Error(), { name: 'snapshot_synthetic_marker_missing' });
        }

        stage = 'viewport-' + size.width + '-evaluate';
        const measurement = await tab.playwright.evaluate(() => {
          const rect = (element) => {
            if (!element) return null;
            const r = element.getBoundingClientRect();
            return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height };
          };
          const nav = document.querySelector('.bg-nav');
          const wrap = document.querySelector('.wrap');
          const brand = document.querySelector('.bg-nav .brand');
          const links = [...document.querySelectorAll('.bg-nav a')];
          if (!nav || !wrap || !brand || links.length === 0) {
            return { sample_error: 'required_selector_missing' };
          }
          const navStyle = getComputedStyle(nav);
          const navRect = rect(nav);
          const wrapRect = rect(wrap);
          const linkTops = links.map((link) => link.getBoundingClientRect().top);
          const documentElement = document.documentElement;
          return {
            viewport: { width: window.innerWidth, height: window.innerHeight },
            document: { clientWidth: documentElement.clientWidth, scrollWidth: documentElement.scrollWidth },
            nav: {
              rect: navRect,
              clientWidth: nav.clientWidth,
              scrollWidth: nav.scrollWidth,
              overflowX: navStyle.overflowX,
              whiteSpace: navStyle.whiteSpace,
            },
            wrap: { rect: wrapRect },
            brand: { display: getComputedStyle(brand).display },
            links: links.map((link) => ({ rect: rect(link) })),
            checks: {
              local_file: location.protocol === 'file:',
              nav_before_wrap: navRect.bottom <= wrapRect.top,
              links_same_row: Math.max(...linkTops) - Math.min(...linkTops) <= 1,
              no_page_horizontal_overflow: documentElement.scrollWidth <= documentElement.clientWidth,
              nav_horizontal_scroll: navStyle.overflowX === 'auto',
              nav_nowrap: navStyle.whiteSpace === 'nowrap',
              brand_hidden: getComputedStyle(brand).display === 'none',
              document_metrics_positive: documentElement.clientWidth > 0 && documentElement.scrollWidth > 0,
            },
          };
        });
        const resultRecord = {
          viewport: size,
          snapshot_grounding: {
            synthetic_marker: true,
            selector_presence_sampled_in_evaluate: true,
          },
          sampled_utc: new Date().toISOString(),
          measurement,
          screenshot: null,
          screenshot_sha256: null,
        };
        results.push(resultRecord);

        if (measurement.sample_error ||
            measurement.viewport?.width !== size.width ||
            measurement.viewport?.height !== size.height ||
            Object.values(measurement.checks || {}).some((passed) => passed !== true)) {
          throw Object.assign(new Error(), { name: 'viewport_geometry_check_failed' });
        }

        stage = 'viewport-' + size.width + '-screenshot';
        const jpeg = await tab.screenshot({ fullPage: false });
        if (!(jpeg instanceof Uint8Array) || jpeg.length === 0) {
          throw Object.assign(new Error(), { name: 'screenshot_not_nonempty_uint8array' });
        }
        const screenshotName = 'viewport-' + size.width + '.jpg';
        await fs.writeFile(runDir + '/' + screenshotName, jpeg, { flag: 'wx' });
        resultRecord.screenshot = screenshotName;
        resultRecord.screenshot_sha256 = sha256(jpeg);
      }
    } catch (error) {
      failure = {
        stage,
        error_type: typeof error?.name === 'string' ? error.name : 'Error',
      };
    } finally {
      if (viewport) {
        try { await viewport.reset(); }
        catch (error) {
          failure ||= {
            stage: 'viewport-reset',
            error_type: typeof error?.name === 'string' ? error.name : 'Error',
          };
        }
      }
      if (tab) {
        try { await tab.close(); }
        catch (error) {
          failure ||= {
            stage: 'close-created-tab',
            error_type: typeof error?.name === 'string' ? error.name : 'Error',
          };
        }
      }
    }

    if (!manifestBound || !manifest) {
      throw Object.assign(new Error(), { name: 'manifest_preflight_failed_before_browser' });
    }
    const viewportEvidence = {
      run_id: runId,
      status: failure ? 'stopped' : 'complete',
      failure,
      recorded_samples_are_local_file: results.length > 0 &&
        results.every((item) => item.measurement?.checks?.local_file === true),
      generator_manifest_sha256: manifestSha256,
      source_sha256: manifest.source_sha256,
      project_import_closure_sha256: manifest.project_import_closure_sha256,
      helper_sha256: expectedHelperSha256,
      generated_output_sha256: manifest.outputs,
      viewports: results,
    };
    await fs.writeFile(
      runDir + '/viewport-check.json',
      JSON.stringify(viewportEvidence, null, 2) + '\n',
      { flag: 'wx' },
    );
    if (failure) throw Object.assign(new Error(), { name: 'viewport_evidence_stopped' });
```

脚本不填造几何数值。viewport-check.json 只保存页面 evaluate 返回的数值/布尔/computed CSS、snapshot 中 synthetic marker 的核对结果及 selector presence 已由 evaluate 采样的布尔值、UTC 采样时间、截图文件名/hash，以及生成器 manifest 中绑定的 source/helper/output hash。两种 viewport 都须实测窗口尺寸并通过：nav.bottom <= wrap.top；所有 nav anchor 的 rect.top 极差 ≤1 CSS px；document.scrollWidth <= clientWidth；nav overflowX 为 auto、whiteSpace 为 nowrap；brand display 为 none；本地 file 协议成立且 document 尺寸为正。nav 内部横向溢出可接受并记录。

CUA 没有页面请求观察 API，本计划不声称已测得请求数量。生成器对合成 HTML 的无外部资源断言是前置边界；执行中不点击链接。snapshot 未显示 synthetic marker，evaluate 未找到必需 selector，或几何、CSS、本地 file、截图、cleanup 检查任一失败，脚本立即停止并保留当前 UUID 证据；不重试或改输入。最终目录限定一个 UUID，最多 6 个文件：3 个生成件、viewport-320.jpg、viewport-390.jpg、viewport-check.json。不能保存 JPEG 或几何值时只记录停止原因，不拿旧现网截图补位。

## 人工复核与停止条件

复核者检查 source SHA、项目导入闭包 SHA、生成器 manifest、CSS-order JSON、浏览器每视口 JSON 与 JPEG 截图同一 UUID 绑定；检查 removed_inline_script_count == 1 和无残留事件/外部资源。报告必须写“本地合成页面结果”，不宣称线上已部署、现网已修复或真实客户页面通过。

任何 source/import SHA 变化、路径/UUID 已存在、CSS 条件失败、script 计数不为一、残留 handler/资源、Browser 不能精确 viewport、nav.bottom > wrap.top、anchor 换行、document 横向溢出或截图/测量不一致，都停止并保留证据；不清理、不改源码、不修 CSS、不重跑。没有已知阻断时，仍需单独审批后才能生成与使用 Browser。

## 根正式绑定

2026-10-10T23:22:40.218688+08:00：原计划 AE312A…7D58F、生成器 D8AF05…D3F97 已静态审阅，CUA async browser getter已补await，AX只核合成marker，selector由只读DOM evaluate核存在。仅正式pack执行件可消费；批准前生成/Browser/输出目录均未启动。新的具体执行批准须同时覆盖固定UUID六件、单次合成生成及320/390两视口CUA；旧现网只读查看许可不扩用。本地结果不得视为线上修复，部署仍另审。
