import { placeBubble } from "@/features/room/model";

const BOUNDS = { width: 300, height: 500 };
const BUBBLE = { width: 120, height: 40 };

describe("고른 가구 옆 말풍선 자리", () => {
  it("기본은 가구 바로 아래 가운데다", () => {
    expect(placeBubble({ x: 100, y: 100, width: 80, height: 60 }, BUBBLE, BOUNDS)).toEqual({ x: 80, y: 168 });
  });

  it("아래로 넘치면 가구 위로 올린다", () => {
    expect(placeBubble({ x: 100, y: 430, width: 80, height: 60 }, BUBBLE, BOUNDS)).toEqual({ x: 80, y: 382 });
  });

  it("좌우 끝의 가구는 영역 안으로 당긴다", () => {
    expect(placeBubble({ x: 0, y: 100, width: 40, height: 40 }, BUBBLE, BOUNDS).x).toBe(8);
    expect(placeBubble({ x: 270, y: 100, width: 30, height: 40 }, BUBBLE, BOUNDS).x).toBe(300 - 120 - 8);
  });

  it("위아래 모두 자리가 없으면 영역 안쪽 아래에 붙인다", () => {
    expect(placeBubble({ x: 50, y: 10, width: 200, height: 480 }, BUBBLE, BOUNDS)).toEqual({ x: 90, y: 500 - 40 - 8 });
  });

  it("말풍선이 영역보다 넓어도 왼쪽 여백은 지킨다", () => {
    expect(placeBubble({ x: 100, y: 100, width: 80, height: 60 }, { width: 400, height: 40 }, BOUNDS).x).toBe(8);
  });
});
