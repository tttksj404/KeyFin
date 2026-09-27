import { initTopbar, finCall, recRows, won, $, esc, num, fmt, ymd, parseDate, toast, confirmDialog } from '/common.js';

initTopbar('/subscriptions.html');

let subs = [];
let services = [];
let cards = [];
const S = { filter: 'ALL', open: new Set(), hist: new Map(), svc: '', card: 0, cycle: 'MONTHLY', submitting: false };
const STATUS = { ACTIVE: ['활성', 'badge-pos'], PAUSED: ['일시정지', 'badge-warn'], CANCELED: ['해지됨', 'badge-off'] };
const FILTERS = [['ALL', '전체'], ['ACTIVE', '활성'], ['PAUSED', '일시정지'], ['CANCELED', '해지됨']];
const idOf = (s) => String(s.subscriptionId ?? '');

function showError(message) {
  $('err').textContent = message;
  $('err').classList.toggle('hidden', !message);
}
const md = (s) => { const d = parseDate(s); return d ? `${d.getMonth() + 1}월 ${d.getDate()}일` : ''; };
function dday(s) {
  const d = parseDate(s);
  if (!d) return '';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const n = Math.round((d - today) / 864e5);
  return n === 0 ? '오늘' : n === 1 ? '내일' : n > 1 ? `${n}일 뒤` : '';
}

// ---------- 목록 불러오기 ----------
async function loadList() {
  showError('');
  let payload;
  try {
    payload = await finCall('subList', {});
  } catch (err) {
    showError('정기결제 목록 조회 실패: ' + (err?.message || err));
    if (!subs.length) $('list').innerHTML = '';
    return;
  }
  const rec = payload.REC || {};
  subs = recRows(payload);
  $('s-total').innerHTML = `${fmt(rec.totalMonthlyAmount)}<small>원</small>`;
  $('s-active').textContent = num(rec.activeCount ?? subs.filter((s) => s.status === 'ACTIVE').length);
  $('s-paused').textContent = subs.filter((s) => s.status === 'PAUSED').length;
  renderFilters();
  renderList();
}

// ---------- 상태 색인 ----------
function renderFilters() {
  const box = $('filters');
  box.querySelectorAll('.cat').forEach((b) => b.remove());
  FILTERS.forEach(([k, label]) => {
    const n = k === 'ALL' ? subs.length : subs.filter((s) => s.status === k).length;
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cat' + (k === 'ALL' ? ' all' : '') + (k === S.filter ? ' on' : '');
    b.setAttribute('aria-pressed', k === S.filter);
    b.innerHTML = `<span>${label}</span><em>${n}</em>`;
    b.onclick = () => { S.filter = k; renderFilters(); renderList(); };
    box.appendChild(b);
  });
  requestAnimationFrame(moveInd);
}
function moveInd() {
  const on = $('filters').querySelector('.cat.on');
  const ind = $('cat-ind');
  if (!on) return;
  ind.style.transform = `translate(${on.offsetLeft}px,${on.offsetTop}px)`;
  ind.style.height = on.offsetHeight + 'px';
  ind.style.width = on.offsetWidth + 'px';
}

