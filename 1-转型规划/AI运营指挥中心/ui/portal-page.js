// 公共框架：只读入口与同源脱敏展示。无业务写请求、无模拟复核。
const titles = {overview:'门户',apps:'应用目录',tasks:'我的待办',review:'人工复核',system:'系统与发布',procurement:'采购部',quality:'质量部',finance:'财务部',sales:'销售部',operations:'运营管理',engineering:'工程研发'};
const departmentViews = {采购:'procurement',质量:'quality',财务:'finance',销售:'sales',运营管理:'operations',工程研发:'engineering'};
const sidebar = document.getElementById('sidebar');
const scrim = document.getElementById('scrim');
const burger = document.getElementById('hamburger');
const mobileQuery = window.matchMedia('(max-width:760px)');
document.querySelector('.skip-link').addEventListener('click',event=>{
  event.preventDefault();
  document.getElementById('main-content').focus();
});
function syncDrawer(open, restoreFocus = false) {
  const isMobile = mobileQuery.matches;
  sidebar.classList.toggle('open', isMobile && open);
  sidebar.inert = isMobile && !open;
  scrim.classList.toggle('show', isMobile && open);
  scrim.hidden = !(isMobile && open);
  burger.setAttribute('aria-expanded', String(isMobile && open));
  if (restoreFocus && isMobile) burger.focus();
}
burger.addEventListener('click',()=>syncDrawer(!sidebar.classList.contains('open')));
scrim.addEventListener('click',()=>syncDrawer(false,true));
document.addEventListener('keydown',e=>{
  if (e.key==='Escape' && sidebar.classList.contains('open')) syncDrawer(false,true);
});
mobileQuery.addEventListener('change',()=>syncDrawer(false));
function go(value, changeHash = true) {
  const view = parseView(value);
  const activeInDrawer = sidebar.contains(document.activeElement);
  document.querySelectorAll('.view').forEach(el=>{el.classList.toggle('active',el.id==='view-'+view);el.hidden=el.id!=='view-'+view;});
  document.querySelectorAll('[data-view]').forEach(el=>{
    el.classList.toggle('active', el.dataset.view===view);
    if(el.dataset.view===view) el.setAttribute('aria-current','page'); else el.removeAttribute('aria-current');
  });
  document.getElementById('crumb').textContent='卓品智能 / '+titles[view];
  syncDrawer(false,activeInDrawer);
  if(changeHash && location.hash!=='#'+view) location.hash=view;
  window.scrollTo(0,0);
}
document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>go(el.dataset.view)));
window.addEventListener('hashchange',()=>go(location.hash,false));
function cardFor(app) {
  const card = document.createElement(app.href ? 'a' : 'article');
  card.className='app-card';
  if(app.href){card.href=app.href;if(!app.href.startsWith('#')){card.target='_blank';card.rel='noopener';}}
  const glyph = document.createElement('span');glyph.className='app-icon';
  // 图标SVG是固定Heroicons库导出，不消费数据源文本。
  const iconId=app.id==='sc8'?'cube':app.id==='q2'?'tasks':'document';
  glyph.innerHTML=document.getElementById('app-icon-'+iconId).innerHTML;
  card.append(glyph);
  const copy=document.createElement('div');
  const title=document.createElement('h3');title.textContent=app.name;
  const badge=document.createElement('span');badge.className='badge'+(app.stage.includes('确认')?' pending':app.stage==='规划'?' plan':'');badge.textContent=app.stage;
  const desc=document.createElement('p');desc.textContent=app.description;
  const meta=document.createElement('span');meta.className='meta';meta.textContent=app.department+'部 · '+app.id.toUpperCase();
  copy.append(title,badge,desc,meta);card.append(copy);return card;
}
function fillCards(container, items) {container.replaceChildren(...items.map(cardFor));}
function renderDirectory() {
  const items=filterApps(appRegistry,{query:document.getElementById('app-query').value,department:document.getElementById('department-filter').value});
  fillCards(document.getElementById('app-results'),items);
  document.getElementById('search-count').textContent=items.length+' 个应用 / 入口';
  document.getElementById('search-empty').hidden=items.length!==0;
}
document.getElementById('directory-search').addEventListener('submit',e=>{e.preventDefault();renderDirectory();});
document.getElementById('department-filter').addEventListener('change',renderDirectory);
document.getElementById('reset-search').addEventListener('click',()=>{document.getElementById('app-query').value='';document.getElementById('department-filter').value='全部';renderDirectory();});
document.getElementById('home-search').addEventListener('submit',e=>{e.preventDefault();document.getElementById('app-query').value=document.getElementById('home-query').value;document.getElementById('department-filter').value='全部';renderDirectory();go('apps');document.getElementById('app-query').focus();});
document.querySelectorAll('[data-query]').forEach(button=>button.addEventListener('click',()=>{document.getElementById('app-query').value=button.dataset.query;document.getElementById('department-filter').value='全部';renderDirectory();go('apps');}));
for(const [department,view] of Object.entries(departmentViews)) {
  const target=document.getElementById(view+'-apps');
  if(target) fillCards(target,appRegistry.filter(app=>app.department===department));
}
fillCards(document.getElementById('frequent-apps'),['qd-b','sc8','q2'].map(id=>appRegistry.find(app=>app.id===id)));
renderDirectory();go(location.hash,false);

