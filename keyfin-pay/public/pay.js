import { initTopbar, finCall, recRows, $, esc, num, fmt, ymd } from '/common.js';

initTopbar('/pay.html');

let merchants = [];
let cats = [];
let cards = null; // null = 불러오는 중, [] = 카드 없음
const S = { cat: '전체', q: '', merchant: null, amount: '', card: 0, busy: false };
const mobile = () => matchMedia('(max-width:900px)').matches;

// ---------- 초성 ----------
const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const choOf = (s) => [...s].map((ch) => { const c = ch.charCodeAt(0) - 0xAC00; return c >= 0 && c < 11172 ? CHO[Math.floor(c / 588)] : ch; }).join('');
const isCho = (q) => /^[ㄱ-ㅎ\s]+$/.test(q);
const headOf = (n) => {
  const c = n.charCodeAt(0);
  if (c >= 0xAC00 && c <= 0xD7A3) { const h = CHO[Math.floor((c - 0xAC00) / 588)]; return { ㄲ: 'ㄱ', ㄸ: 'ㄷ', ㅃ: 'ㅂ', ㅆ: 'ㅅ', ㅉ: 'ㅈ' }[h] || h; }
  return /[a-z]/i.test(n[0]) ? 'ABC' : '#';
};
const ARROW = '<svg viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M4 10L10 4M5.2 4H10v4.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function showError(message) {
  $('err').textContent = message;
  $('err').classList.toggle('hidden', !message);
}

// ---------- 업종 색인 ----------
function renderCats() {
  const box = $('cats');
  box.querySelectorAll('.cat').forEach((b) => b.remove());
  const items = [['전체', merchants.length], ...cats.map((c) => [c, merchants.filter((m) => m.subcategoryName === c).length])];
  for (const [c, n] of items) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cat' + (c === '전체' ? ' all' : '') + (c === S.cat ? ' on' : '');
    b.setAttribute('aria-pressed', c === S.cat);
    b.innerHTML = `<span>${esc(c)}</span><em>${n}</em>`;
    b.onclick = () => { S.cat = c; S.q = ''; $('q').value = ''; renderCats(); renderList(); $('list').scrollTop = 0; };
    box.appendChild(b);
  }
  requestAnimationFrame(moveInd);
}
function moveInd() {
  const on = $('cats').querySelector('.cat.on');
  const ind = $('cat-ind');
  if (!on) return;
  ind.style.transform = `translate(${on.offsetLeft}px,${on.offsetTop}px)`;
  ind.style.height = on.offsetHeight + 'px';
  ind.style.width = on.offsetWidth + 'px';
  if (mobile()) on.scrollIntoView({ inline: 'nearest', block: 'nearest' });
}

// ---------- 가맹점 목록 ----------
function hl(name, q) {
  if (!q || isCho(q)) return esc(name);
  const i = name.toLowerCase().indexOf(q.toLowerCase());
  return i < 0 ? esc(name) : esc(name.slice(0, i)) + '<mark>' + esc(name.slice(i, i + q.length)) + '</mark>' + esc(name.slice(i + q.length));
}
function match(m, q) {
  if (!q) return true;
  if (isCho(q)) return choOf(m.name).replace(/\s/g, '').includes(q.replace(/\s/g, ''));
  const t = q.toLowerCase();
  return m.name.toLowerCase().includes(t) || m.subcategoryName.toLowerCase().includes(t);
}
function rowHtml(m, showSub) {
  const sel = S.merchant && S.merchant.finMerchantId === m.finMerchantId ? ' sel' : '';
  return `<button type="button" class="row${sel}" data-id="${esc(m.finMerchantId)}"><span class="nm">${hl(m.name, S.q.trim())}</span>`
    + `${showSub ? `<span class="sub">${esc(m.subcategoryName)}</span>` : ''}${ARROW}</button>`;
}
function renderList() {
  const q = S.q.trim();
  const pool = merchants.filter((m) => (S.cat === '전체' || m.subcategoryName === S.cat) && match(m, q));
  const list = $('list');
  if (!pool.length) {
    list.innerHTML = q
      ? `<div class="empty">'${esc(q)}'에 맞는 가맹점이 없어요<small>초성이나 업종 이름으로 다시 찾아보세요</small></div>`
      : '<div class="empty">등록된 가맹점이 없어요</div>';
    return;
  }
  let groups;
  if (q) groups = [['검색 결과', pool, true]];
  else if (S.cat === '전체') groups = cats.map((c) => [c, pool.filter((m) => m.subcategoryName === c), false]);
  else if (pool.length > 12) {
    const map = new Map();
    [...pool].sort((a, b) => a.name.localeCompare(b.name, 'ko')).forEach((m) => {
      const h = headOf(m.name);
      if (!map.has(h)) map.set(h, []);
      map.get(h).push(m);
    });
    groups = [...map].map(([h, ms]) => [h, ms, false]);
  } else groups = [[S.cat, pool, false]];
  list.innerHTML = groups.filter((g) => g[1].length)
    .map(([t, ms, sub]) => `<div class="grp"><h3>${esc(t)}<em>${ms.length}</em></h3><div class="rows">${ms.map((m) => rowHtml(m, sub)).join('')}</div></div>`)
    .join('');
}
const byId = (id) => merchants.find((m) => String(m.finMerchantId) === String(id));
$('list').addEventListener('click', (e) => { const r = e.target.closest('.row'); if (r) pick(byId(r.dataset.id)); });

