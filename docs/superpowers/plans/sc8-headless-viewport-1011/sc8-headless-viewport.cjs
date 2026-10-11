'use strict';

// Prepared for review only. Do not execute without a separate SC8-specific approval.
const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');
const runtimeRoot = 'C:/Users/Paul Shao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node';
const packageRoot = runtimeRoot + '/node_modules/playwright';
const coreRoot = runtimeRoot + '/node_modules/playwright-core';
const nodePath = runtimeRoot + '/bin/node.exe';
const formalScriptPath = 'C:/Dev/zhuopin-ai/docs/superpowers/plans/sc8-headless-viewport-1011/sc8-headless-viewport.cjs';

const runId = '95a30c80-333f-4f81-bb9d-17c015ff1657';
const sourcePath = 'C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02/mock-home.html';
const manifestPath = 'C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02/generator-manifest.json';
const cssCheckPath = 'C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/local-css-f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02/css-order-check.json';
const runRoot = 'C:/Dev/zhuopin-ai/reports/sc8-live-readonly-1010/playwright-headless-' + runId;
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const expected = {
  htmlSha256: 'EC0886DA76451CE5926BF858979BC38F635F43C9E2BE2A65B176896BA1DA7106',
  manifestSha256: 'DA91BCC2078C6B3E0EBD08FAF6343AD87D3047652BDB16E2FDE8C3DCEC609283',
  cssCheckSha256: 'CC668A173859ABC6BCC1F36FF2DAD1038C41B6EB8E70339A35989C84DC8B8604',
  webappSha256: '1CB27E63F548B72A6D36A69CB4FCB50158FA2B04B2C5F83716AEE8856286240E',
  baoguanSha256: '19D443EA46BEA534FCC0469053D361883AE08D22FA802A75ACE8C4FBC0DCFBF9',
};
const marker = 'SYNTHETIC CSS CHECK — NO CUSTOMER OR SNAPSHOT DATA';
const sizes = [{ width: 320, height: 844 }, { width: 390, height: 844 }];
const sha256 = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();

async function packageTreeIdentity(root) {
  const files = [];
  async function visit(relative) {
    for (const entry of await fs.readdir(root + (relative ? '/' + relative : ''), { withFileTypes: true })) {
      if (entry.isSymbolicLink()) throw Object.assign(new Error(), { name: 'package_symlink_rejected' });
      const path = relative ? relative + '/' + entry.name : entry.name;
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) files.push(path);
      else throw Object.assign(new Error(), { name: 'package_nonordinary_entry_rejected' });
    }
  }
  await visit('');
  files.sort();
  let text = '';
  for (const path of files) {
    const bytes = await fs.readFile(root + '/' + path);
    text += path + '\t' + bytes.length + '\t' + sha256(bytes) + '\n';
  }
  return { file_count: files.length, tree_sha256: sha256(Buffer.from(text, 'utf8')) };
}

