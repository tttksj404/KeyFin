import { MOVING_IN_COPY, pickReturningCopy } from "@/features/room/components/RoomWaiting";

describe("방 대기 문구", () => {
  it("이미 입주한 계정의 문구는 입주 문구와 겹치지 않고, 무작위 값의 양 끝에서도 하나를 고른다", () => {
    const picks = [0, 0.25, 0.5, 0.75, 0.999999, 1].map((value) => pickReturningCopy(() => value));

    for (const copy of picks) {
      expect(copy).toBeDefined();
      expect(copy.title).not.toBe(MOVING_IN_COPY.title);
      expect(copy.title).toMatch(/^캐릭터가 .+ 있어요$/);
      expect(copy.description).toContain("잠시만 기다려 주세요");
    }
    expect(new Set(picks.map((copy) => copy.title)).size).toBeGreaterThan(1);
  });
});
