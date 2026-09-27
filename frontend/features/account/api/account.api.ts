import { api, isMocked } from "@/api/client";
import { accountListMock, setIncomeAccountMock } from "@/api/mocks/account";
import { withMockLatency } from "@/api/mocks/latency";
import { toLinkedAccounts, type AccountListDto, type LinkedAccount } from "@/features/account/model";

/** GET /accounts — 관리 중인 연결 계좌 (FR-USR-03, docs/api-contract.md ACCOUNT). 금융망을 부르지 않고 저장된 잔액 스냅샷을 준다 */
export async function getAccounts(signal?: AbortSignal): Promise<LinkedAccount[]> {
  if (isMocked("account")) return toLinkedAccounts(await withMockLatency(accountListMock(), signal));
  const { data } = await api.get<AccountListDto>("/accounts", { signal });
  return toLinkedAccounts(data);
}

/**
 * PUT /accounts/{id}/income — 수입 계좌 지정·변경 (FR-USR-03). 200, data null.
 * 사용자당 1개라 기존 수입 계좌는 서버가 해제하고, 이미 수입 계좌면 그대로 성공한다.
 */
export async function setIncomeAccount(accountId: number): Promise<void> {
  if (isMocked("account")) {
    setIncomeAccountMock(accountId);
    await withMockLatency(undefined);
    return;
  }
  await api.put(`/accounts/${accountId}/income`);
}
