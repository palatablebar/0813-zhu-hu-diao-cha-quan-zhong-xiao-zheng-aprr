import {element} from './client.js';

function zone(target, className, text) {
  const box = element('div', undefined, {class:className});
  if (text) box.append(element('span',text));
  target.append(box);
  return box;
}

function fill(layer, value, max, label) {
  const mark = zone(layer, 'mark-piece', label);
  mark.style.setProperty('--part', `${Math.max(0,Math.min(100,100*value/Math.max(1,max)))}%`);
  return mark;
}

export function visualize(report, selected) {
  const target = document.querySelector('#visual');
  const row = report.cases?.find(item=>item.case===selected && (item.measure || item.prep?.ledger || item.ledger));
  target.replaceChildren();
  if (!row) { target.append(element('p','该分组暂无计算值')); return; }
  const strata = row.measure?.strata ?? row.prep?.ledger ?? row.ledger ?? [];
  if (strata.length) { renderStrata(target, strata); return; }
  const {evidence:e, value, expected, unit} = row.measure;
  render(target, e, value, expected, unit);
}

function renderStrata(target, strata) {
  const sheet = zone(target,'weight-sheet');
  let total = 0;
  let expected = 0;
  for (const layer of strata) {
    const after = layer.after ?? {households: layer.weighted, weight: layer.weight};
    const item = zone(sheet,'weight-slip',`分层 ${layer.stratum}`);
    item.append(element('strong', after.weight ?? '—'));
    item.append(element('small', `目标 ${layer.target ?? '缺'} · 迁后 ${after.households} 户`));
    if (layer.balanced) item.dataset.result = 'READY';
    total += after.households;
    expected += layer.target ?? 0;
  }
  zone(target,'weight-sum',`逐层合计 ${total} / ${expected} 户`);
}

function render(target,e,value,expected,unit) {
  const rows=zone(target,'weight-sheet');
  for(const [s,w] of Object.entries(e)) {
    const item=zone(rows,'weight-slip',`分层 ${s}`);
    item.append(element('strong',w));
  }
  zone(target,'weight-sum',`加权覆盖 ${value} / ${expected} 户`);
}
