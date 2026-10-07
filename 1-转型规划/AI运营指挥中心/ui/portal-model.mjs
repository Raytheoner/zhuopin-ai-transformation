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
  return {label: !ok ? '加载失败 · 历史快照' : !syncTime ? '更新时间缺失' : '已加载 · 请核对更新时间', sourceTime: syncTime || '来源未提供更新时间'};
}
export function displayMoney(value) {
  if ((typeof value !== 'number' && typeof value !== 'string') || String(value).trim()==='' || !Number.isFinite(Number(value))) return '来源未提供';
  return '¥'+Math.round(Number(value)/10000).toLocaleString('zh-CN')+'万';
}
export function salesSummary(data) {
  return {leads:data.kpis?.total_leads==null?'来源线索数未提供':'来源线索数 '+data.kpis.total_leads,
    risk:Array.isArray(data.high_risk_leads)?'来源明细 '+data.high_risk_leads.length+' 条 · 联系方式沿用脱敏来源':'来源明细未提供',
    conversion:'转化率以来源口径为准',insight:'按当前来源显示评分分布，缺失分段不推断为零。'};
}