const snapshotTime='2026-06-25';
function markSales(ok,syncTime){
  const state=salesState({ok,syncTime});
  document.getElementById('salesBadge').textContent=state.label;
  document.getElementById('salesSync').textContent=state.sourceTime;
  document.getElementById('sales-state').classList.toggle('snapshot',!ok || !syncTime);
}
function text(tag,value,className){const node=document.createElement(tag);node.textContent=String(value ?? '来源未提供');if(className)node.className=className;return node;}
function money(value){return displayMoney(value);}
function renderBars(id,rows){
  const target=document.getElementById(id);target.replaceChildren();
  if(!rows.length){target.append(text('p','来源未提供此部分数据','meta'));return;}
  const maximum=Math.max(1,...rows.map(row=>Number(row.count)||0));
  for(const row of rows){const block=document.createElement('div');block.className='prow';const track=document.createElement('div');track.className='track';const bar=document.createElement('i');bar.style.width=Math.max(0,Math.min(100,(Number(row.count)||0)/maximum*100))+'%';track.append(bar);block.append(text('div',row.name,'pn'),track,text('div',row.count,'pc'));target.append(block);}
}
function renderRows(id,rows){
  const target=document.getElementById(id);target.replaceChildren();
  if(!rows.length){const tr=document.createElement('tr');const td=text('td','来源未提供此部分数据');td.colSpan=4;tr.append(td);target.append(tr);return;}
  for(const values of rows){const tr=document.createElement('tr');tr.append(...values.map(value=>text('td',value)));target.append(tr);}
}
function renderSalesData(data){
  if(!data || typeof data!=='object' || Array.isArray(data)) throw new Error('销售来源格式错误');
  const summary=salesSummary(data);
  for(const [id,value] of Object.entries({salesConversion:summary.conversion,salesScoreTotal:summary.leads,salesRiskMeta:summary.risk,salesScoreInsight:summary.insight})) document.getElementById(id).textContent=value;
  const k=data.kpis || {};
  const opp=Array.isArray(data.funnel)?data.funnel[2]?.count:undefined;
  const missing=value=>value??'来源未提供';
  const metrics=[['商机管道',money(k.pipeline_amount),'在库商机 '+missing(opp)+' 个'],['赢单 Design-Win',k.design_win_count,'贡献 '+missing(k.design_win_contribution)],['线索总数',k.total_leads,'客户 '+missing(k.total_customers)+' · 联系人 '+missing(k.total_contacts)],['高危线索',k.high_risk_leads_count,'沿用原评分与干预口径'],['平均销售周期',k.sales_cycle_avg_days == null ? undefined : k.sales_cycle_avg_days+'天','渗透率 '+missing(k.marketing_penetration_rate)+' · 三角控单 '+missing(k.triangle_control_completeness)]];
  const target=document.getElementById('salesKpis');target.replaceChildren();
  for(const [label,value,detail] of metrics){const card=document.createElement('div');card.className='kpi';card.append(text('div',label,'kl'),text('div',value,'kv'),text('div',detail,'ks'));target.append(card);}
  renderBars('salesFunnel',Array.isArray(data.funnel)?data.funnel.filter(x=>x&&typeof x==='object').map(x=>({name:x.stage,count:x.count})):[]);
  renderBars('salesScore',data.score_distribution&&typeof data.score_distribution==='object'?Object.entries(data.score_distribution).map(([name,count])=>({name,count})):[]);
  renderRows('salesTopCust',Array.isArray(data.channels)?data.channels.filter(x=>x&&typeof x==='object').map(x=>[x.name,money(x.amount),x.count]):[]);
  renderRows('salesRisk',Array.isArray(data.high_risk_leads)?data.high_risk_leads.filter(x=>x&&typeof x==='object').map(x=>[x.company||'（未映射公司）',x.contact,x.phone,x.score]):[]);
  markSales(true,typeof data.sync_time==='string'?data.sync_time:null);
}
// 仅沿用原来的同源、已脱敏销售读取；失败保留明确标记的历史快照。
fetch('data/sales_dashboard_data.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('销售来源不可用');return response.json();}).then(renderSalesData).catch(()=>markSales(false,snapshotTime));
