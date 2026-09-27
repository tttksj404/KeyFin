import type { UseQueryResult } from "@tanstack/react-query";

import { budgetPeriodLabel, type Budget } from "@/features/budget/model";
import { BudgetSheet } from "@/features/home/components/BudgetSheet";
import { WallBoard } from "@/features/room/components/WallBoard";
import { getWallItemRect } from "@/features/room/scene";
import { selectPlacements, useRoomStore } from "@/features/room/store";

type HomeWallBoardProps = {
  /** 캔버스 폭(pt) */
  width: number;
  /** 조회 상태째 받는다 — 못 받았어도 보드는 눌리고, 시트가 불러오는 중·재시도를 보여준다 */
  budget: UseQueryResult<Budget>;
  onOpen: () => void;
};

/** 스크린리더용 보드 설명. 에셋 위에는 글자가 없어 여기에만 잔여율이 있다 */
function boardLabel(budget: UseQueryResult<Budget>): string {
  if (budget.isPending) return "예산 보드, 불러오는 중";
  if (budget.isError) return "예산 보드, 불러오지 못했어요";
  const rate = budget.data.total?.remainingRate ?? null;
  return `예산 보드, ${budgetPeriodLabel(budget.data)} ${rate === null ? "예산 미설정" : `${rate}% 남음`}`;
}

/**
 * 방 벽의 리스트(보드) 에셋 (FR-BGT-04). 방 안의 오브젝트라 카메라를 따라 함께 확대·이동하고, 자리는 방 배치(스토어)를 따른다.
 * 홈에 예산 카드가 없어(2026-09-15) 이 보드가 예산으로 들어가는 유일한 입구다 — 조회가 실패해도 눌려야 시트에서 재시도할 수 있다.
 */
function HomeWallBoard({ width, budget, onOpen }: HomeWallBoardProps) {
  // 배치 배열은 참조가 안정적이라 그대로 고르고, 사각형은 렌더에서 계산한다(셀렉터가 새 객체를 돌려주면 재렌더가 돈다).
  const placements = useRoomStore(selectPlacements);
  const rect = getWallItemRect(placements, "board");
  if (!rect) return null;

  return <WallBoard width={width} rect={rect} label={boardLabel(budget)} onPress={onOpen} />;
}

type HomeBoardPanelProps = {
  visible: boolean;
  budget: UseQueryResult<Budget>;
  onClose: () => void;
};

/** 보드를 탭했을 때 아래서 올라오는 예산 시트 */
function HomeBoardPanel({ visible, budget, onClose }: HomeBoardPanelProps) {
  return <BudgetSheet visible={visible} budget={budget} onClose={onClose} />;
}

export { HomeBoardPanel, HomeWallBoard };
export type { HomeBoardPanelProps, HomeWallBoardProps };
