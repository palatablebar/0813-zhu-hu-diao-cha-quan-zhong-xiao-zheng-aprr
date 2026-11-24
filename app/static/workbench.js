import {request} from './client.js';
import {snapshot, history} from './view.js';
import {visualize} from './plots.js';

const form = document.querySelector('#source');
const file = document.querySelector('#file');
const profile = document.querySelector('#profile');
const status = document.querySelector('#notice');
const detail = document.querySelector('#review');
const evidence = document.querySelector('#evidence');
const stages = [...document.querySelectorAll('[data-stage]')];
let stage = 'balance';
let report, selected, batch, running = false;

function source() {
  const data = new FormData();
  if (file.files.length) data.append('file',file.files[0]);
  else data.append('sample',profile.value);
  return data;
}

function announce(text, failure = false) {
  status.textContent = text;
  status.dataset.failure = String(failure);
}

function blockersText(report) {
  const items = Object.values(report?.balance?.blockers || {});
  if (!items.length) return '';
  return ' · 待处理 ' + items.map(item =>
    `${item.code}${item.records.length ? `(${item.records.join(',')})` : ''}`).join('、');
}

function draw() {
  if (!report) return;
  snapshot(report, selected, stage);
  visualize(report, selected);
  for (const button of stages) button.setAttribute('aria-pressed',String(button.dataset.stage===stage));
  document.querySelector('#panel-title').textContent = stages.find(button => button.dataset.stage===stage)?.textContent || '运行对账';
  detail.hidden = !batch;
  if (batch) {
    const blocked = batch.attempts?.filter(item => item.outcome === 'BLOCKED') || [];
    const last = blocked[blocked.length - 1];
    const suffix = last ? ` · 已挡住 ${blocked.length} 次发布尝试` : '';
    const readiness = report.balance.releasable ? '可签发' : '不可签发（提交后会列出记录键）';
    document.querySelector('#run-status').textContent = `${batch.id.slice(0,10)} · ${batch.status} · r${batch.revision} · ${readiness}${suffix}`;
    detail.querySelector('[value="APPROVED"]').disabled = batch.status==='APPROVED';
    detail.querySelector('[value="HELD"]').disabled = batch.status==='APPROVED';
    evidence.href = `/api/runs/${batch.id}/evidence`;
  }
}

function show(payload, committed = false) {
  batch = committed ? payload : null;
  report = committed ? payload.report : payload;
  detail.elements.note.value = batch?.note || '';
  selected = report.cases?.[0]?.case;
  draw();
}

async function refresh() {
  const data = await request('/api/runs');
  history(data.items, batch?.id);
}

async function perform(action) {
  if (running) return;
  running = true;
  document.body.setAttribute('aria-busy','true');
  announce('处理中…');
  try { await action(); }
  catch (error) {
    const keys = error.records?.length ? ` · 记录键 ${error.records.join(', ')}` : '';
    announce(`${error.message}${keys}`, true);
  }
  finally { running = false; document.body.removeAttribute('aria-busy'); }
}

function preview(next) {
  return perform(async () => {
    const payload = await request(`/api/stages/${next}`,{method:'POST',body:source()});
    stage = next;
    show(payload);
    announce('阶段预览已更新');
    await refresh();
  });
}

stages.forEach(button => button.addEventListener('click',()=>preview(button.dataset.stage)));
form.addEventListener('submit', event => {
  event.preventDefault();
  perform(async () => {
    const result = await request('/api/runs',{method:'POST',body:source()});
    stage = 'balance'; show(result,true);
    announce(`批次已保存${blockersText(result.report)}`); await refresh();
  });
});
const filename = document.querySelector('#file-name');
profile.addEventListener('change',()=>{file.value=''; filename.textContent=''; preview(stage);});
file.addEventListener('change',()=>{filename.textContent=file.files[0]?.name || ''; preview(stage);});
document.querySelector('#rows').addEventListener('click',event=>{
  const button = event.target.closest('[data-case]');
  if (button) { selected = button.dataset.case; draw(); document.querySelector(`[data-case="${CSS.escape(selected)}"]`).focus(); }
});
document.querySelector('#history').addEventListener('click',event=>{
  const button = event.target.closest('[data-run]');
  if (button) perform(async()=>{
    const result = await request(`/api/runs/${button.dataset.run}`);
    stage='balance'; show(result,true); announce('已载入历史批次'); await refresh();
  });
});
detail.addEventListener('submit',event=>{
  event.preventDefault();
  const note = detail.elements.note.value;
  const wanted = event.submitter.value;
  perform(async()=>{
    const payload={status:wanted,revision:batch.revision,note};
    try {
      const result=await request(`/api/runs/${batch.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      show(result,true); announce(result.status==='APPROVED'?'批次已签发':'批次已暂缓');
      await refresh();
    } catch (error) {
      if (error.code === 'UNRESOLVED_ISSUES') {
        // 发布失败：旧版本与复核意见都保留，重新载入批次以显示失败尝试。
        const current = await request(`/api/runs/${batch.id}`);
        show(current,true);
        detail.elements.note.value = note;
        await refresh();
      }
      throw error;
    }
  });
});
preview(stage);