// ---------- 최근 결제: 첫 번째 카드의 최근 90일 승인 내역에서 가맹점 4곳 ----------
async function loadRecent() {
  const c = cards?.[0];
  if (!c) return;
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 90);
  let rows;
  try {
    rows = recRows(await finCall('transactions', {
      cardNo: String(c.cardNo), cvc: String(c.cvc),
      startDate: ymd(start).replaceAll('-', ''), endDate: ymd(end).replaceAll('-', ''),
    }));
  } catch {
    return; // 최근 결제는 부가 정보라 실패해도 조용히 숨긴다
  }
  const seen = new Set();
  const recent = [];
  rows
    .filter((t) => !/취소|CANCEL/i.test(`${t.cardStatus ?? ''}${t.transactionStatus ?? ''}${t.status ?? ''}`))
    .sort((a, b) => `${b.transactionDate}${b.transactionTime}`.localeCompare(`${a.transactionDate}${a.transactionTime}`))
    .forEach((t) => {
      // 가맹점 목록은 이름으로 중복을 걸러 대표 ID 만 남기므로 ID 가 안 맞으면 이름으로 찾는다
      const m = byId(t.merchantId) || merchants.find((x) => x.name === t.merchantName);
      if (!m || seen.has(m.finMerchantId) || recent.length >= 4) return;
      seen.add(m.finMerchantId);
      recent.push({ m, amount: num(t.transactionBalance ?? t.paymentBalance) });
    });
  if (!recent.length) return;
  const box = $('recent');
  box.innerHTML = recent.map(({ m, amount }) => `<button type="button" class="rc" data-id="${esc(m.finMerchantId)}" data-a="${amount}">`
    + `<b>${esc(m.name)}</b><span>지난번 <i>${fmt(amount)}</i>원</span></button>`).join('');
  box.classList.remove('hidden');
  box.onclick = (e) => {
    const b = e.target.closest('.rc');
    if (!b || S.busy) return;
    pick(byId(b.dataset.id));
    S.amount = String(Math.min(99999999, num(b.dataset.a)));
    renderTicket();
  };
}

