import { confirmBudgetMock, createProposalMock, currentBudgetMock, overEnvelopeIdsMock, resetBudgetMocks } from "@/api/mocks/budget";
import { classifyTransactionMock, resetTransactionMocks, transactionListMock } from "@/api/mocks/transaction";
import { FURNITURE, type FurnitureId } from "@/features/room/catalog";
import { penaltyGeometry, PENALTY_SPRITES } from "@/features/room/penalties";
import type { Placement } from "@/features/room/scene";

const dining: Placement = { itemId: "dining_table_original", anchor: { x: 160, y: 330 }, direction: "FRONT_RIGHT" };
const coffee: Placement = { itemId: "coffee_table_original", anchor: { x: 200, y: 380 }, direction: "FRONT_LEFT" };

describe("카테고리 페널티 배치", () => {
  it.each([
    [[1], [true, false]], [[4], [false, true]], [[1, 4], [true, true]], [[], [false, false]], [[2, 3, 5, 6, 7], [false, false]],
  ])("초과 봉투 %j는 해당 탁상 효과만 표시한다", (ids, visible) => {
    expect([dining, coffee].map((p) => penaltyGeometry(p, ids as number[]) !== null)).toEqual(visible);
    expect(penaltyGeometry({ itemId: "sofa_default", anchor: dining.anchor }, ids as number[])).toBeNull();
  });

  it("두 종류의 두 방향 실물 렌더만 앱에 등록한다", () => {
    expect(PENALTY_SPRITES).toHaveLength(4);
    expect(new Set(PENALTY_SPRITES).size).toBe(4);
  });

  it.each(["dining_table", "coffee_table"] as const)("%s 네 색상·두 방향을 잘린 이미지 기준점에 맞춘다", (kind) => {
    const baseline = kind === "dining_table" ? dining : coffee;
    const expected = kind === "dining_table"
      ? { x: 93.974312, y: 251.58843, width: 132.051376, height: 116.879316 }
      : { x: 146.681356, y: 328.874312, width: 106.637288, height: 81.301099 };
    for (const color of ["original", "black", "pink", "sunset"]) {
      const itemId = `${kind}_${color}` as FurnitureId;
      expect(FURNITURE[itemId]).toBeDefined();
      const right = penaltyGeometry({ ...baseline, itemId, direction: "FRONT_RIGHT" }, [1, 4])!;
      const left = penaltyGeometry({ ...baseline, itemId, direction: "FRONT_LEFT" }, [1, 4])!;
      expect(right.sprite).not.toBe(left.sprite);
      for (const geometry of [right, left]) {
        expect(geometry.rect.x).toBeCloseTo(expected.x, 5);
        expect(geometry.rect.y).toBeCloseTo(expected.y, 5);
        expect(geometry.rect.width).toBe(expected.width);
        expect(geometry.rect.height).toBe(expected.height);
      }
    }
  });

  it("가구 위치를 따라가며 가구가 사라지거나 초과가 해소되면 효과를 남기지 않는다", () => {
    const original = penaltyGeometry(dining, [1])!;
    const moved = penaltyGeometry({ ...dining, anchor: { x: dining.anchor.x + 24, y: dining.anchor.y - 12 } }, [1])!;
    expect(moved.rect.x - original.rect.x).toBeCloseTo(24);
    expect(moved.rect.y - original.rect.y).toBeCloseTo(-12);
    expect(penaltyGeometry(dining, [])).toBeNull();
    expect(penaltyGeometry({ ...dining, surface: "WALL_LEFT" }, [1])).toBeNull();
    expect(([coffee] as Placement[]).map((p) => penaltyGeometry(p, [1])).filter(Boolean)).toEqual([]);
  });
});

describe("예산 목과 방 페널티 판정", () => {
  const today = "2026-09-22";
  beforeEach(() => { resetBudgetMocks(); resetTransactionMocks(); });
  afterEach(() => { resetBudgetMocks(); resetTransactionMocks(); });
  const confirm = (food: number, leisure: number) => {
    createProposalMock("202609");
    confirmBudgetMock(1, { envelopes: [1, 2, 3, 4, 5, 6, 7].map((envelopeId) => ({
      envelopeId, amount: envelopeId === 1 ? food : envelopeId === 4 ? leisure : 100000,
    })) }, today);
  };

  it.each([[67000, 55000, [1]], [68000, 54000, [4]], [67000, 54000, [1, 4]], [68000, 55000, []], [0, 0, [1, 4]]])(
    "확정액 %i/%i에서 지출 > 예산인 봉투만 반환한다", (food, leisure, expected) => {
      confirm(food as number, leisure as number);
      expect(overEnvelopeIdsMock(today)).toEqual(expected);
    });

  it("방 조회는 예산을 만들지 않고 미확정·새 주기는 빈 목록이다", () => {
    expect(overEnvelopeIdsMock(today)).toEqual([]);
    expect(() => createProposalMock("202609")).not.toThrow();
    expect(overEnvelopeIdsMock(today)).toEqual([]);
    confirmBudgetMock(1, { envelopes: [{ envelopeId: 1, amount: 0 }] }, today);
    expect(overEnvelopeIdsMock(today)).toContain(1);
    expect(overEnvelopeIdsMock("2026-10-01")).toEqual([]);
    expect(currentBudgetMock("2026-10-01").status).toBe("PROPOSED");
  });

  it("재분류·제외·더치페이 수정분이 예산과 방 조회에 함께 반영된다", () => {
    confirm(67000, 60000);
    const tx = transactionListMock({ month: "202609", size: 100 }, today).items.find((t) => t.envelopeId === 1 && t.status === "NORMAL" && t.excludeTag === "NONE")!;
    expect(overEnvelopeIdsMock(today)).toEqual([1]);
    classifyTransactionMock(tx.id, { subcategoryId: 401 });
    expect(overEnvelopeIdsMock(today)).toEqual([4]);
    classifyTransactionMock(tx.id, { excludeTag: "SELF_TRANSFER" });
    expect(overEnvelopeIdsMock(today)).toEqual([]);
    classifyTransactionMock(tx.id, { excludeTag: "DUTCH", adjustedAmount: 1 });
    expect(overEnvelopeIdsMock(today)).toEqual([]);
    expect(transactionListMock({ month: "202609", size: 100 }, today).items.find((t) => t.id === tx.id))
      .toMatchObject({ envelopeId: null, subcategoryId: null, adjustedAmount: 1 });
    classifyTransactionMock(tx.id, { subcategoryId: 101 });
    expect(overEnvelopeIdsMock(today)).toEqual([1]);
  });
});
