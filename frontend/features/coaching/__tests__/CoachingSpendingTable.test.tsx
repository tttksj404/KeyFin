import { render, screen } from "@testing-library/react-native";

import { CoachingSpendingTable } from "@/features/coaching/components/CoachingSpendingTable";
import type { ChatSpendingRow } from "@/features/coaching/model";

const rows: ChatSpendingRow[] = [
  { envelope: "외식", totalKrw: "45000", count: 3 },
  { envelope: "교통", totalKrw: "12000", count: 4 },
];

describe("CoachingSpendingTable", () => {
  it("봉투별 금액·건수와 서버 합계를 표시한다", async () => {
    await render(<CoachingSpendingTable rows={rows} totalKrw="57000" />);

    expect(screen.getByText("봉투")).toBeTruthy();
    expect(screen.getByText("소비 금액")).toBeTruthy();
    expect(screen.getByText("건수")).toBeTruthy();
    expect(screen.getByText("외식")).toBeTruthy();
    expect(screen.getByText("45,000원")).toBeTruthy();
    expect(screen.getByText("3건")).toBeTruthy();
    expect(screen.getByLabelText("교통, 소비 금액 12,000원, 4건")).toBeTruthy();
    expect(screen.getByText("합계")).toBeTruthy();
    expect(screen.getByText("57,000원")).toBeTruthy();
  });

  it("일반 답변·GET 이력처럼 집계가 없으면 표와 합계를 표시하지 않는다", async () => {
    await render(<CoachingSpendingTable rows={[]} totalKrw={null} />);
    expect(screen.toJSON()).toBeNull();
  });

  it("지출이 없으면 빈 표 대신 합계 0원을 표시한다", async () => {
    await render(<CoachingSpendingTable rows={[]} totalKrw="0" />);
    expect(screen.queryByText("봉투")).toBeNull();
    expect(screen.getByText("합계")).toBeTruthy();
    expect(screen.getByText("0원")).toBeTruthy();
  });

  it("0원·0건인 행도 표시한다", async () => {
    await render(<CoachingSpendingTable rows={[{ envelope: "외식", totalKrw: "0", count: 0 }]} totalKrw="0" />);
    expect(screen.getByLabelText("외식, 소비 금액 0원, 0건")).toBeTruthy();
    expect(screen.getAllByText("0원")).toHaveLength(2);
  });

  it("서버 합계가 null이면 행으로 합계를 만들어 내지 않는다", async () => {
    await render(<CoachingSpendingTable rows={rows} totalKrw={null} />);
    expect(screen.getByText("45,000원")).toBeTruthy();
    expect(screen.queryByText("합계")).toBeNull();
    expect(screen.queryByText("57,000원")).toBeNull();
  });
});