// ---------- 전표 ----------
function pick(m) {
  if (!m || S.busy) return;
  S.merchant = m;
  showEntry();
  document.querySelectorAll('.row.sel').forEach((r) => r.classList.remove('sel'));
  document.querySelector(`.row[data-id="${CSS.escape(String(m.finMerchantId))}"]`)?.classList.add('sel');
  renderTicket();
  openReg();
}
function renderPad() {
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '00', '0', 'del'];
  $('pad').innerHTML = keys.map((k) => (k === 'del'
    ? '<button type="button" class="fn" data-k="del" aria-label="지우기"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 5.5h10a1.5 1.5 0 011.5 1.5v10a1.5 1.5 0 01-1.5 1.5H9L3.5 12z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M11.5 9.5l5 5m0-5l-5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>'
    : `<button type="button" data-k="${k}"${k === '00' ? ' class="fn"' : ''}>${k}</button>`)).join('');
  $('pad').onclick = (e) => { const b = e.target.closest('button'); if (b) press(b.dataset.k); };
  $('quick').onclick = (e) => {
    const b = e.target.closest('button');
    if (!b || S.busy || !$('receipt').hidden) return;
    S.amount = String(Math.min(99999999, num(S.amount) + num(b.dataset.add)));
    setNote('', false);
    renderTicket();
  };
}
function press(k) {
  if (S.busy || !$('receipt').hidden) return;
  if (k === 'del') S.amount = S.amount.slice(0, -1);
  else { const next = (S.amount + k).replace(/^0+/, ''); if (next.length <= 8) S.amount = next; }
  setNote('', false);
  renderTicket();
}
const CARD_ART = ['c1', 'c2', 'c3'];
const shortName = (name) => String(name).replace(/\s*카드$/, '').trim() || String(name);
function renderCards() {
  const box = $('cards');
  if (cards === null) { box.innerHTML = '<p class="cards-msg">카드를 불러오는 중이에요</p>'; $('card-nm').textContent = ''; return; }
  if (!cards.length) { box.innerHTML = '<p class="cards-msg">보유한 카드가 없어요. 관리자 콘솔에서 카드를 먼저 발급하세요.</p>'; $('card-nm').textContent = ''; return; }
  box.innerHTML = cards.map((c, i) => `<button type="button" class="cc ${CARD_ART[i % 3]}${i === S.card ? ' on' : ''}" data-i="${i}" aria-pressed="${i === S.card}" aria-label="${esc(c.cardName)}">`
    + `<b>${esc(shortName(c.cardName))}</b><i>${esc(String(c.cardNo).slice(0, 4))} ••••</i></button>`).join('');
  $('card-nm').textContent = cards[S.card].cardName;
  box.onclick = (e) => { const b = e.target.closest('.cc'); if (b && !S.busy) { S.card = +b.dataset.i; renderCards(); } };
}
function renderTicket() {
  const m = S.merchant;
  const a = num(S.amount);
  $('t-nm').textContent = m ? m.name : '가맹점을 고르세요';
  $('t-nm').classList.toggle('ph', !m);
  $('t-meta').innerHTML = m ? `${esc(m.subcategoryName)} · 가맹점 <i>${esc(m.finMerchantId)}</i>` : '목록이나 최근 결제에서 고르면 여기에 찍혀요';
  $('t-num').textContent = fmt(a);
  $('t-num').classList.toggle('zero', !a);
  const note = $('t-note');
  if (!note.classList.contains('err')) note.textContent = a ? '' : '숫자 키로도 입력할 수 있어요';
  const noCard = !cards?.length;
  const btn = $('pay');
  btn.disabled = !m || !a || noCard || S.busy;
  btn.innerHTML = S.busy ? '승인 요청 중'
    : cards === null ? '카드를 불러오는 중'
      : noCard ? '결제할 카드가 없어요'
        : !m ? '가맹점을 먼저 고르세요'
          : !a ? '금액을 입력하세요'
            : `${fmt(a)}원 결제<span class="ar">↗</span>`;
}
function setNote(message, isErr) {
  const note = $('t-note');
  note.className = 'amt-note' + (isErr ? ' err' : '');
  note.textContent = message;
}
function showEntry() { $('receipt').hidden = true; $('entry').hidden = false; setNote('', false); }
function printer(busy) {
  $('printer').classList.toggle('busy', busy);
  $('p-st').textContent = busy ? '인쇄 중' : '대기 중';
}

async function pay() {
  if ($('pay').disabled || S.busy) return;
  const m = S.merchant;
  const c = cards[S.card];
  const amount = String(num(S.amount));
  S.busy = true;
  setNote('', false);
  renderTicket();
  printer(true);
  try {
    // 스펙엔 Long이지만 실제 API는 문자열만 받는다(숫자로 보내면 Q1001) — 전 필드 문자열로 전송
    const payload = await finCall('pay', {
      cardNo: String(c.cardNo),
      cvc: String(c.cvc),
      merchantId: String(m.finMerchantId),
      paymentBalance: amount,
    });
    showReceipt(payload.REC || {}, m, c, amount);
  } catch (err) {
    setNote('결제 실패: ' + (err?.message || err), true);
  } finally {
    S.busy = false;
    printer(false);
    renderTicket();
  }
}
function showReceipt(rec, m, c, amount) {
  const d = String(rec.transactionDate ?? '').replace(/\D/g, '');
  const t = String(rec.transactionTime ?? '').replace(/\D/g, '');
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  $('r-time').textContent = d.length === 8
    ? `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}${t.length >= 4 ? ` ${t.slice(0, 2)}:${t.slice(2, 4)}${t.length >= 6 ? ':' + t.slice(4, 6) : ''}` : ''}`
    : `${now.getFullYear()}.${p(now.getMonth() + 1)}.${p(now.getDate())} ${p(now.getHours())}:${p(now.getMinutes())}:${p(now.getSeconds())}`;
  const no = String(rec.transactionUniqueNo ?? '-');
  const cardNo = String(c.cardNo);
  const lines = [
    ['가맹점', rec.merchantName || m.name],
    ['업종', rec.categoryName || m.subcategoryName],
    ['카드', c.cardName],
    ['카드번호', `${cardNo.slice(0, 4)}-****-****-${cardNo.slice(-4)}`, true],
    ['거래번호', no, true],
  ];
  $('r-lines').innerHTML = lines.map(([k, v, mono]) => `<div><dt>${k}</dt><span class="ld"></span><dd${mono ? ' class="m"' : ''}>${esc(v)}</dd></div>`).join('');
  $('r-total').innerHTML = `${fmt(rec.paymentBalance ?? amount)}<small>원</small>`;
  drawBar(no.replace(/\D/g, '') || '0');
  $('r-no').textContent = no;
  $('entry').hidden = true;
  $('receipt').hidden = false;
  const paper = $('paper');
  paper.classList.remove('feed');
  void paper.offsetWidth;
  paper.classList.add('feed');
  $('register').scrollTop = 0;
}
function drawBar(no) {
  let x = 0;
  let out = '';
  ('1' + no + '9').split('').map(Number).forEach((dgt, i) => {
    for (let b = 0; b < 4; b++) {
      const v = (dgt * 7 + i * 3 + b * 5) % 9;
      const w = 1 + (v % 3);
      out += `<rect x="${x}" y="0" width="${w}" height="46"/>`;
      x += w + 1 + ((v + b) % 3);
    }
  });
  const svg = $('r-bar');
  svg.setAttribute('viewBox', `0 0 ${x} 46`);
  svg.innerHTML = `<g fill="#18201A">${out}</g>`;
}
$('pay').onclick = pay;
$('next').onclick = () => { S.amount = ''; showEntry(); renderTicket(); };