async function run() {
  let stage = 'input-preflight';
  let browser = null;
  let context = null;
  let page = null;
  let outputCreated = false;
  const evidence = {
    run_id: runId,
    status: 'stopped',
    synthetic_only: true,
    online_deployment_claim: false,
    source_path: sourcePath,
    source_sha256: null,
    manifest_sha256: null,
    css_check_sha256: null,
    browser: { executable_path: chromePath, version: null },
    request_observation_scope: 'page.route only; not a Chrome process-level network claim',
    runtime_identity: [],
    own_temp_root: runRoot + '/browser-temp',
    viewport_samples: [],
    external_requests_blocked: 0,
    source_unchanged: null,
    own_browser_closed: false,
    failure: null,
  };

  try {
    if (__filename.replace(/\\/g, '/') !== formalScriptPath ||
        process.execPath.replace(/\\/g, '/') !== nodePath || process.version !== 'v24.19.0') {
      throw Object.assign(new Error(), { name: 'execution_path_or_node_version_mismatch' });
    }
    const runtimePins = [
      [nodePath, '3602F2BB1A10F2CBAB4C36886218A33C1AB3DB87290E73B033C46C77147D0237'],
      [packageRoot + '/package.json', 'CA170EC143A88ED3043AC953EB3B2377B2B97304104F4E1E23316684CE2C35AF'],
      [packageRoot + '/index.js', '4E98F65F0A9D9BCAB8CFFC0C5CFDD87FD3F5B0BE74FC494FF166A466B204CD44'],
      [packageRoot + '/cli.js', '5E79302A6AAD7D835D92D5AE6B4244C91CF61B28E94D7917279090E6C231F7A1'],
      [coreRoot + '/package.json', '07C47543631FEF9508760365DEE9FBE958C562093EC8D122543949ED231F233F'],
      [coreRoot + '/index.js', 'A58FB2CEC4293E7DCF73C58A179898A4F3986666451A19DA4E731FA3AF63265B'],
      [chromePath, '6849D2982038DE9F9489A7B3858F3B785B7FEC06A842C93C517281D21995C8CA'],
      ['C:/Dev/zhuopin-ai/docs/superpowers/plans/2026-10-10-sc8-local-css-verification.md', '7292EDEDB14914732E16EDE38BC8AB70683E4106693B9A3FB0016C342A450CE4'],
    ];
    for (const [path, pin] of runtimePins) {
      const actual = sha256(await fs.readFile(path));
      if (actual !== pin) throw Object.assign(new Error(), { name: 'runtime_or_source_plan_sha_mismatch' });
      evidence.runtime_identity.push({ path, sha256: actual });
    }
    for (const [root, count, pin] of [
      [packageRoot, 62, 'F081C07ACD2DCE682F187DF71BED0E1DB63DB18F3346D351132A7A6CC8E7C68E'],
      [coreRoot, 111, '19A3BCFAC18B8596A419139C2C415D323EEC6298468B4245755A1C756E4A4C8C'],
    ]) {
      const actual = await packageTreeIdentity(root);
      if (actual.file_count !== count || actual.tree_sha256 !== pin) {
        throw Object.assign(new Error(), { name: 'complete_package_tree_identity_mismatch' });
      }
      evidence.runtime_identity.push({ path: root, ...actual });
    }
    if (JSON.parse(await fs.readFile(packageRoot + '/package.json', 'utf8')).version !== '1.62.1' ||
        JSON.parse(await fs.readFile(coreRoot + '/package.json', 'utf8')).version !== '1.62.1') {
      throw Object.assign(new Error(), { name: 'playwright_package_version_mismatch' });
    }
    const [htmlBytes, manifestBytes, cssBytes] = await Promise.all([
      fs.readFile(sourcePath), fs.readFile(manifestPath), fs.readFile(cssCheckPath),
    ]);
    const manifest = JSON.parse(manifestBytes.toString('utf8'));
    const cssCheck = JSON.parse(cssBytes.toString('utf8'));
    evidence.source_sha256 = sha256(htmlBytes);
    evidence.manifest_sha256 = sha256(manifestBytes);
    evidence.css_check_sha256 = sha256(cssBytes);
    if (evidence.source_sha256 !== expected.htmlSha256 ||
        evidence.manifest_sha256 !== expected.manifestSha256 ||
        evidence.css_check_sha256 !== expected.cssCheckSha256 ||
        manifest.run_id !== 'f41d8ef8-3d74-4e0e-9b10-f8c11ca0aa02' ||
        manifest.synthetic_only !== true || manifest.online_deployment_claim !== false ||
        manifest.outputs?.['mock-home.html'] !== expected.htmlSha256 ||
        manifest.source_sha256?.['sc8/webapp.py'] !== expected.webappSha256 ||
        manifest.source_sha256?.['sc8/baoguan.py'] !== expected.baoguanSha256 ||
        !htmlBytes.toString('utf8').includes(marker) ||
        cssCheck.synthetic_only !== true ||
        JSON.stringify(cssCheck.css_order) !== JSON.stringify(['base', 'navigation', 'portal']) ||
        cssCheck.portal_rules?.nav_overflow_x_auto !== true ||
        cssCheck.portal_rules?.nav_white_space_nowrap !== true ||
        cssCheck.portal_rules?.mobile_breakpoint_600px !== true ||
        cssCheck.portal_rules?.mobile_brand_hidden !== true ||
        cssCheck.residual_script_handlers_js_urls_external_resources !== false) {
      throw Object.assign(new Error(), { name: 'input_identity_or_static_manifest_mismatch' });
    }
    if (await fs.stat(runRoot).then(() => true, (error) => {
      if (error?.code === 'ENOENT') return false;
      throw error;
    })) {
      throw Object.assign(new Error(), { name: 'new_run_output_path_already_exists' });
    }
    const sourceUrl = pathToFileURL(sourcePath).href;
    if (!sourceUrl.startsWith('file:///C:/Dev/zhuopin-ai/reports/')) {
      throw Object.assign(new Error(), { name: 'source_url_outside_approved_local_root' });
    }

    stage = 'create-owned-output-and-temp';
    await fs.mkdir(runRoot, { recursive: false });
    outputCreated = true;
    await fs.mkdir(evidence.own_temp_root, { recursive: false });
    // Process-scoped only; Playwright's temporary profile/artifacts stay in this new UUID.
    process.env.TEMP = evidence.own_temp_root;
    process.env.TMP = evidence.own_temp_root;
    stage = 'load-verified-playwright';
    const { chromium } = require(packageRoot);
    stage = 'launch-owned-headless-chrome';
    browser = await chromium.launch({
      executablePath: chromePath,
      headless: true,
      chromiumSandbox: true,
      args: ['--no-first-run', '--no-default-browser-check', '--disable-background-networking'],
    });
    evidence.browser.version = browser.version();
    if (evidence.browser.version !== '154.0.8037.98') {
      throw Object.assign(new Error(), { name: 'chrome_version_mismatch' });
    }
    context = await browser.newContext({
      viewport: sizes[0],
      deviceScaleFactor: 1,
      colorScheme: 'light',
      javaScriptEnabled: false,
      serviceWorkers: 'block',
    });
    page = await context.newPage();
    await page.route('**/*', async (route) => {
      const url = route.request().url();
      if (url === sourceUrl || url.startsWith('data:')) return route.continue();
      evidence.external_requests_blocked += 1;
      return route.abort();
    });

    stage = 'navigate-to-fixed-local-html';
    await page.goto(sourceUrl, { waitUntil: 'load' });
    if (page.url() !== sourceUrl) {
      throw Object.assign(new Error(), { name: 'navigation_not_fixed_local_file' });
    }
    for (const size of sizes) {
      stage = 'viewport-' + size.width + '-set';
      await page.setViewportSize(size);
      const measurement = await page.evaluate(() => {
        const nav = document.querySelector('.bg-nav');
        const wrap = document.querySelector('.wrap');
        const brand = document.querySelector('.bg-nav .brand');
        const links = [...document.querySelectorAll('.bg-nav a')];
        if (!nav || !wrap || !brand || links.length === 0) return { sample_error: 'required_selector_missing' };
        const rect = (element) => {
          const r = element.getBoundingClientRect();
          return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height };
        };
        const navStyle = getComputedStyle(nav);
        const navRect = rect(nav);
        const wrapRect = rect(wrap);
        const linkTops = links.map((link) => link.getBoundingClientRect().top);
        const documentElement = document.documentElement;
        return {
          viewport: { width: window.innerWidth, height: window.innerHeight },
          document: { clientWidth: documentElement.clientWidth, scrollWidth: documentElement.scrollWidth },
          nav: { rect: navRect, clientWidth: nav.clientWidth, scrollWidth: nav.scrollWidth,
            overflowX: navStyle.overflowX, whiteSpace: navStyle.whiteSpace },
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
      const check = {
        viewport: size,
        sampled_utc: new Date().toISOString(),
        measurement,
        screenshot: null,
        screenshot_sha256: null,
      };
      evidence.viewport_samples.push(check);
      if (measurement.sample_error || measurement.viewport?.width !== size.width ||
          measurement.viewport?.height !== size.height ||
          Object.values(measurement.checks || {}).some((passed) => passed !== true)) {
        throw Object.assign(new Error(), { name: 'viewport_geometry_check_failed' });
      }
      if (evidence.external_requests_blocked !== 0) {
        throw Object.assign(new Error(), { name: 'nonlocal_request_was_blocked' });
      }
      stage = 'viewport-' + size.width + '-jpeg';
      const jpeg = await page.screenshot({ type: 'jpeg', quality: 85, fullPage: false });
      if (jpeg.length < 4 || jpeg[0] !== 0xff || jpeg[1] !== 0xd8 ||
          jpeg[jpeg.length - 2] !== 0xff || jpeg[jpeg.length - 1] !== 0xd9) {
        throw Object.assign(new Error(), { name: 'screenshot_not_jpeg' });
      }
      const fileName = 'viewport-' + size.width + '.jpg';
      await fs.writeFile(runRoot + '/' + fileName, jpeg, { flag: 'wx' });
      check.screenshot = fileName;
      check.screenshot_sha256 = sha256(jpeg);
    }
    stage = 'source-unchanged-check';
    evidence.source_unchanged = sha256(await fs.readFile(sourcePath)) === expected.htmlSha256;
    if (!evidence.source_unchanged) throw Object.assign(new Error(), { name: 'source_changed_during_review' });
    if (evidence.viewport_samples.length !== 2 || evidence.external_requests_blocked !== 0) {
      throw Object.assign(new Error(), { name: 'evidence_scope_mismatch' });
    }
    evidence.status = 'complete';
  } catch (error) {
    evidence.failure = { stage, error_type: typeof error?.name === 'string' ? error.name : 'Error' };
  } finally {
    if (context) {
      try { await context.close(); }
      catch (error) {
        evidence.failure ||= { stage: 'close-owned-context', error_type: typeof error?.name === 'string' ? error.name : 'Error' };
      }
    }
    if (browser) {
      try { await browser.close(); evidence.own_browser_closed = true; }
      catch (error) {
        evidence.failure ||= { stage: 'close-owned-browser', error_type: typeof error?.name === 'string' ? error.name : 'Error' };
      }
    }
    if (evidence.failure) evidence.status = 'stopped';
    if (outputCreated) {
      await fs.writeFile(runRoot + '/viewport-check.json', JSON.stringify(evidence, null, 2) + '\n', { flag: 'wx' });
    }
  }
  console.log(JSON.stringify({ run_id: runId, status: evidence.status,
    viewport_samples: evidence.viewport_samples.length, external_requests_blocked: evidence.external_requests_blocked,
    failure: evidence.failure }));
  if (evidence.status !== 'complete') process.exitCode = 1;
}

run().catch((error) => {
  console.error(JSON.stringify({ status: 'stopped', error_type: typeof error?.name === 'string' ? error.name : 'Error' }));
  process.exitCode = 1;
});
