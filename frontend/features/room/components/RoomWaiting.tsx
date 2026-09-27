import * as React from "react";
import { View } from "react-native";

import { LottieLoop } from "@/components/ui/lottie-loop";
import { Sprite, type SpriteFrames } from "@/components/ui/sprite";
import { Text } from "@/components/ui/text";
import { CHARACTER_FRAMES } from "@/features/room/assets";
import { cn } from "@/lib/utils";

const DOT_INTERVAL_MS = 400;
const DOTS = [0, 1, 2];

/** 시안(sla4v)의 원형 200 · 캐릭터 160. 4px 스케일 밖 값이라 크기만 style 로 준다 */
const CIRCLE_STYLE = { width: 200, height: 200 } as const;
const CHARACTER_STYLE = { width: 160, height: 160 } as const;

/** 원 둘레에서 별이 번갈아 반짝이는 장식(직접 만든 Lottie, 240×240). 원보다 20씩 크게 겹친다 */
const SPARKLES = require("@/assets/lottie/moving-in-sparkles.json");
const SPARKLES_STYLE = { width: 240, height: 240 } as const;

export type RoomWaitingCopy = {
  title: string;
  description: string;
  frames: SpriteFrames;
  /** 캐릭터 그림을 읽어 주는 말 */
  spriteLabel: string;
};

/** 처음 입주할 때(PAGE-08). 입주 화면과, 거기서 넘어온 홈이 방을 다 그릴 때까지 같은 문구를 이어서 쓴다 */
export const MOVING_IN_COPY: RoomWaitingCopy = {
  title: "캐릭터가 입주하고 있어요",
  description: "잠시만 기다려 주세요.\n방을 준비하고 있어요.",
  frames: CHARACTER_FRAMES.celebrate,
  spriteLabel: "입주하는 캐릭터",
};

/**
 * 이미 입주한 계정이 홈에 들어올 때. 방 그림을 읽는 동안 캐릭터가 뭔가 하느라 잠깐 안 보인다는 핑계를 댄다(사용자 요청 2026-09-21).
 * 들어올 때마다 하나를 고른다 — 문구만 다르고 뜻은 모두 "곧 나온다"다.
 */
const RETURNING_COPIES: readonly RoomWaitingCopy[] = [
  { title: "캐릭터가 샤워하고 있어요", description: "금방 나올 거예요.\n잠시만 기다려 주세요.", frames: CHARACTER_FRAMES.wave, spriteLabel: "인사하는 캐릭터" },
  { title: "캐릭터가 방을 치우고 있어요", description: "손님 맞을 준비 중이에요.\n잠시만 기다려 주세요.", frames: CHARACTER_FRAMES.scan, spriteLabel: "방을 살펴보는 캐릭터" },
  { title: "캐릭터가 옷을 고르고 있어요", description: "오늘은 뭘 입을까요?\n잠시만 기다려 주세요.", frames: CHARACTER_FRAMES.wave, spriteLabel: "인사하는 캐릭터" },
  { title: "캐릭터가 가계부를 보고 있어요", description: "오늘 쓴 돈을 확인하는 중이에요.\n잠시만 기다려 주세요.", frames: CHARACTER_FRAMES.phone, spriteLabel: "휴대폰을 보는 캐릭터" },
];

export function pickReturningCopy(random: () => number = Math.random): RoomWaitingCopy {
  return RETURNING_COPIES[Math.min(RETURNING_COPIES.length - 1, Math.floor(random() * RETURNING_COPIES.length))];
}

// Pencil character-moving-in (sla4v). 방이 준비되기를 기다리는 화면 — 입주 연출(PAGE-08)과 홈의 방 대기 덮개가 같이 쓴다.
function RoomWaiting({ copy }: { copy: RoomWaitingCopy }) {
  return (
    <View className="flex-1 items-center justify-center gap-8 bg-background px-6" accessibilityLiveRegion="polite">
      <View className="items-center justify-center" style={SPARKLES_STYLE}>
        <View className="pointer-events-none absolute">
          <LottieLoop source={SPARKLES} width={SPARKLES_STYLE.width} height={SPARKLES_STYLE.height} />
        </View>
        <View className="items-center justify-center overflow-hidden rounded-full bg-muted" style={CIRCLE_STYLE}>
          <Sprite frames={copy.frames} style={CHARACTER_STYLE} accessibilityLabel={copy.spriteLabel} />
        </View>
      </View>

      <View className="items-center gap-2">
        <Text className="text-h1 text-foreground" accessibilityRole="header">
          {copy.title}
        </Text>
        <Text className="text-center text-body-sm text-card-foreground">{copy.description}</Text>
      </View>

      <LoadingDots />
    </View>
  );
}

/** 점 세 개가 차례로 켜지는 인디케이터. 화면이 곧 사라지므로 애니메이션 라이브러리 없이 간격만 돌린다. */
function LoadingDots() {
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    const timer = setInterval(() => setActive((prev) => (prev + 1) % DOTS.length), DOT_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <View className="flex-row gap-2" accessible accessibilityLabel="불러오는 중">
      {DOTS.map((dot) => (
        <View key={dot} className={cn("h-2.5 w-2.5 rounded-full", dot === active ? "bg-primary" : "bg-border")} />
      ))}
    </View>
  );
}

export { RoomWaiting };