// ---------- 계산대 열기·닫기 ----------
const isOpen = () => $('main').classList.contains('reg-open');
let returnFocus = null;
function openReg() {
  if (isOpen()) return;
  returnFocus = document.activeElement;
  $('main').classList.add('reg-open');
  if (mobile()) document.body.classList.add('reg-lock');
  $('register').focus({ preventScroll: true }); // 키보드·스크린리더가 열린 계산대로 따라가게
}
function closeReg() {
  if (!isOpen() || S.busy) return;
  $('main').classList.remove('reg-open');
  document.body.classList.remove('reg-lock');
  S.merchant = null;
  S.amount = '';
  showEntry();
  renderTicket();
  document.querySelectorAll('.row.sel').forEach((r) => r.classList.remove('sel'));
  if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  returnFocus = null;
}
$('reg-close').onclick = closeReg;

// ---------- 검색 · 키보드 ----------
$('q').addEventListener('input', (e) => { S.q = e.target.value; renderList(); $('list').scrollTop = 0; });
document.addEventListener('keydown', (e) => {
  const inField = document.activeElement === $('q');
  if (e.key === '/' && !inField) { e.preventDefault(); $('q').focus(); return; }
  if (e.key === 'Escape' && inField) { $('q').blur(); return; }
  if (e.key === 'Escape' && isOpen()) { closeReg(); return; }
  if (inField || e.ctrlKey || e.metaKey || e.altKey || !isOpen()) return;
  // 카드·업종 같은 다른 버튼에 포커스가 있으면 Enter 는 그 버튼을 누르게 둔다 (키패드·결제 버튼만 예외)
  const el = document.activeElement;
  if (e.key === 'Enter' && el && el !== document.body && el.matches('button,a,input,select,textarea') && !el.closest('#pad, #quick, #pay')) return;
  if (/^[0-9]$/.test(e.key)) press(e.key);
  else if (e.key === 'Backspace') { e.preventDefault(); press('del'); }
  else if (e.key === 'Enter') { e.preventDefault(); if (!$('receipt').hidden) $('next').click(); else pay(); }
});
addEventListener('resize', moveInd);

// ---------- 시작 ----------
async function loadCards() {
  try {
    cards = recRows(await finCall('cards', {}));
  } catch (err) {
    cards = [];
    showError('내 카드 목록 조회 실패: ' + (err?.message || err));
  }
  S.card = 0;
  renderCards();
  renderTicket();
}

async function init() {
  renderPad();
  renderCards();
  renderTicket();
  const cardsReady = loadCards(); // 가맹점과 동시에 — 계산대를 열기 전까지만 준비되면 된다
  try {
    const res = await (await fetch('/api/merchants')).json();
    if (!Array.isArray(res)) throw new Error(res?.message || '가맹점 로드 실패');
    merchants = res;
  } catch (err) {
    showError('가맹점 목록 로드 실패: ' + (err?.message || err));
    $('list').innerHTML = '';
    return;
  }
  cats = [...new Set(merchants.map((m) => m.subcategoryName))];
  renderCats();
  renderList();
  await cardsReady;
  loadRecent();
}

init();
