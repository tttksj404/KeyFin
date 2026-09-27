import { boldSegments } from "@/features/coaching/boldSegments";

describe("boldSegments", () => {
  it("제안 문장의 **…** 만 굵게 조각으로 나눈다", () => {
    expect(boldSegments("여유가 있다냥. **옮겨 두면 좋다냥.**\n\n알려 달라냥.")).toEqual([
      { text: "여유가 있다냥. ", bold: false },
      { text: "옮겨 두면 좋다냥.", bold: true },
      { text: "\n\n알려 달라냥.", bold: false },
    ]);
  });

  it("표시가 없으면 한 조각, 짝이 없는 ** 는 글자 그대로 둔다", () => {
    expect(boldSegments("잔액이다냥.")).toEqual([{ text: "잔액이다냥.", bold: false }]);
    expect(boldSegments("2**3 은 8")).toEqual([{ text: "2**3 은 8", bold: false }]);
    expect(boldSegments("")).toEqual([]);
  });
});
