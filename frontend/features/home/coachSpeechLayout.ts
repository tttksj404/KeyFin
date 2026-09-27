import { getCanvasSize, getSceneScale, type SceneSize } from "@/features/room/model";
import { COACH_CAT_FLOAT_HEIGHT, COACH_CAT_STROLL_RANGE, COACH_SPEECH_ANCHOR } from "@/features/room/scene";

export const COACH_SPEECH_CLOSE_SIZE = 44;
export const COACH_SPEECH_CLOSE_VISUAL_SIZE = 28;
// 원의 중심은 말풍선 윗변에 걸친다. 위·오른쪽으로 나온 터치 영역도 부모 안에 둔다.
const CLOSE_TOP_SPACE = COACH_SPEECH_CLOSE_SIZE - COACH_SPEECH_CLOSE_VISUAL_SIZE / 2;
const CLOSE_RIGHT_SPACE = (COACH_SPEECH_CLOSE_SIZE - COACH_SPEECH_CLOSE_VISUAL_SIZE) / 2;
const CONTENT_PADDING_TOP = COACH_SPEECH_CLOSE_VISUAL_SIZE / 2 + 4;
const MAX_WIDTH = 230;
/** 말풍선 바깥의 닫기 영역까지 포함한 전체 높이 상한. */
const MAX_HEIGHT = 180;
const CAT_GAP = 8;
const SCREEN_MARGIN = 8;
const PADDING_X = 24;
const PADDING_BOTTOM = 8;
const BORDER = 2;

/**
 * 카메라가 1배일 때 홈의 중앙 잘림을 고려한 말풍선 범위. 반환 좌표는 씬 캔버스 기준이다.
 * 고양이 이동값은 부모가 한 번만 적용한다. 최대 이동분을 미리 비워 폭·높이 상한은 산책 중에도 고정한다.
 */
export function coachSpeechLayout(width: number, viewport: SceneSize = getCanvasSize(width)) {
  const scale = getSceneScale(width);
  const canvas = getCanvasSize(width);
  const insetX = Math.max(0, (canvas.width - viewport.width) / 2);
  const insetY = Math.max(0, (canvas.height - viewport.height) / 2);
  const visibleRight = Math.min(canvas.width, insetX + viewport.width);
  const left = COACH_SPEECH_ANCHOR.x * scale;
  const bottom = COACH_SPEECH_ANCHOR.y * scale - CAT_GAP;
  const topLimit = insetY + SCREEN_MARGIN + COACH_CAT_FLOAT_HEIGHT * scale;
  const maxWidth = Math.max(0, Math.min(MAX_WIDTH, visibleRight - SCREEN_MARGIN - left - COACH_CAT_STROLL_RANGE.right * scale));
  const maxHeight = Math.max(0, Math.min(MAX_HEIGHT, bottom - topLimit));
  const bubbleMaxWidth = Math.max(0, maxWidth - CLOSE_RIGHT_SPACE);
  const bubbleMaxHeight = Math.max(0, maxHeight - CLOSE_TOP_SPACE);

  return {
    left,
    top: bottom - maxHeight,
    maxWidth,
    maxHeight,
    closeTopSpace: CLOSE_TOP_SPACE,
    closeRightSpace: CLOSE_RIGHT_SPACE,
    contentPaddingTop: CONTENT_PADDING_TOP,
    bubbleMaxWidth,
    bubbleMaxHeight,
    contentMaxWidth: Math.max(0, bubbleMaxWidth - PADDING_X - BORDER),
    contentMaxHeight: Math.max(0, bubbleMaxHeight - CONTENT_PADDING_TOP - PADDING_BOTTOM - BORDER),
  };
}