// ---------- 구독 목록 ----------
function renderList() {
  const list = subs.filter((s) => S.filter === 'ALL' || s.status === S.filter);
  const label = FILTERS.find((f) => f[0] === S.filter)[1];
  $('h1').textContent = S.filter === 'ALL' ? '구독 전체' : `${label} 구독`;
  $('h1-sub').textContent = `${list.length}건`;
  if (!list.length) {
    $('list').innerHTML = `<div class="empty"><b>${S.filter === 'ALL' ? '아직 구독이 없어요' : `${label} 구독이 없어요`}</b>`
      + '<p>오른쪽에서 새 구독을 시작할 수 있어요.</p><button type="button" class="btn btn-secondary btn-md" data-focus-form>새 구독 고르기</button></div>';
    return;
  }
  $('list').innerHTML = list.map((s) => {
    const id = idOf(s);
    const [st, cls] = STATUS[s.status] || [s.status || '상태 미상', 'badge-off'];
    const open = S.open.has(id);
    const daily = s.billingCycle === 'DAILY';
    const cycle = daily ? '매일' : s.billingCycle === 'MONTHLY' ? '매달' : (s.billingCycle || '');
    const amount = daily ? (s.dailyAmount ?? s.paymentAmount) : s.paymentAmount;
    const active = s.status === 'ACTIVE';
    const next = active ? md(s.nextPaymentDate) : '';
    return `<article class="sub${open ? ' open' : ''}${s.status === 'CANCELED' ? ' canceled' : ''}" data-id="${esc(id)}">
      <div class="l1">
        <div><div class="nm">${esc(s.subscriptionName ?? id)}</div>
          <div class="price"><b>${esc(won(amount))}</b>${cycle ? ` · ${esc(cycle)}` : ''}</div></div>
        <div class="next">${s.status === 'CANCELED' ? '결제 끝남' : s.status === 'PAUSED' ? '쉬는 중' : '다음 결제'}<b>${next || '-'}</b>${next ? `<span class="dday">${dday(s.nextPaymentDate)}</span>` : ''}</div>
      </div>
      <div class="l2">
        <span class="badge ${cls}">${esc(st)}</span>
        <span class="spacer"></span>
        <button type="button" class="btn btn-secondary btn-sm" data-act="hist" aria-expanded="${open}">${open ? '이력 접기' : '결제 이력'}</button>
        ${s.status === 'CANCELED' ? '' : `<button type="button" class="btn btn-secondary btn-sm" data-act="toggle">${s.status === 'PAUSED' ? '다시 시작' : '일시정지'}</button>
        <button type="button" class="btn btn-danger-text btn-sm" data-act="cancel">해지</button>`}
      </div>
      ${open ? histHtml(id) : ''}
    </article>`;
  }).join('');
}
function histHtml(id) {
  const h = S.hist.get(id);
  const wrap = (inner) => `<div class="hist"><h4>결제 이력</h4>${inner}</div>`;
  if (h === undefined || h === 'loading') return wrap('<div class="none">불러오는 중이에요</div>');
  if (h instanceof Error) return wrap(`<div class="none fail">이력 조회 실패: ${esc(h.message)}</div>`);
  if (!h.length) return wrap('<div class="none">아직 결제된 적이 없어요.</div>');
  return wrap(`<ol>${h.map((r) => {
    const ok = r.resultCode === 'H0000';
    return `<li><span>${esc(md(r.paymentDate) || r.paymentDate || '')}</span><span>${esc(won(r.paymentAmount))}</span>`
      + `<span class="${ok ? 'ok' : 'fail'}">${ok ? '결제됨' : `실패 · ${esc(r.resultMessage ?? r.resultCode ?? '')}`}</span></li>`;
  }).join('')}</ol>`);
}
async function toggleHistory(id) {
  if (S.open.has(id)) { S.open.delete(id); renderList(); return; }
  S.open.add(id);
  S.hist.set(id, 'loading');
  renderList();
  try {
    S.hist.set(id, recRows(await finCall('subHistory', { subscriptionId: id })));
  } catch (err) {
    S.hist.set(id, new Error(err?.message || String(err)));
  }
  if (S.open.has(id)) renderList();
}

$('list').addEventListener('click', async (e) => {
  if (e.target.closest('[data-focus-form]')) { $('svc').querySelector('input')?.focus(); return; }
  const b = e.target.closest('[data-act]');
  if (!b) return;
  const id = b.closest('.sub').dataset.id;
  const s = subs.find((x) => idOf(x) === id);
  if (!s) return;
  if (b.dataset.act === 'hist') { toggleHistory(id); return; }
  if (b.dataset.act === 'toggle') {
    const resume = s.status === 'PAUSED';
    await act(b, () => finCall('subToggle', { subscriptionId: id, action: resume ? 'ACTIVE' : 'PAUSED' }),
      resume ? `${s.subscriptionName} 구독을 다시 시작했어요` : `${s.subscriptionName} 구독을 잠시 멈췄어요`);
    return;
  }
  if (b.dataset.act === 'cancel') {
    const ok = await confirmDialog({
      title: '구독을 해지할까요?',
      body: `<b>${esc(s.subscriptionName ?? '')}</b> 구독을 해지하면 다음 결제일부터 <b>${esc(won(s.paymentAmount))}</b>이 더 나가지 않아요. 해지한 구독은 다시 시작할 수 없어요.`,
      okLabel: '해지하기',
    });
    if (!ok) return;
    await act(b, () => finCall('subCancel', { subscriptionId: id }), `${s.subscriptionName} 구독을 해지했어요`);
  }
});
async function act(btn, fn, doneMessage) {
  btn.disabled = true;
  try {
    await fn();
    toast(doneMessage);
    S.hist.clear();
    S.open.clear();
    await loadList();
  } catch (err) {
    showError('처리 실패: ' + (err?.message || err));
    btn.disabled = false;
  }
}

