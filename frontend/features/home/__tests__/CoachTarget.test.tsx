import { fireEvent, render, screen, within } from "@testing-library/react-native";
import * as React from "react";

import { CoachTarget } from "@/features/home/components/CoachTarget";
import type { CoachSpeechView } from "@/features/home/useCoachSpeech";

function makeSpeech(overrides: Partial<CoachSpeechView> = {}): CoachSpeechView {
  return {
    text: "이번 달 예산을 확인해 주세요.",
    open: true,
    unread: true,
    onPressIcon: jest.fn(),
    onClose: jest.fn(),
    ...overrides,
  };
}

describe("CoachTarget", () => {
  it("고양이 자리의 탭 영역을 누르면 알린다", async () => {
    const onPress = jest.fn();
    await render(<CoachTarget width={327} onPress={onPress} />);

    await fireEvent.press(screen.getByRole("button", { name: "코치" }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it.each([
    "이번 달 예산을 확인해 주세요.",
    "외식 지출이 예산을 넘었어요. 남은 기간에는 식비 계획을 조정해 보세요.",
    "카드별 결제 내역과 이번 달 예산을 차근차근 확인해 주세요. ".repeat(30),
  ])("본문을 누르거나 스크롤해도 접히지 않고 모서리의 닫기 버튼으로 접는다", async (text) => {
    const speech = makeSpeech({ text });
    const onPressCat = jest.fn();
    await render(<CoachTarget width={327} speech={speech} onPress={onPressCat} />);

    await fireEvent.press(screen.getByText(text));
    await fireEvent.scroll(screen.getByTestId("coach-speech-content"), {
      nativeEvent: { contentOffset: { x: 0, y: 100 } },
    });
    expect(speech.onClose).not.toHaveBeenCalled();
    expect(onPressCat).not.toHaveBeenCalled();

    const close = screen.getByRole("button", { name: "코치 말풍선 닫기" });
    expect(within(screen.getByTestId("coach-speech-bubble")).queryByRole("button", { name: "코치 말풍선 닫기" })).toBeNull();
    expect(close).toHaveStyle({ position: "absolute", top: 0, right: 0, width: 44, height: 44, zIndex: 1 });
    await fireEvent.press(close);
    expect(speech.onClose).toHaveBeenCalledTimes(1);
    expect(onPressCat).not.toHaveBeenCalled();
  });

  it.each([false, true])("접힌 아이콘은 AI 코칭의 읽음 상태를 표시하고 말풍선만 펼친다 (미읽음: %s)", async (unread) => {
    const speech = makeSpeech({ open: false, unread });
    const onPressCat = jest.fn();
    await render(<CoachTarget width={327} speech={speech} onPress={onPressCat} />);

    expect(screen.queryByText(speech.text)).toBeNull();
    expect(screen.queryByRole("button", { name: "코치 말풍선 닫기" })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: unread ? "코치가 할 말 보기, 새 메시지" : "코치가 할 말 보기" }));
    expect(speech.onPressIcon).toHaveBeenCalledTimes(1);
    expect(speech.onClose).not.toHaveBeenCalled();
    expect(onPressCat).not.toHaveBeenCalled();
  });

  it("AI 코칭이 없으면 고양이 탭 영역만 남긴다", async () => {
    await render(<CoachTarget width={327} speech={null} onPress={jest.fn()} />);

    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "코치" })).toBeTruthy();
  });

  // Jest는 네이티브 레이아웃을 계산하지 않으므로 높이 제한과 스크롤 설정의 계약을 검사한다.
  it.each([
    { width: 327, totalLimit: 180, bubbleLimit: 150, contentLimit: 122 },
    { width: 109, totalLimit: 148, bubbleLimit: 118, contentLimit: 90 },
  ])("폭 $width에서 바깥 닫기 영역을 포함한 높이 상한과 본문 스크롤을 유지한다", async ({ width, totalLimit, bubbleLimit, contentLimit }) => {
    await render(<CoachTarget width={width} speech={makeSpeech()} onPress={jest.fn()} />);

    expect(screen.getByTestId("coach-speech-placement")).toHaveStyle({ height: totalLimit });
    expect(screen.getByTestId("coach-speech-bubble")).toHaveStyle({ maxHeight: bubbleLimit, paddingTop: 18 });
    const content = screen.getByTestId("coach-speech-content");
    expect(content).toHaveStyle({ flexGrow: 0, flexShrink: 1, maxHeight: contentLimit });
    expect(content.props.showsVerticalScrollIndicator).toBe(true);
    expect(content.props.bounces).toBe(false);
  });

  it("화면 오른쪽 여백을 남기면서 본문은 X 열 없이 말풍선 내부 폭을 사용한다", async () => {
    await render(<CoachTarget width={379} viewport={{ width: 280, height: 680 }} speech={makeSpeech()} onPress={jest.fn()} />);

    const placement = screen.getByTestId("coach-speech-placement");
    const rightAtStrollEnd = placement.props.style.left + placement.props.style.width + 12 * (379 / 327) - (379 - 280) / 2;
    expect(rightAtStrollEnd).toBeCloseTo(272); // 화면 오른쪽 8pt를 남긴다.
    const content = screen.getByTestId("coach-speech-content");
    expect(content.props.style.maxWidth + 24 + 2 + 8).toBeCloseTo(placement.props.style.width);
  });
});
