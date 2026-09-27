export function getUser() {
  try { return JSON.parse(localStorage.getItem('keyfinPayUser')); } catch { return null; }
}

export function requireUser() {
  const user = getUser();
  if (!user?.userKey) { location.href = '/'; throw new Error('not logged in'); }
  return user;
}

export function logout() {
  localStorage.removeItem('keyfinPayUser');
  location.href = '/';
}

export async function finCall(action, fields) {
  const { userKey } = requireUser();
  const res = await fetch(`/api/fin/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userKey, fields }),
  });
  const result = await res.json();
  const payload = result.ok ? result.data : result.error || {};
  const code = payload?.responseCode ?? payload?.Header?.responseCode;
  if (!result.ok || (code && code !== 'H0000')) {
    throw new Error(payload?.responseMessage || payload?.Header?.responseMessage || result.message || '요청에 실패했습니다.');
  }
  return payload;
}

export function recRows(payload) {
  const rec = payload?.REC;
  if (Array.isArray(rec)) return rec;
  if (rec && typeof rec === 'object') {
    const list = Object.values(rec).find(Array.isArray);
    if (list) return list;
  }
  return [];
}

export const won = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('ko-KR') + '원' : String(v);
};

export function initTopbar(active) {
  const user = requireUser();
  const link = document.querySelector(`.topbar nav a[href="${active}"]`);
  link?.classList.add('on');
  link?.setAttribute('aria-current', 'page');
  const who = document.getElementById('who-name');
  const name = document.createElement('b');
  name.textContent = user.userName;
  who.replaceChildren(name, ' 님');
  who.title = user.userId;
  document.getElementById('logout-btn').addEventListener('click', logout);
}

// ---------- 화면 공용 도구 ----------

export const $ = (id) => document.getElementById(id);
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
export const fmt = (v) => num(v).toLocaleString('ko-KR');
const pad2 = (n) => String(n).padStart(2, '0');
// toISOString 은 UTC 라 KST 자정~09시에 날짜가 밀린다 — 로컬 기준으로 만든다
export const ymd = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;

// 금융망 날짜는 '20261013' 과 '2026-10-13' 두 형식으로 온다
export function parseDate(s) {
  const d = String(s ?? '').replace(/\D/g, '');
  if (d.length < 8) return null;
  const date = new Date(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8));
  return Number.isNaN(date.getTime()) ? null : date;
}

let toastTimer;
export function toast(message) {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.className = 'toast hidden';
    el.setAttribute('role', 'status');
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2600);
}

// 되돌릴 수 없는 동작 전에 묻는다. body 는 신뢰할 수 있는 HTML 만 넘긴다(값은 esc 로 감쌀 것).
export function confirmDialog({ title, body, okLabel }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'dlg-t');
    overlay.innerHTML = `<div class="dialog"><h2 id="dlg-t"></h2><p>${body}</p>
      <div class="acts"><button type="button" class="btn btn-secondary btn-md" data-v="0">돌아가기</button>
      <button type="button" class="btn btn-danger btn-md" data-v="1"></button></div></div>`;
    overlay.querySelector('h2').textContent = title;
    overlay.querySelector('[data-v="1"]').textContent = okLabel;
    const back = document.activeElement;
    const done = (v) => {
      document.removeEventListener('keydown', onKey, true);
      overlay.remove();
      back?.focus?.();
      resolve(v);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); done(false); return; }
      if (e.key === 'Tab') { // 두 버튼 사이에서만 순환한다
        const btns = [...overlay.querySelectorAll('button')];
        const i = btns.indexOf(document.activeElement);
        e.preventDefault();
        btns[(i + (e.shiftKey ? -1 : 1) + btns.length) % btns.length].focus();
      }
    };
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) return done(false);
      const b = e.target.closest('[data-v]');
      if (b) done(b.dataset.v === '1');
    });
    document.addEventListener('keydown', onKey, true);
    document.body.appendChild(overlay);
    overlay.querySelector('[data-v="0"]').focus();
  });
}
