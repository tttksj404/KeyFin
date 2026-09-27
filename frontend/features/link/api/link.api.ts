import { api, isMocked } from "@/api/client";
import { releaseIncomeAccountMock } from "@/api/mocks/account";
import { withMockLatency } from "@/api/mocks/latency";
import {
  connectFinanceMock,
  createLinksMock,
  financeStatusMock,
  linkCandidatesMock,
  unlinkAccountMock,
  unlinkCardMock,
} from "@/api/mocks/link";
import {
  toLinkCandidates,
  type FinanceLinkRequest,
  type FinanceLinkResponseDto,
  type FinanceStatusDto,
  type LinkCandidates,
  type LinkCandidatesDto,
  type LinkRequest,
  type LinkResponseDto,
} from "@/features/link/model";

/** GET /links/status — 현재 사용자의 금융망 연결 여부 (docs/api-contract.md LINK). 미연결도 200 + false 다. */
export async function getFinanceStatus(signal?: AbortSignal): Promise<boolean> {
  if (isMocked("link")) {
    const { connected } = await withMockLatency(financeStatusMock(), signal);
    return connected;
  }
  const { data } = await api.get<FinanceStatusDto>("/links/status", { signal });
  return data.connected;
}

/** POST /links/connect — 금융망 회원 연결 (docs/api-contract.md LINK). 같은 금융망 회원으로 다시 보내면 성공이다(멱등) */
export async function connectFinanceAccount(request: FinanceLinkRequest): Promise<boolean> {
  if (isMocked("link")) {
    const { connected } = await withMockLatency(connectFinanceMock(request));
    return connected;
  }
  const { data } = await api.post<FinanceLinkResponseDto>("/links/connect", request);
  return data.connected;
}

/**
 * GET /links/candidates — 금융망 기준 연결 가능한 계좌·카드 (docs/api-contract.md LINK, FR-USR-02).
 * 금융망 회원 연결(PAGE-03B)이 끝나야 후보가 돌아온다.
 */
export async function getLinkCandidates(signal?: AbortSignal): Promise<LinkCandidates> {
  if (isMocked("link")) return toLinkCandidates(await withMockLatency(linkCandidatesMock(), signal));
  const { data } = await api.get<LinkCandidatesDto>("/links/candidates", { signal });
  return toLinkCandidates(data);
}

/** POST /links — 후보의 KeyFin id 로 선택 항목을 연결한다. 금융망은 부르지 않고, 이미 관리 중인 항목은 건너뛰어 재시도해도 안전하다(멱등) */
export async function createLinks(request: LinkRequest): Promise<LinkResponseDto> {
  if (isMocked("link")) return withMockLatency(createLinksMock(request));
  const { data } = await api.post<LinkResponseDto>("/links", request);
  return data;
}

/**
 * DELETE /links/accounts/{accountId} — 계좌를 관리 대상에서 뺀다 (FR-USR-05, docs/api-contract.md LINK). 200, data null.
 * 행은 남아 거래 이력이 보존되고 수입 계좌 지정도 함께 풀린다. 이미 해제된 계좌도 성공이라 재시도해도 안전하다(멱등).
 */
export async function unlinkAccount(accountId: number): Promise<void> {
  if (isMocked("link")) {
    unlinkAccountMock(accountId);
    releaseIncomeAccountMock(accountId);
    await withMockLatency(undefined);
    return;
  }
  await api.delete(`/links/accounts/${accountId}`);
}

/** DELETE /links/cards/{cardId} — 카드를 관리 대상에서 뺀다 (FR-USR-05). 200, data null, 멱등 */
export async function unlinkCard(cardId: number): Promise<void> {
  if (isMocked("link")) {
    unlinkCardMock(cardId);
    await withMockLatency(undefined);
    return;
  }
  await api.delete(`/links/cards/${cardId}`);
}
