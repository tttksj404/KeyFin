import { initTopbar, finCall, recRows, won, $, esc, num, fmt, ymd, parseDate, toast, confirmDialog } from '/common.js';

initTopbar('/history.html');

let cards = [];
let rows = [];
const S = { card: 0, q: '', start: '', end: '', loading: false, seq: 0 };
const DOW = ['일', '월', '화', '수', '목', '금', '토'];
const isCanceled = (tx) => /취소|CANCEL/i.test(`${tx.transactionStatus ?? ''}${tx.status ?? ''}${tx.cardStatus ?? ''}`);
const amountOf = (tx) => num(tx.transactionBalance ?? tx.paymentBalance);

function showError(message) {
  $('err').textContent = message;
  $('err').classList.toggle('hidden', !message);
}

// ---------- 카드 색인 ----------
function renderCards() {
  const box = $('cards');
  box.querySelectorAll('.cat').forEach((b) => b.remove());
  cards.forEach((c, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cat card-it' + (i === S.card ? ' on' : '');
    b.setAttribute('aria-pressed', i === S.card);
    b.innerHTML = `<span>${esc(c.cardName)}<i class="sub4">${esc(String(c.cardNo).slice(0, 4))} ····</i></span>`;
    b.onclick = () => { if (S.card === i) return; S.card = i; renderCards(); loadHistory(); };
    box.appendChild(b);
  });
  requestAnimationFrame(moveInd);
}
function moveInd() {
  const on = $('cards').querySelector('.cat.on');
  const ind = $('cat-ind');
  if (!on) return;
  ind.style.transform = `translate(${on.offsetLeft}px,${on.offsetTop}px)`;
  ind.style.height = on.offsetHeight + 'px';
  ind.style.width = on.offsetWidth + 'px';
  ind.style.borderRadius = getComputedStyle(on).borderRadius;
}

// ---------- 목록 ----------
const fmtTime = (t) => { const s = String(t ?? '').replace(/\D/g, ''); return s.length >= 4 ? `${s.slice(0, 2)}:${s.slice(2, 4)}` : ''; };
function dayTitle(key) {
  const d = parseDate(key);
  if (!d) return '날짜 미상';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - d) / 864e5);
  const base = `${d.getMonth() + 1}월 ${d.getDate()}일 ${DOW[d.getDay()]}요일`;
  return diff === 0 ? `오늘 · ${base}` : diff === 1 ? `어제 · ${base}` : base;
}
function render() {
  const q = S.q.trim().toLowerCase();
  const list = rows.filter((t) => !q || String(t.merchantName ?? '').toLowerCase().includes(q));
  const ok = rows.filter((t) => !isCanceled(t));
  $('s-total').innerHTML = `${fmt(ok.reduce((a, t) => a + amountOf(t), 0))}<small>원</small>`;
  $('s-ok').textContent = ok.length;
  $('s-cancel').textContent = rows.length - ok.length;
  $('s-label').textContent = `${S.start.slice(5).replace('-', '.')}부터 ${S.end.slice(5).replace('-', '.')}까지 결제`;
  const box = $('list');
  if (S.loading) { box.innerHTML = '<div class="loading">결제 내역을 불러오는 중이에요</div>'; return; }
  if (!list.length) {
    box.innerHTML = S.q
      ? `<div class="empty"><b>'${esc(S.q)}' 결제가 없어요</b><p>가맹점 이름을 다시 확인하거나 기간을 넓혀 보세요.</p><button type="button" class="btn btn-secondary btn-md" data-widen>3개월로 넓히기</button></div>`
      : '<div class="empty"><b>이 기간에는 결제가 없어요</b><p>기간을 넓히거나 결제 페이지에서 새로 결제해 보세요.</p><a class="btn btn-primary btn-md" href="/pay.html" style="text-decoration:none">결제하러 가기</a></div>';
    return;
  }
  const byDay = new Map();
  [...list]
    .sort((a, b) => `${b.transactionDate}${b.transactionTime}`.localeCompare(`${a.transactionDate}${a.transactionTime}`))
    .forEach((t) => {
      const k = String(t.transactionDate ?? '');
      if (!byDay.has(k)) byDay.set(k, []);
      byDay.get(k).push(t);
    });
  box.innerHTML = [...byDay].map(([d, ts]) => {
    const sum = ts.filter((t) => !isCanceled(t)).reduce((a, t) => a + amountOf(t), 0);
    return `<div class="grp"><h3>${dayTitle(d)}<em>${ts.length}건 · ${fmt(sum)}원</em></h3>${ts.map((t) => {
      const canceled = isCanceled(t);
      const no = esc(t.transactionUniqueNo ?? '');
      const meta = [
        t.categoryName ? esc(t.categoryName) : '',
        fmtTime(t.transactionTime),
        no ? `거래번호 <span class="num">${no}</span>` : '',
      ].filter(Boolean).join(' · ');
      return `<div class="tx${canceled ? ' canceled' : ''}">
        <div><div class="nm">${esc(t.merchantName ?? t.merchantId ?? '')}</div><div class="meta">${meta}</div></div>
        <div class="amt">${canceled ? `<s>${fmt(amountOf(t))}원</s><small>취소됨</small>` : `${fmt(amountOf(t))}원`}</div>
        <div class="act">${canceled || !no ? '' : `<button type="button" class="btn btn-tertiary btn-sm" data-no="${no}">결제 취소</button>`}</div>
      </div>`;
    }).join('')}</div>`;
  }).join('');
}

