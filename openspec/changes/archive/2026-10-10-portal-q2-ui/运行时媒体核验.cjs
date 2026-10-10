// Approved Q2 task 3.2 scope. Prepared only; execute after CLI browser permission.
const { chromium } = require('C:/Users/Paul Shao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');

const previewRoot = 'C:/Users/Paul Shao/.codex/worktrees/portal-q2-ui-1008/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/reports/q2-ui-preview';
const outputRoot = __dirname;
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

async function run() {
  await fs.mkdir(outputRoot, { recursive: true });
  const context = await chromium.launchPersistentContext(path.join(outputRoot, 'isolated-profile'), {
    executablePath: chromePath, headless: true, chromiumSandbox: true, viewport: { width: 1440, height: 1024 },
    args: ['--no-first-run', '--no-default-browser-check', '--disable-background-networking'],
  });
  const evidence = { time: new Date().toISOString(), browser: context.browser()?.version(),
    task: 'portal-q2-ui/3.2 reduced-motion only', sourceFilesUnchanged: true,
    productionRequests: 0, externalRequestsBlocked: [], samples: [], complete: false };
  try {
    await context.route('**/*', route => {
      const url = route.request().url();
      if (url.startsWith('file:') || url.startsWith('data:')) return route.continue();
      evidence.externalRequestsBlocked.push(url);
      return route.abort();
    });
    const page = await context.newPage();
    for (const name of ['mixed', 'empty']) {
      const file = path.join(previewRoot, `${name}.html`);
      const before = await fs.readFile(file);
      const sample = { name, file, url: pathToFileURL(file).href,
        sha256: crypto.createHash('sha256').update(before).digest('hex'), results: [] };
      await page.goto(sample.url, { waitUntil: 'load' });
      await page.evaluate(() => {
        const sheet = document.createElement('style');
        sheet.id = 'q2-motion-runtime-probe-style';
        sheet.textContent = '@keyframes q2MotionProbe { from { opacity: .4 } to { opacity: 1 } } #q2-motion-runtime-probe::before, #q2-motion-runtime-probe::after { content: "•"; animation: q2MotionProbe 2s linear infinite; transition: opacity 2s linear; scroll-behavior: smooth; }';
        document.head.append(sheet);
        const probe = document.createElement('div');
        probe.id = 'q2-motion-runtime-probe';
        probe.textContent = '临时 motion probe（浏览器内验证，不属于产品）';
        probe.style.cssText = 'position:fixed;bottom:8px;left:8px;background:#fff;padding:4px;font-size:12px;z-index:99999;animation:q2MotionProbe 2s linear infinite;transition:opacity 2s linear;scroll-behavior:smooth';
        document.body.append(probe);
      });
      for (const preference of ['no-preference', 'reduce', 'no-preference']) {
        await page.emulateMedia({ reducedMotion: preference });
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const observation = await page.evaluate(() => {
          const probe = document.querySelector('#q2-motion-runtime-probe');
          const values = [null, '::before', '::after'].map(pseudo => {
            const style = getComputedStyle(probe, pseudo);
            return { pseudo: pseudo || 'element', animationName: style.animationName,
              animationDuration: style.animationDuration, transitionProperty: style.transitionProperty,
              transitionDuration: style.transitionDuration, scrollBehavior: style.scrollBehavior };
          });
          return { mediaMatches: matchMedia('(prefers-reduced-motion: reduce)').matches,
            values, activeAnimations: probe.getAnimations({ subtree: true }).length };
        });
        sample.results.push({ preference, ...observation });
        if (observation.mediaMatches !== (preference === 'reduce')) throw Error(`Media mismatch: ${name}/${preference}`);
        for (const values of observation.values) {
          if (preference === 'reduce') {
            if (values.animationName !== 'none' || values.animationDuration !== '0s' || values.transitionDuration !== '0s' || values.scrollBehavior !== 'auto') throw Error(`Reduced rule mismatch: ${JSON.stringify(values)}`);
          } else if (values.animationName !== 'q2MotionProbe' || values.animationDuration !== '2s' || values.transitionDuration !== '2s' || values.scrollBehavior !== 'smooth') throw Error(`Control mismatch: ${JSON.stringify(values)}`);
        }
        if (preference === 'reduce' && observation.activeAnimations !== 0) throw Error('Reduced probe still animates');
        if (preference === 'no-preference' && observation.activeAnimations < 1) throw Error('Control has no actual animation');
        if (preference === 'reduce') await page.screenshot({ path: path.join(outputRoot, `${name}-reduce.png`) });
      }
      await page.evaluate(() => { document.querySelector('#q2-motion-runtime-probe')?.remove(); document.querySelector('#q2-motion-runtime-probe-style')?.remove(); });
      const after = await fs.readFile(file);
      if (!before.equals(after)) throw Error('Source preview changed');
      evidence.samples.push(sample);
    }
    await page.emulateMedia({ reducedMotion: null });
    evidence.complete = true;
  } catch (error) {
    evidence.error = String(error.stack || error);
    process.exitCode = 1;
  } finally {
    await context.close();
    await fs.writeFile(path.join(outputRoot, 'runtime-evidence.json'), JSON.stringify(evidence, null, 2) + '\n', 'utf8');
    console.log(JSON.stringify({ complete: evidence.complete, samples: evidence.samples.length, error: evidence.error || null }));
  }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
