import { ApiError } from "@/api/error";
import { managedAccountsMock } from "@/api/mocks/link";
import type { AccountListDto } from "@/features/account/model";

/** 앱이 도는 동안만 유지되는 수입 계좌. 서버의 accounts.is_income 자리를 대신한다(사용자당 1개) */
let incomeAccountId: number | null = null;

/** 잔액 스냅샷 갱신 시각 예시 (시간대 없는 KST) */
const MOCK_BALANCE_UPDATED_AT = "2026-09-11T14:30:00";

/** GET /accounts. 연결 목(POST /links)으로 관리 대상이 된 계좌만 id 오름차순으로 준다 */
export function accountListMock(): AccountListDto {
  return {
    items: managedAccountsMock()
      .sort((a, b) => a.id - b.id)
      .map(({ id, finAccountNo, bankName, balance }) => ({
        id,
        finAccountNo,
        bankName,
        alias: null,
        isIncome: id === incomeAccountId,
        isManaged: true,
        balance,
        balanceUpdatedAt: MOCK_BALANCE_UPDATED_AT,
      })),
  };
}

/** PUT /accounts/{id}/income. 관리 중인 계좌가 아니면 거절하고, 기존 수입 계좌는 덮어써서 해제한다 */
export function setIncomeAccountMock(accountId: number): void {
  if (!managedAccountsMock().some((account) => account.id === accountId)) {
    throw new ApiError(404, "ACCOUNT_001", "계좌를 찾을 수 없습니다.");
  }
  incomeAccountId = accountId;
}

/** 계좌 연결 해제(DELETE /links/accounts/{id})와 함께 서버가 is_income 도 푼다(Account.unlink) */
export function releaseIncomeAccountMock(accountId: number): void {
  if (incomeAccountId === accountId) incomeAccountId = null;
}

/** 온보딩을 마친 사용자로 시작할 때: 첫 관리 계좌를 수입 계좌로 */
export function seedIncomeAccountMock(): void {
  incomeAccountId = managedAccountsMock().sort((a, b) => a.id - b.id)[0]?.id ?? null;
}

/** 테스트·개발 재시작용 */
export function resetAccountMocks(): void {
  incomeAccountId = null;
}
