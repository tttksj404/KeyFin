import { DEFAULT_LAYOUT } from "@/features/room/scene";
import { selectIsEditing, selectPlacements, useRoomStore } from "@/features/room/store";

describe("room store (편집 모드)", () => {
  // 기본 배치는 격자에서 파생되므로 좌표를 적어두지 않고 여기서 가져온다.
  const anchorOf = (id: string) => DEFAULT_LAYOUT.find((p) => p.itemId === id)!.anchor;

  beforeEach(() => {
    useRoomStore.setState({ layout: DEFAULT_LAYOUT, draft: null, selectedId: null });
  });

  it("편집을 시작하면 확정본의 사본을 만들고, 화면은 사본을 그린다", () => {
    useRoomStore.getState().startEdit();
    const state = useRoomStore.getState();
    expect(selectIsEditing(state)).toBe(true);
    expect(state.draft).not.toBe(state.layout);
    expect(selectPlacements(state)).toBe(state.draft);
  });

  it("가구를 옮기면 사본만 바뀌고 확정본은 그대로다", () => {
    const store = useRoomStore.getState();
    store.startEdit();
    store.moveItem("sofa_default", { x: 120, y: 300 });
    const state = useRoomStore.getState();
    expect(state.draft!.find((p) => p.itemId === "sofa_default")!.anchor).toEqual({ x: 120, y: 300 });
    expect(state.layout.find((p) => p.itemId === "sofa_default")!.anchor).toEqual(anchorOf("sofa_default"));
  });

  it("편집 중이 아니면 moveItem 은 무시한다", () => {
    useRoomStore.getState().moveItem("sofa_default", { x: 120, y: 300 });
    expect(useRoomStore.getState().layout.find((p) => p.itemId === "sofa_default")!.anchor).toEqual(anchorOf("sofa_default"));
  });

  it("취소하면 사본과 선택을 버리고 확정본으로 돌아간다", () => {
    const store = useRoomStore.getState();
    store.startEdit();
    store.select("sofa_default");
    store.moveItem("sofa_default", { x: 120, y: 300 });
    store.cancelEdit();
    const state = useRoomStore.getState();
    expect(state.draft).toBeNull();
    expect(state.selectedId).toBeNull();
    expect(selectPlacements(state).find((p) => p.itemId === "sofa_default")!.anchor).toEqual(anchorOf("sofa_default"));
  });

  it("완료하면 사본이 확정본이 된다", () => {
    const store = useRoomStore.getState();
    store.startEdit();
    store.moveItem("dining_table_original", { x: 70, y: 180 });
    store.commitEdit();
    const state = useRoomStore.getState();
    expect(state.draft).toBeNull();
    expect(state.layout.find((p) => p.itemId === "dining_table_original")!.anchor).toEqual({ x: 70, y: 180 });
  });
});
