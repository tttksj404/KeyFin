import { fireEvent, render, screen } from "@testing-library/react-native";

import { TabBar, type TabBarProps } from "@/components/ui/tab-bar";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const TITLES: Record<string, string> = { index: "홈", assets: "자산", budget: "예산", my: "마이" };

function buildProps(activeIndex: number) {
  const routes = Object.keys(TITLES).map((name) => ({ key: `${name}-key`, name }));
  const emit = jest.fn(() => ({ defaultPrevented: false }));
  const navigate = jest.fn();
  const props = {
    state: { index: activeIndex, routes },
    descriptors: Object.fromEntries(routes.map((r) => [r.key, { options: { title: TITLES[r.name] } }])),
    navigation: { emit, navigate },
    insets: { top: 0, bottom: 0, left: 0, right: 0 },
  } as unknown as TabBarProps;
  return { props, emit, navigate };
}

describe("TabBar", () => {
  it("탭 4개의 라벨을 모두 보여주고 활성 탭만 selected 상태를 갖는다", async () => {
    await render(<TabBar {...buildProps(0).props} />);
    for (const title of Object.values(TITLES)) expect(screen.getByText(title)).toBeTruthy();
    expect(screen.getByRole("tab", { name: "홈" }).props.accessibilityState).toEqual({ selected: true });
    expect(screen.getByRole("tab", { name: "자산" }).props.accessibilityState).toEqual({ selected: false });
  });

  it("비활성 탭을 누르면 tabPress 이벤트 후 이동하고, 활성 탭은 이동하지 않는다", async () => {
    const { props, emit, navigate } = buildProps(0);
    await render(<TabBar {...props} />);
    await fireEvent.press(screen.getByRole("tab", { name: "마이" }));
    expect(emit).toHaveBeenCalledWith({ type: "tabPress", target: "my-key", canPreventDefault: true });
    expect(navigate).toHaveBeenCalledWith("my");

    await fireEvent.press(screen.getByRole("tab", { name: "홈" }));
    expect(navigate).toHaveBeenCalledTimes(1);
  });
});
