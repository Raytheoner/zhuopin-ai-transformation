import test from 'node:test';
import assert from 'node:assert/strict';
import {parseView, filterApps, salesState, displayMoney, salesSummary} from '../ui/portal-model.mjs';
test('未知hash返回首页，允许全部公共视图', () => {
  assert.equal(parseView('#unknown'), 'overview');
  assert.equal(parseView('#<img>'), 'overview');
  for (const view of ['overview','apps','tasks','review','system','procurement','quality','finance','sales','operations','engineering']) {
    assert.equal(parseView('#'+view), view);
  }
});
test('中文空格组合检索、部门限制、空结果及重置', () => {
  const apps = [
    {id:'sc8',name:'SC8 客户订单交期',department:'采购',stage:'试用',href:'http://192.168.100.51:8091/'},
    {id:'q2',name:'Q2 8D报告',department:'质量',stage:'mock',href:'http://192.168.100.51:8098/'},
    {id:'r',name:'工程研发辅助',department:'工程研发',stage:'规划',href:null}
  ];
  assert.equal(filterApps(apps,{query:'  SC8  交期 ',department:'采购'}).length,1);
  assert.equal(filterApps(apps,{query:'SC8',department:'质量'}).length,0);
  assert.equal(filterApps(apps,{query:'无匹配'}).length,0);
  assert.equal(filterApps(apps).length,3);
  assert.equal(filterApps(apps,{query:'研发'})[0].href,null);
});
test('销售加载失败、更新时间缺失与已加载分开', () => {
  assert.deepEqual(salesState({ok:false,syncTime:'2026-06-25'}),{label:'加载失败 · 历史快照',sourceTime:'2026-06-25'});
  assert.equal(salesState({ok:true,syncTime:null}).label,'更新时间缺失');
  assert.equal(salesState({ok:true,syncTime:'2026-10-07T16:00:00+08:00'}).label,'已加载 · 请核对更新时间');
});
test('金额缺资料不转换为零，真实零与数值仍可显示', () => {
  for(const value of [null,undefined,'',' ',false,{},[],'bad']) assert.equal(displayMoney(value),'来源未提供');
  assert.equal(displayMoney(0),'¥0万');
  assert.equal(displayMoney('120000'),'¥12万');
});
test('加载后清除旧快照统计和洞察，不沿用旧总数', () => {
  assert.deepEqual(salesSummary({kpis:{total_leads:22},high_risk_leads:[{}]}),{leads:'来源线索数 22',risk:'来源明细 1 条 · 联系方式沿用脱敏来源',conversion:'转化率以来源口径为准',insight:'按当前来源显示评分分布，缺失分段不推断为零。'});
  assert.equal(salesSummary({}).leads,'来源线索数未提供');
});
