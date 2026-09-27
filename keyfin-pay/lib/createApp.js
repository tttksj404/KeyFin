import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildFinBody } from './finHeader.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, '..', 'public');

// 금융망 중복 등록 사고(같은 가맹점 2건)의 잔재를 이름+카테고리 기준으로 걸러낸다 — 먼저 등록된 ID를 사용
const MERCHANT_SQL =
  'SELECT MIN(m.fin_merchant_id) AS fin_merchant_id, m.name, s.name AS subcategory_name '
  + 'FROM merchants m JOIN subcategories s ON m.subcategory_id = s.id '
  + 'GROUP BY m.name, s.name ORDER BY s.name, m.name';
// 원장이 아는 금융망 가맹점 ID 전부 — 중복 등록으로 걸러진 ID도 원장에는 있으니 미분류가 아니다
const KNOWN_ID_SQL = 'SELECT fin_merchant_id FROM merchants';

// 금융망에는 있지만 원장 merchants 에 없는 가맹점은 '미분류' 업종으로 내려 준다
export const UNCATEGORIZED = '미분류';
const FIN_MERCHANT_TTL_MS = 60_000; // 콘솔에서 새로 등록한 가맹점이 1분 안에 목록에 뜨도록

export function createApp({ finBaseUrl, finApiKey, db, fetchImpl = fetch }) {
  const FIN = String(finBaseUrl || '').replace(/\/$/, '');
  if (!FIN) throw new Error('finBaseUrl(FINANCE_API_BASE_URL)이 필요합니다.');
  if (!finApiKey) throw new Error('finApiKey(FINANCE_API_KEY)가 필요합니다.');
  // 이 앱이 중계를 허용하는 금융망 API 화이트리스트
  const FIN_ACTIONS = {
    cards: `${FIN}/edu/creditCard/inquireSignUpCreditCardList`,
    pay: `${FIN}/edu/creditCard/createCreditCardTransaction`,
    transactions: `${FIN}/edu/creditCard/inquireCreditCardTransactionList`,
    cancel: `${FIN}/edu/creditCard/deleteTransaction`,
    subServices: `${FIN}/edu/creditCard/inquireSubscriptionService`,
    subList: `${FIN}/edu/creditCard/inquireSubscriptionList`,
    subCreate: `${FIN}/edu/creditCard/subscriptionPayment`,
    subCancel: `${FIN}/edu/creditCard/cancelSubscription`,
    subToggle: `${FIN}/edu/creditCard/pauseSubscription`,
    subHistory: `${FIN}/edu/creditCard/inquireSubscriptionHistory`,
  };
  const MEMBER_SEARCH = `${FIN}/member/search`;
  const MERCHANT_LIST = `${FIN}/edu/creditCard/inquireMerchantList`;

  const app = express();
  app.use(express.json());
  app.use(express.static(PUBLIC_DIR));

  async function callFin(url, fields, userKey) {
    const res = await fetchImpl(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildFinBody({ url, fields, apiKey: finApiKey, userKey })),
    });
    return { ok: true, data: await res.json() };
  }

  const fail = (res, status, message) => res.status(status).json({ ok: false, message });

  app.get('/healthz', (req, res) => res.json({ status: 'UP' }));

  app.post('/api/login', async (req, res) => {
    try {
      const userId = String(req.body?.userId || '').trim();
      if (!userId) return fail(res, 400, '이메일을 입력하세요.');
      const result = await callFin(MEMBER_SEARCH, { userId });
      const data = result.ok ? result.data : null;
      if (data?.userKey) {
        return res.json({ ok: true, userId, userKey: data.userKey, userName: data.userName || userId.split('@')[0] });
      }
      const message = data?.responseMessage || result.error?.responseMessage || '로그인에 실패했습니다.';
      res.json({ ok: false, message });
    } catch (err) {
      fail(res, 500, String(err?.message || err));
    }
  });

  let ledgerCache = null; // ponytail: 프로세스 캐시 — 원장 가맹점 추가가 잦아지면 TTL 부여
  async function loadLedger() {
    if (!ledgerCache) {
      const [[rows], [known]] = await Promise.all([db.query(MERCHANT_SQL), db.query(KNOWN_ID_SQL)]);
      ledgerCache = {
        merchants: rows.map((r) => ({
          finMerchantId: r.fin_merchant_id,
          name: r.name,
          subcategoryName: r.subcategory_name,
        })),
        ids: new Set(known.map((r) => String(r.fin_merchant_id))),
        names: new Set(rows.map((r) => r.name)),
      };
    }
    return ledgerCache;
  }

  let finMerchantCache = null; // { at, rows }
  async function loadFinMerchants() {
    if (finMerchantCache && Date.now() - finMerchantCache.at < FIN_MERCHANT_TTL_MS) return finMerchantCache.rows;
    const { data } = await callFin(MERCHANT_LIST, {});
    const code = data?.Header?.responseCode;
    if (code !== 'H0000' || !Array.isArray(data?.REC)) {
      throw new Error(data?.Header?.responseMessage || data?.responseMessage || `가맹점 조회 응답 이상(${code ?? '코드 없음'})`);
    }
    finMerchantCache = { at: Date.now(), rows: data.REC };
    return data.REC;
  }

  function uncategorizedOf(finRows, ledger) {
    const byName = new Map();
    for (const r of finRows) {
      const id = Number(r.merchantId);
      const name = String(r.merchantName ?? '').trim();
      // 이름이 원장 가맹점과 같으면 중복 등록 잔재라 목록에서 같은 가게가 두 번 보이지 않게 뺀다
      if (!Number.isFinite(id) || !name || ledger.ids.has(String(id)) || ledger.names.has(name)) continue;
      const prev = byName.get(name);
      if (!prev || id < prev.finMerchantId) byName.set(name, { finMerchantId: id, name, subcategoryName: UNCATEGORIZED });
    }
    return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  }

  app.get('/api/merchants', async (req, res) => {
    let ledger;
    try {
      ledger = await loadLedger();
    } catch (err) {
      return fail(res, 500, 'DB 조회 실패: ' + String(err?.message || err));
    }
    let extra = [];
    try {
      extra = uncategorizedOf(await loadFinMerchants(), ledger);
    } catch (err) {
      // 금융망이 실패해도 원장 가맹점으로는 결제할 수 있게 둔다
      console.warn('금융망 가맹점 조회 실패:', err?.message || err);
    }
    res.json([...ledger.merchants, ...extra]);
  });

  app.post('/api/fin/:action', async (req, res) => {
    const url = FIN_ACTIONS[req.params.action];
    if (!url) return fail(res, 404, '허용되지 않은 요청입니다.');
    try {
      const { userKey, fields } = req.body || {};
      res.json(await callFin(url, fields || {}, userKey));
    } catch (err) {
      fail(res, 500, String(err?.message || err));
    }
  });

  return app;
}
