import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const file = path.join(root, 'AI运营指挥中心-框架原型-v0.1.html');
let html = await readFile(file, 'utf8');
for (const [name, source, tag] of [
  ['MODEL','ui/portal-model.mjs','script'],
  ['THEME','ui/portal-theme.css','style'],
  ['PAGE','ui/portal-page.js','script']
]) {
  const begin = `<!-- PORTAL_UI_${name}_BEGIN -->`;
  const end = `<!-- PORTAL_UI_${name}_END -->`;
  if (html.split(begin).length !== 2 || html.split(end).length !== 2 || html.indexOf(begin) >= html.indexOf(end)) {
    throw new Error(`内联标记缺失、重复或次序错误：${name}`);
  }
  let body = await readFile(path.join(root, source), 'utf8');
  if (name === 'MODEL') {
    body = body.replace(/^export /gm, '');
    const apps = JSON.parse(await readFile(path.join(root, 'ui/apps.json'),'utf8'));
    body += '\nconst appRegistry = '+JSON.stringify(apps).replace(/</g,'\\u003c')+';\n';
  }
  if (body.toLowerCase().includes(`</${tag}`)) throw new Error(`源文件含提前结束标签：${name}`);
  const start = html.indexOf(begin) + begin.length;
  const finish = html.indexOf(end);
  html = html.slice(0,start) + `\n<${tag}>\n${body}\n</${tag}>\n` + html.slice(finish);
}
await writeFile(file, html, 'utf8');
console.log('单文件模型与主题内联完成');
