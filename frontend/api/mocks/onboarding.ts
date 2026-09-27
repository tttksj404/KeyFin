import { isMocked } from "@/api/client";
import { seedIncomeAccountMock } from "@/api/mocks/account";
import { seedConfirmedBudgetMock } from "@/api/mocks/budget";
import { seedConnectedMock } from "@/api/mocks/link";

/**
 * 기기에 "온보딩 완료" 가 기록된 사용자로 시작할 때 목을 그 상태로 맞춘다.
 * 목 상태는 메모리에만 있어 코드 수정·리로드마다 초기화되는데, 그때마다 금융망 연결·예산 확정을 다시 하지 않게 한다 (2026-09-16).
 * 실서버 도메인은 건드리지 않는다 — 서버가 상태를 갖는다.
 */
export function seedOnboardedMocks(): void {
  if (isMocked("link")) seedConnectedMock();
  if (isMocked("account")) seedIncomeAccountMock();
  if (isMocked("budget")) seedConfirmedBudgetMock();
}