async function loadHistory() {
  const c = cards[S.card];
  if (!c) return;
  showError('');
  const seq = ++S.seq; // 카드·기간을 빠르게 바꿀 때 늦게 온 이전 응답이 화면을 덮지 않게
  S.loading = true;
  rows = []; // 불러오는 동안 이전 카드 합계를 보여주지 않게
  render();
  try {
    const payload = await finCall('transactions', {
      cardNo: String(c.cardNo),
      cvc: String(c.cvc),
      startDate: S.start.replaceAll('-', ''),
      endDate: S.end.replaceAll('-', ''),
    });
    if (seq !== S.seq) return;
    rows = recRows(payload);
  } catch (err) {
    if (seq !== S.seq) return;
    rows = [];
    showError('내역 조회 실패: ' + (err?.message || err));
  }
  S.loading = false;
  render();
}

// ---------- 결제 취소 ----------
$('list').addEventListener('click', async (e) => {
  if (e.target.closest('[data-widen]')) { setRange(90); return; }
  const btn = e.target.closest('[data-no]');
  if (!btn) return;
  const tx = rows.find((t) => String(t.transactionUniqueNo) === btn.dataset.no);
  const c = cards[S.card];
  if (!tx || !c) return;
  const ok = await confirmDialog({
    title: '결제를 취소할까요?',
    body: `<b>${esc(tx.merchantName ?? '')}</b>에서 결제한 <b>${esc(won(amountOf(tx)))}</b>을 취소해요. 취소한 결제는 되돌릴 수 없어요.`,
    okLabel: '결제 취소',
  });
  if (!ok) return;
  btn.disabled = true;
  try {
    // 스펙엔 Long이지만 실제 API는 문자열만 받는다 — 문자열로 전송
    await finCall('cancel', { cardNo: String(c.cardNo), cvc: String(c.cvc), transactionUniqueNo: String(tx.transactionUniqueNo) });
    toast(`${tx.merchantName ?? ''} ${won(amountOf(tx))} 결제를 취소했어요`);
    await loadHistory();
  } catch (err) {
    showError('결제 취소 실패: ' + (err?.message || err));
    btn.disabled = false;
  }
});

// ---------- 기간 ----------
function setRange(days) {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - days);
  S.start = ymd(start);
  S.end = ymd(end);
  $('start').value = S.start;
  $('end').value = S.end;
  document.querySelectorAll('#range button').forEach((b) => b.classList.toggle('on', +b.dataset.days === days));
  loadHistory();
}
$('range').onclick = (e) => { const b = e.target.closest('button'); if (b) setRange(+b.dataset.days); };
$('load').onclick = () => {
  const s = $('start').value;
  const en = $('end').value;
  if (!s || !en || s > en) { showError('시작일이 종료일보다 늦어요. 기간을 다시 골라 주세요.'); return; }
  S.start = s;
  S.end = en;
  document.querySelectorAll('#range button').forEach((b) => b.classList.remove('on'));
  loadHistory();
};
$('q').addEventListener('input', (e) => { S.q = e.target.value; render(); });
addEventListener('resize', moveInd);

// ---------- 시작 ----------
async function init() {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 30); // '1개월' 프리셋(30일)과 같게
  S.start = ymd(start);
  S.end = ymd(end);
  $('start').value = S.start;
  $('end').value = S.end;
  try {
    cards = recRows(await finCall('cards', {}));
  } catch (err) {
    showError('내 카드 목록 조회 실패: ' + (err?.message || err));
    $('list').innerHTML = '';
    return;
  }
  if (!cards.length) {
    $('list').innerHTML = '<div class="empty"><b>보유한 카드가 없어요</b><p>관리자 콘솔에서 카드를 먼저 발급하세요.</p></div>';
    return;
  }
  renderCards();
  loadHistory();
}

init();
