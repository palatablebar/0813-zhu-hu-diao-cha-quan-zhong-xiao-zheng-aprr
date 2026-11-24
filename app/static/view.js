import {element, pretty} from './client.js';

const labels = {
  READY:'通过', MISMATCH:'差异待复核', PENDING:'待复核', APPROVED:'已签发', HELD:'已暂缓',
  MOVE_CONFLICT:'迁户冲突', MOVE_TARGET_MISSING:'缺目标层', MOVE_REPLAY:'重复挪户',
  MOVE_OVERDRAW:'迁出超量', STRATUM_MISMATCH:'分层不平',
  NO_RESPONDENTS:'无回应户', FRAME_STRATUM_MISMATCH:'分层框不符', FRAME_DUPLICATE:'目标层重复',
  EXCESS_RESPONSE:'回应超户数', UNBALANCED_LINES:'行数不平', ISOLATED_ROWS:'隔离行',
  UNRESOLVED_ISSUES:'存在待处理差异'
};
const headers = ['业务分组', '输入行', '计算值', '参考值', '判定'];

export function badge(status) {
  return element('span', labels[status] || status, {class:'badge', 'data-result':status, title: status});
}

export function snapshot(report, selected, stage) {
  const stats = report.intake;
  document.querySelector('[data-metric="input"]').textContent = stats.input;
  document.querySelector('[data-metric="accepted"]').textContent = stats.accepted;
  document.querySelector('[data-metric="isolated"]').textContent = stats.rejected;
  document.querySelector('[data-metric="cases"]').textContent = report.cases?.length ?? '—';
  const table = document.querySelector('#rows');
  table.replaceChildren();
  const head = element('tr');
  const body = table.createTBody();
  if (stage === 'intake') {
    head.append(...['源行', '记录键', '业务分组', '原因码'].map(title => element('th', title, {scope:'col'})));
    for (const item of stats.isolation) {
      const tr = body.insertRow();
      tr.append(...[item.line,item.record,item.case,item.reason].map(value=>element('td',value)));
    }
    if (!stats.isolation.length) body.insertRow().insertCell().textContent = '当前文件没有隔离行';
  } else {
    head.append(...headers.map(title => element('th', title, {scope:'col'})));
    for (const row of report.cases || []) {
      const tr = body.insertRow();
      const button = element('button',row.case,{type:'button','data-case':row.case,'aria-pressed':String(row.case===selected)});
      tr.insertCell().append(button);
      [row.records.length, row.measure?.value ?? '—', row.measure?.expected ?? '—'].forEach(value=>tr.insertCell().textContent=value);
      tr.insertCell().append(badge(row.status));
    }
  }
  table.createTHead().append(head);
  const picked = report.cases?.find(row=>row.case===selected);
  document.querySelector('#detail-title').textContent = picked ? `分组 ${picked.case}` : '采信摘要';
  const shown = picked ? detailOf(picked) : stats.reasons;
  document.querySelector('#detail').textContent = pretty(shown);
  const blocked = report.balance?.blockers || {};
  const codes = Object.keys(blocked);
  const unreachable = report.balance ? ` · ${report.balance.releasable ? '可签发' : '不可签发'}` : '';
  document.querySelector('#counts').textContent = report.balance
    ? `行数 ${report.balance.accounted}/${report.balance.input} · ${report.balance.ready} 组通过 · ${report.balance.strata?.length ?? 0} 层${codes.length ? ` · 阻断 ${codes.join('、')}` : ''}${unreachable}`
    : `采信 ${stats.accepted} 行 · 隔离 ${stats.rejected} 行`;
}

function ledgerLines(ledger) {
  return ledger.map(layer =>
    `分层 ${layer.stratum} 目标 ${layer.target}｜迁前 ${layer.before?.households ?? '—'}/${layer.before?.responded ?? '—'} 户 权重 ${layer.before?.weight ?? '—'}｜` +
    `迁出 ${layer.moved_out?.households ?? 0}/${layer.moved_out?.responded ?? 0} 迁入 ${layer.moved_in?.households ?? 0}/${layer.moved_in?.responded ?? 0}｜` +
    `迁后 ${layer.after?.households ?? layer.weighted ?? '—'}/${layer.after?.responded ?? '—'} 户 权重 ${layer.after?.weight ?? '—'} ${layer.balanced ? '平' : '不平'}`);
}

function detailOf(item) {
  if (item.blocker) {
    const details = item.blocker.details ? `\n${pretty(item.blocker.details)}` : '';
    const ledger = item.ledger || item.prep?.ledger;
    const lines = ledger?.length ? `\n${ledgerLines(ledger).join('\n')}` : '';
    return `阻断 ${labels[item.blocker.code] || item.blocker.code} · 记录键 ${item.blocker.records.join(', ') || '—'}${details}${lines}`;
  }
  const ledger = item.measure?.strata ?? item.prep?.ledger;
  if (ledger?.length) {
    const moves = (item.prep?.moves || item.measure?.moves || []).map(m => `${m.record}: 层${m.from}→层${m.to} ${m.households}户`);
    const move = moves.length ? `\n迁户记录 ${moves.join('；')}` : '';
    return `${ledgerLines(ledger).join('\n')}${move}`;
  }
  return item.measure?.evidence ?? item.prep?.details ?? {原因: item.status};
}

export function history(items, active) {
  const target = document.querySelector('#history');
  target.replaceChildren();
  for (const run of items) {
    const button = element('button', run.id.slice(0,10), {'data-run':run.id,'aria-pressed':String(run.id===active),type:'button'});
    const item = element('li');
    item.append(button, badge(run.status));
    target.append(item);
  }
  if (!items.length) target.append(element('li','尚无执行批次'));
}
