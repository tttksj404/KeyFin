import { Pressable } from "react-native";

import { getSceneScale, type SceneRect } from "@/features/room/model";

// Pencil home/p0 WallBoard Asset (K5Ndp). 그림(체크리스트)은 Skia 씬이 스프라이트(WALL_ITEMS.board)로 그리고,
// 이 컴포넌트는 그 위에 얹는 탭 영역뿐이다 — 벽걸이가 1×1 칸이라 글자를 얹지 않고 기간·잔여율·봉투 상태는 예산 시트(BudgetSheet)가 보여준다
// (사용자 결정 2026-09-15). 자리는 배치(스토어)에서 온 사각형이라 방 꾸미기에서 옮기면 따라간다.

type WallBoardProps = {
  /** 캔버스 폭(pt). 씬 좌표를 이 폭으로 환산한다 */
  width: number;
  /** 보드 스프라이트가 놓인 씬 사각형 */
  rect: SceneRect;
  /** 스크린리더가 읽는 설명 "예산 보드, 9월 1일~30일 36% 남음" */
  label: string;
  onPress: () => void;
};

function WallBoard({ width, rect, label, onPress }: WallBoardProps) {
  const scale = getSceneScale(width);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint="예산 보드를 엽니다"
      onPress={onPress}
      hitSlop={8}
      className="absolute active:opacity-80"
      style={{ left: rect.x * scale, top: rect.y * scale, width: rect.width * scale, height: rect.height * scale }}
    />
  );
}

export { WallBoard };
export type { WallBoardProps };