// ---------- 새 구독 ----------
function renderServices() {
  const box = $('svc');
  if (!services.length) { box.innerHTML = '<p class="form-msg">구독할 수 있는 서비스가 없어요</p>'; return; }
  if (!services.some((v) => String(v.serviceId) === S.svc)) S.svc = String(services[0].serviceId);
  box.innerHTML = services.map((v) => `<label><input type="radio" name="svc" value="${esc(v.serviceId)}"${String(v.serviceId) === S.svc ? ' checked' : ''} /><span class="dot"></span>`
    + `<span class="t">${esc(v.serviceName)}${v.planName ? `<small>${esc(v.planName)}</small>` : ''}</span><span class="p">월 ${esc(fmt(v.monthlyPrice))}원</span></label>`).join('');
}
function renderFormCards() {
  const box = $('card');
  if (!cards.length) { box.innerHTML = '<p class="form-msg">보유한 카드가 없어요</p>'; return; }
  box.innerHTML = cards.map((c, i) => `<button type="button" data-i="${i}" class="${i === S.card ? 'on' : ''}" aria-pressed="${i === S.card}">`
    + `${esc(String(c.cardName).replace(/\s*카드$/, ''))} ${esc(String(c.cardNo).slice(0, 4))}</button>`).join('');
}
$('svc').addEventListener('change', (e) => { if (e.target.name === 'svc') S.svc = e.target.value; });
$('card').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; S.card = +b.dataset.i; renderFormCards(); };
$('cycle').onclick = (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  S.cycle = b.dataset.v;
  $('cycle').querySelectorAll('button').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
  $('payday-f').classList.toggle('hidden', S.cycle !== 'MONTHLY');
};
const clampDay = (v) => Math.min(31, Math.max(1, Math.round(num(v)) || 1));
$('pd-dn').onclick = () => { $('payday').value = clampDay(num($('payday').value) - 1); };
$('pd-up').onclick = () => { $('payday').value = clampDay(num($('payday').value) + 1); };
$('payday').addEventListener('change', () => { $('payday').value = clampDay($('payday').value); });

function formNote(message, isErr) {
  const note = $('f-note');
  note.className = 'note ' + (isErr ? 'note-neg' : 'note-pos');
  note.textContent = message;
}
$('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (S.submitting) return;
  const card = cards[S.card];
  if (!services.length || !S.svc) { formNote('구독할 서비스를 골라 주세요.', true); return; }
  if (!card) { formNote('결제할 카드가 없어요. 관리자 콘솔에서 카드를 먼저 발급하세요.', true); return; }
  if (!$('start').value) { formNote('시작일을 골라 주세요.', true); return; }
  const monthly = S.cycle === 'MONTHLY';
  const fields = {
    cardNo: String(card.cardNo),
    serviceId: String(S.svc),
    billingCycle: S.cycle,
    startDate: $('start').value.replaceAll('-', ''),
  };
  if (monthly) fields.paymentDay = String(clampDay($('payday').value));
  const btn = $('submit');
  S.submitting = true;
  btn.disabled = true;
  btn.textContent = '등록 중';
  try {
    await finCall('subCreate', fields);
    const v = services.find((x) => String(x.serviceId) === S.svc);
    formNote(`${v?.serviceName ?? '새'} 구독을 시작했어요.`, false);
    S.filter = 'ALL';
    S.hist.clear();
    S.open.clear();
    await loadList();
  } catch (err) {
    formNote('등록 실패: ' + (err?.message || err), true);
  } finally {
    S.submitting = false;
    btn.disabled = false;
    btn.textContent = '구독 시작하기';
  }
});

async function loadServices() {
  try {
    services = recRows(await finCall('subServices', {}));
  } catch (err) {
    services = [];
    showError('구독 서비스 목록 조회 실패: ' + (err?.message || err));
  }
  renderServices();
}
async function loadCards() {
  try {
    cards = recRows(await finCall('cards', {}));
  } catch (err) {
    cards = [];
    showError('내 카드 목록 조회 실패: ' + (err?.message || err));
  }
  renderFormCards();
}

addEventListener('resize', moveInd);
$('start').value = ymd(new Date());
renderFilters();
loadList().then(() => { loadServices(); loadCards(); });
