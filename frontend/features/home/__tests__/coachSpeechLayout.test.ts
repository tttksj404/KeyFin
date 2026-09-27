import { coachSpeechLayout } from "@/features/home/coachSpeechLayout";
import { coverSceneWidth, getCanvasSize, getSceneScale } from "@/features/room/model";
import { COACH_CAT_RECT, COACH_SPEECH_ANCHOR } from "@/features/room/scene";
import { coachCatOffsetAt } from "@/features/room/useCoachCatMotion";

describe("coachSpeechLayout", () => {
  it("기울어진 머리의 60% 지점을 기준으로 모서리를 8pt 위에 붙인다", () => {
    expect(COACH_SPEECH_ANCHOR).toEqual({ x: COACH_CAT_RECT.x + COACH_CAT_RECT.width * 0.6, y: COACH_CAT_RECT.y });
    const layout = coachSpeechLayout(327);
    expect(layout.left).toBe(84);
    expect(layout.top + layout.maxHeight).toBe(487);
    expect(layout.maxHeight).toBe(180);
    expect(layout.bubbleMaxHeight).toBe(150); // 겹쳐진 X의 위쪽 터치 영역 30pt만 별도로 확보한다.
    expect(layout.contentMaxHeight).toBe(122);
    expect(layout.contentMaxWidth).toBe(layout.bubbleMaxWidth - 24 - 2); // 본문 옆에 X 열을 남기지 않는다.
    // 원의 위아래 절반이 말풍선 윗변에 걸치고, 터치 영역 아래에 본문 여백을 둔다.
    expect(44 - 28 / 2).toBe(layout.closeTopSpace);
    expect(layout.closeTopSpace + layout.contentPaddingTop).toBeGreaterThan(44);
    expect(layout.closeRightSpace).toBe(8);
  });

  it.each([
    { width: 280, height: 680 },
    { width: 320, height: 568 },
    { width: 360, height: 640 },
    { width: 360, height: 800 },
    { width: 412, height: 915 },
    { width: 430, height: 932 },
  ])("$width×$height에서 산책·떠오르기 내내 머리 정렬과 화면 여백을 유지한다", (viewport) => {
    const width = coverSceneWidth(viewport.width, viewport.height);
    const scale = getSceneScale(width);
    const canvas = getCanvasSize(width);
    const insetX = Math.max(0, (width - viewport.width) / 2);
    const insetY = Math.max(0, (canvas.height - viewport.height) / 2);
    const layout = coachSpeechLayout(width, viewport);
    expect(layout.maxWidth).toBeLessThanOrEqual(230);
    expect(layout.maxHeight).toBeLessThanOrEqual(180);
    expect(layout.bubbleMaxWidth + layout.closeRightSpace).toBe(layout.maxWidth);
    expect(layout.bubbleMaxHeight + layout.closeTopSpace).toBe(layout.maxHeight);
    expect(layout.contentMaxHeight + layout.contentPaddingTop + 8 + 2).toBe(layout.bubbleMaxHeight);
    expect(layout.contentMaxWidth).toBeGreaterThan(100);

    // 4구간의 산책 전체를 검사한다. 모션을 바꿔도 실제 이동값이 예약 범위를 넘으면 실패한다.
    for (let time = 0; time <= 23_200; time += 100) {
      const motion = coachCatOffsetAt(time);
      const x = layout.left + motion.x * scale - insetX;
      const y = layout.top + motion.y * scale - insetY;
      const headX = (COACH_CAT_RECT.x + COACH_CAT_RECT.width * 0.6 + motion.x) * scale - insetX;
      const headY = (COACH_CAT_RECT.y + motion.y) * scale - insetY;
      expect(x).toBeCloseTo(headX);
      expect(headY - (y + layout.maxHeight)).toBeCloseTo(8);
      expect(x).toBeGreaterThanOrEqual(8);
      expect(x + layout.maxWidth).toBeLessThanOrEqual(viewport.width - 8 + 0.001);
      expect(y).toBeGreaterThanOrEqual(8);
    }
  });

  it("고양이 위 공간이 작으면 최대 떠오름을 포함해 높이를 줄인다", () => {
    const layout = coachSpeechLayout(109);
    expect(layout.maxHeight).toBe(148);
    expect(layout.top - 3 / 3).toBe(8);
    expect(layout.bubbleMaxHeight).toBe(118);
    expect(layout.contentMaxHeight).toBe(90);
  });

  it("캔버스 위아래가 잘리면 보이는 화면의 위쪽 경계로 높이를 제한한다", () => {
    const viewport = { width: 163.5, height: 80 };
    const layout = coachSpeechLayout(163.5, viewport);
    expect(layout.maxHeight).toBe(123.5);
    expect(layout.bubbleMaxHeight).toBe(93.5);
    expect(layout.top - (293 - 80) / 2 - 3 * 0.5).toBe(8);
  });
});
