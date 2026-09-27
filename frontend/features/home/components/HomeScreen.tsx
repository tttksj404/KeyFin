import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { Bell, CircleQuestionMark, Coins, Shirt, Store, WifiOff } from "lucide-react-native";
import * as React from "react";
import { Pressable, View, type LayoutChangeEvent } from "react-native";
import type { LucideIcon } from "lucide-react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Screen, useTopInset } from "@/components/ui/screen";
import { Text } from "@/components/ui/text";
import { needsConfirmation, useCurrentBudget } from "@/features/budget/api/queries";
import { PROPOSAL_FROM_HOME_HREF } from "@/features/budget/components/BudgetProposalScreen";
import { AttendanceToast } from "@/features/home/components/AttendanceToast";
import { CharacterRoom } from "@/features/home/components/CharacterRoom";
import { MOVING_IN_COPY, RoomWaiting, pickReturningCopy } from "@/features/room/components/RoomWaiting";
import { HomeCalendar } from "@/features/home/components/HomeCalendar";
import { HomeCoachTarget } from "@/features/home/components/HomeCoach";
import { useCoachSpeech } from "@/features/home/useCoachSpeech";
import { HomeBoardPanel, HomeWallBoard } from "@/features/home/components/HomeWallBoard";
import { RoomGuideOverlay } from "@/features/home/components/RoomGuideOverlay";
import { ROOM_GUIDE_STEPS, useRoomGuide, type GuideTargetId } from "@/features/home/useRoomGuide";
import { useHomeDataRefresh } from "@/features/home/useHomeDataRefresh";
import { useHomeActive } from "@/features/home/useHomeActive";
import { useCheckAttendance, useRoom } from "@/features/room/api/queries";
import { RoomEditorOverlay } from "@/features/room/components/RoomEditorOverlay";
import { RoomStickerTargets, StickerRemovalDialog } from "@/features/room/components/RoomStickers";
import { coverSceneWidth, getCanvasSize, getSceneScale, type SceneRect } from "@/features/room/model";
import { COACH_CAT_RECT, getWallItemRect, type Placement } from "@/features/room/scene";
import { useCoachSpeechStore } from "@/features/notification/store";
import { selectPlacements, useRoomStore } from "@/features/room/store";
import { useRoomLayoutSync } from "@/features/room/useRoomLayout";
import { currentMonthKey } from "@/lib/date";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

/** 벽 오브젝트가 여는 패널. 지금은 예산 보드 시트 하나뿐이다 — 캘린더는 팝오버를 거치지 않고 결제 캘린더 화면으로 간다(2026-09-18). */
type RoomPanel = "board" | null;

/** 벽 캘린더를 누르면 바로 여는 화면 (PAGE-24). 중간 팝오버를 거치지 않는다 (사용자 결정 2026-09-18) */
const PAYMENT_CALENDAR_ROUTE = "/payment/calendar";

/** 상태바 아래로 사이드 버튼을 내리는 간격 */
/** 방이 들어가는 영역. 테스트가 이 영역의 크기를 알려 줄 때 쓴다 */
export const HOME_ROOM_BOX_TEST_ID = "home-room-box";

const SIDE_ACTION_GAP = 8;
/** 오류 화면은 헤더가 없으니 상태바만큼 내려 준다 */
const ERROR_TOP_GAP = 24;

/**
 * 방 대기 덮개를 아무리 길어도 이만큼만 둔다. 그림 한 장이 끝내 안 읽히면(디코딩 실패, 웹에서 Skia 를 못 받음)
 * "다 그렸다"는 신호가 영영 오지 않아 홈이 통째로 막힌다. 넘기면 덮개를 걷고 방이 스스로 보여 주는 상태(스켈레톤)에 맡긴다.
 */
const SCENE_WAIT_LIMIT_MS = 10_000;

type HomeScreenProps = {
  /** 입주 연출(PAGE-08)에서 막 넘어왔다. 방을 다 그릴 때까지 입주 문구를 이어서 보여 준다 */
  arriving?: boolean;
};

function HomeScreen({ arriving = false }: HomeScreenProps) {
  const router = useRouter();
  const room = useRoom();
  // 재조회가 실패해도 마지막으로 받은 방과 편집 상태를 유지한다.
  const roomData = room.data;
  const initialRoomError = room.isError && roomData === undefined;
  // 방 데이터가 와도 그림(가구·바닥 스프라이트)을 읽는 데 시간이 더 걸린다. 그동안 빈 방·스켈레톤 대신 대기 화면을 덮어 둔다
  // (사용자 요청 2026-09-21). 문구는 들어올 때 한 번 고르고, 기다리는 도중에 바뀌지 않게 상태로 잡아 둔다.
  const [sceneReady, setSceneReady] = React.useState(false);
  const markSceneReady = React.useCallback(() => setSceneReady(true), []);
  React.useEffect(() => {
    if (sceneReady) return;
    const timer = setTimeout(markSceneReady, SCENE_WAIT_LIMIT_MS);
    return () => clearTimeout(timer);
  }, [sceneReady, markSceneReady]);
  const [waitingCopy] = React.useState(() => (arriving ? MOVING_IN_COPY : pickReturningCopy()));
  useHomeDataRefresh();
  useRoomLayoutSync();
  const topInset = useTopInset();
  const month = currentMonthKey();
  const budget = useCurrentBudget();
  const attendance = useHomeAttendance(roomData !== undefined && !roomData.checkedInToday);
  const [panel, setPanel] = React.useState<RoomPanel>(null);
  const [selectedSticker, setSelectedSticker] = React.useState<Placement | null>(null);
  const [box, setBox] = React.useState({ width: 0, height: 0 });
  const guide = useRoomGuide(roomData !== undefined && sceneReady);
  const placements = useRoomStore(selectPlacements);
  // 준비된 AI 코칭만 표시한다. 푸시 문구·방 상태·미확정 결제는 말풍선으로 반복하지 않는다.
  // 방 대기 화면·안내·보드·딱지 창이 떠 있는 동안에는 겹치지 않게 가린다.
  const aiSpeech = useCoachSpeechStore((state) => state.latest);
  const clearAiSpeech = useCoachSpeechStore((state) => state.clear);
  const coachSpeechPaused = !sceneReady || guide.step !== null || panel !== null || selectedSticker !== null;
  const homeActive = useHomeActive();
  const coachSpeech = useCoachSpeech(aiSpeech, { paused: coachSpeechPaused, active: homeActive }, clearAiSpeech);
  // 방 밖(화면)에 떠 있는 버튼은 씬 좌표가 없어 실제로 그려진 자리를 재 둔다
  const [buttonRects, setButtonRects] = React.useState<Partial<Record<GuideTargetId, SceneRect>>>({});
  const measureButton = React.useCallback((id: GuideTargetId, rect: SceneRect) => {
    setButtonRects((current) => (sameRect(current[id], rect) ? current : { ...current, [id]: rect }));
  }, []);

  const handleLayout = React.useCallback((event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setBox({ width: Math.round(width), height: Math.round(height) });
  }, []);

  // 이번 주기 예산이 확정 전이면 확정 화면으로 보낸다(노션 예산·잔액 조회, 사용자 결정 2026-09-12). 방·보드가 확정 예산을 기준으로 동작한다.
  if (needsConfirmation(budget)) return <Redirect href={PROPOSAL_FROM_HOME_HREF} />;

  // 방이 홈의 주인공이다(사용자 결정 2026-09-15). 2026-09-18 코치 피드백 반영: **헤더를 없애고 하단 탭바를 뺀 화면 전체를 방으로 채운다.**
  // 화면은 씬(327:404)보다 세로로 길기 때문에 폭을 넘치게 키워(coverSceneWidth) 가운데를 보여 주고 좌우는 잘라 낸다.
  // 인사말은 버렸고 코인·알림만 방 위에 뜨는 사이드 버튼으로 남는다. 방이 화면을 꽉 채우니 세로 스크롤도 없다.
  const roomWidth = box.width > 0 && box.height > 0 ? coverSceneWidth(box.width, box.height) : 0;

  // 방 레이어는 화면 가운데에 놓이고 넘치는 만큼 잘리므로, 씬 좌표를 화면 좌표로 옮길 때 그 절반을 빼 준다.
  const roomScale = roomWidth > 0 ? getSceneScale(roomWidth) : 0;
  const offsetX = Math.max(0, (roomWidth - box.width) / 2);
  const offsetY = roomWidth > 0 ? Math.max(0, (getCanvasSize(roomWidth).height - box.height) / 2) : 0;
  const sceneToScreen = (rect: SceneRect): SceneRect => ({
    x: rect.x * roomScale - offsetX,
    y: rect.y * roomScale - offsetY,
    width: rect.width * roomScale,
    height: rect.height * roomScale,
  });
  const guideRect = (target: GuideTargetId): SceneRect | null => {
    if (roomScale === 0) return null;
    // 코치는 방에 앉은 고양이라 벽 오브젝트처럼 씬 좌표에 있다
    if (target === "coach") return sceneToScreen(COACH_CAT_RECT);
    if (target === "board" || target === "calendar") {
      const rect = getWallItemRect(placements, target);
      return rect === null ? null : sceneToScreen(rect);
    }
    return buttonRects[target] ?? null;
  };

  // 안내 중에 에셋을 직접 누르면 목적을 이룬 것이라 안내를 끝낸다
  const openBoard = () => {
    guide.finish();
    setPanel("board");
  };
  const openCalendar = () => {
    guide.finish();
    router.push(PAYMENT_CALENDAR_ROUTE);
  };

  return (
    <Screen>
      <View className="flex-1 items-center justify-center overflow-hidden" onLayout={handleLayout} testID={HOME_ROOM_BOX_TEST_ID}>
        {initialRoomError ? (
          <View className="w-full flex-1 px-6" style={{ paddingTop: topInset + ERROR_TOP_GAP }}>
            <EmptyState
              icon={WifiOff}
              title="방 정보를 불러오지 못했어요"
              description="연결 상태를 확인한 뒤 다시 시도해 주세요."
              action={{ label: "다시 시도", onPress: () => room.refetch(), disabled: room.isFetching }}
            />
          </View>
        ) : null}
        {roomData ? (
          <CharacterRoom
            width={roomWidth > 0 ? roomWidth : undefined}
            viewport={roomWidth > 0 ? box : undefined}
            locked={panel !== null || selectedSticker !== null || coachSpeech?.open === true}
            onSceneReady={markSceneReady}
            sceneObjects={(width) => (
              <>
                <RoomStickerTargets width={width} placements={placements} furnitures={roomData.furnitures}
                  onSelect={(placement) => { guide.finish(); setSelectedSticker(placement); }} />
                <HomeWallBoard width={width} budget={budget} onOpen={openBoard} />
                <HomeCalendar width={width} month={month} onOpen={openCalendar} />
                <HomeCoachTarget
                  width={width}
                  viewport={roomWidth > 0 ? box : undefined}
                  onOpen={guide.finish}
                  speech={coachSpeech}
                />
              </>
            )}
          />
        ) : null}
        {roomData && sceneReady && attendance.isSuccess && attendance.data.granted > 0 ? (
          <AttendanceToast granted={attendance.data.granted} />
        ) : null}
      </View>
      <HomeBoardPanel visible={panel === "board"} budget={budget} onClose={() => setPanel(null)} />
      {selectedSticker && roomData ? <StickerRemovalDialog placement={selectedSticker} stickers={roomData.stickers}
        onClose={() => setSelectedSticker(null)} /> : null}
      {roomData ? (
        <HomeSideActions
          coinBalance={roomData.coinBalance}
          showEdit={panel === null && selectedSticker === null}
          onMeasure={measureButton}
          onHelp={sceneReady ? guide.restart : undefined}
        />
      ) : null}
      {/* 안내 덮개는 방과 사이드 버튼을 모두 덮어야 해서 맨 위에 둔다 */}
      {guide.step ? (
        <RoomGuideOverlay
          rect={guideRect(guide.step.target)}
          message={guide.step.message}
          progress={`${guide.step.index + 1}/${ROOM_GUIDE_STEPS.length}`}
          isLast={guide.step.isLast}
          onNext={guide.next}
          onSkip={guide.finish}
        />
      ) : null}
      {/* 방 대기 덮개. 방은 밑에서 계속 그림을 읽고 있어야 하므로 방을 치우지 않고 위에 덮는다 — 사이드 버튼까지 가려야 해서 맨 위다.
          오류일 때는 걷는다(다시 시도 버튼이 보여야 한다). */}
      {!sceneReady && !initialRoomError ? (
        <View className="absolute inset-0">
          <RoomWaiting copy={waitingCopy} />
        </View>
      ) : null}
    </Screen>
  );
}

/**
 * 홈에 들어올 때 당일 첫 출석이면 POST /attendance 를 한 번 부른다 (FR-GAM-03).
 * 서버 checkedToday 가 1차 방어, 세션 중 재진입은 ref 가 막는다. 실패는 조용히 두지 않고 mutation error 로 남기되 화면은 막지 않는다. (TBD: 실패 문구)
 */
function useHomeAttendance(shouldCheckIn: boolean) {
  const attendance = useCheckAttendance();
  const requested = React.useRef(false);
  const { mutate: checkIn } = attendance;

  useFocusEffect(
    React.useCallback(() => {
      if (!shouldCheckIn || requested.current) return;
      requested.current = true;
      checkIn();
    }, [shouldCheckIn, checkIn])
  );

  return attendance;
}

/**
 * 방 위에 떠 있는 사이드 버튼 줄. 왼쪽에 코인·알림·상점·옷장을 세로로, 오른쪽에 꾸미기 버튼을 둔다 (2026-09-18 코치 피드백, 상점·옷장은 2026-09-20 사용자 요청).
 * 첫 진입 안내 중에는 방과 같이 물러나도록 흐려 둔다 — 방만 어둑해지고 버튼만 밝으면 덮개가 따로 놀아 보인다 (2026-09-20).
 * 방은 화면보다 넓을 수 있어(cover 맞춤) 방 기준이 아니라 **화면 기준**으로 놓는다 — 방 레이어에 두면 오른쪽 버튼이 화면 밖으로 나간다.
 */
function HomeSideActions({
  coinBalance,
  showEdit,
  onMeasure,
  onHelp,
}: {
  coinBalance: number;
  showEdit: boolean;
  onMeasure: (id: GuideTargetId, rect: SceneRect) => void;
  /** 첫 진입 안내를 다시 연다. 방이 다 그려지기 전에는 undefined 라 버튼을 숨긴다 */
  onHelp?: () => void;
}) {
  const topInset = useTopInset();

  return (
    <View
      className="absolute left-0 right-0 flex-row items-start justify-between px-4"
      style={{ top: topInset + SIDE_ACTION_GAP }}
      pointerEvents="box-none"
    >
      <View className="items-start gap-2" pointerEvents="box-none">
        <CoinBadge balance={coinBalance} />
        <NotificationButton onMeasure={onMeasure} />
        <RoomActionButton
          icon={Store}
          label="상점"
          hint="상점을 엽니다"
          faceClassName="bg-primary"
          iconClassName="text-primary-foreground"
          route={SHOP_ROUTE}
          guideId="shop"
          onMeasure={onMeasure}
        />
        <RoomActionButton
          icon={Shirt}
          label="옷장"
          hint="캐릭터 옷을 갈아입습니다"
          faceClassName="bg-positive"
          iconClassName="text-positive-foreground"
          route={WARDROBE_ROUTE}
          guideId="wardrobe"
          onMeasure={onMeasure}
        />
        {onHelp ? <HelpButton onPress={onHelp} /> : null}
      </View>
      {showEdit ? <RoomEditorOverlay /> : null}
    </View>
  );
}

const COIN_HISTORY_ROUTE = "/coin";

/**
 * 방 위에 떠 있는 버튼의 게임 UI 톤 (사용자 요청 2026-09-23 "게임 화면 톤으로").
 * 앱 화면과 같은 연보라 원이면 방 위에서 앱 UI 로 보여, 색 면 + 흰 테두리 + 아래쪽 음영으로 입체 버튼처럼 만든다.
 * 누르면 아래 음영이 얇아져 눌려 들어간 것처럼 보인다. 색은 버튼마다 다른 시맨틱 토큰이고 음영·테두리는 고정 토큰 white·black 이다.
 */
const GAME_BUTTON_CLASS =
  "h-12 w-12 items-center justify-center rounded-lg border-2 border-b-4 border-white border-b-black/20 shadow-md shadow-black/20 active:border-b-2";
/** 게임 톤 아이콘은 선을 조금 굵게 그린다 */
const GAME_ICON_STROKE = 2.5;

// Pencil CoinBadge (DsQOx) 를 게임 톤으로 바꿨다(2026-09-23): 반투명 검정 알약 + 흰 테두리 금화 + 흰 숫자. 누르면 코인 이력(PAGE-30)으로 간다.
function CoinBadge({ balance }: { balance: number }) {
  const router = useRouter();
  const text = formatKRW(String(balance), { unit: false });

  return (
    <Pressable
      className="h-11 flex-row items-center gap-2 rounded-full border-2 border-white/40 bg-black/40 pl-1 pr-4 active:opacity-80"
      accessibilityRole="button"
      accessibilityLabel={`코인 ${text}개`}
      accessibilityHint="코인 이력을 엽니다"
      hitSlop={8}
      onPress={() => router.push(COIN_HISTORY_ROUTE)}
    >
      <View className="h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-warning" accessible={false}>
        <Icon as={Coins} size={16} strokeWidth={GAME_ICON_STROKE} className="text-warning-foreground" />
      </View>
      <Text className="text-h3 tabular-nums text-white">{text}</Text>
    </Pressable>
  );
}

const NOTIFICATION_ROUTE = "/notification";
const SHOP_ROUTE = "/shop";
const WARDROBE_ROUTE = "/character/wardrobe";

type RoomActionButtonProps = {
  icon: LucideIcon;
  /** 스크린리더가 읽는 이름 */
  label: string;
  hint: string;
  /** 버튼 면 색. 봉투처럼 버튼마다 다른 색을 줘 한눈에 갈린다 (사용자 요청 2026-09-20, 면 색은 2026-09-23 게임 톤) */
  faceClassName: string;
  /** 면 색 위에 올라가는 아이콘 색(그 면 색의 -foreground) */
  iconClassName: string;
  route: string;
  /** 첫 진입 안내가 가리킬 대상 id */
  guideId: GuideTargetId;
  onMeasure: (id: GuideTargetId, rect: SceneRect) => void;
};

// Pencil NotificationBtn (q6hfgQ) 을 게임 톤으로 바꿨다(2026-09-23, GAME_BUTTON_CLASS). 알림·상점·옷장이 같은 모양이라 함께 쓴다.
// 첫 진입 안내가 이 버튼들도 가리키므로 그려진 자리를 창 기준으로 재서 올려 보낸다 — 씬 좌표가 없는 화면 레이어라 계산으로는 못 구한다.
function RoomActionButton({ icon, label, hint, faceClassName, iconClassName, route, guideId, onMeasure }: RoomActionButtonProps) {
  const router = useRouter();
  const ref = React.useRef<View>(null);
  const measure = React.useCallback(() => {
    ref.current?.measureInWindow((x, y, width, height) => onMeasure(guideId, { x, y, width, height }));
  }, [guideId, onMeasure]);

  return (
    <Pressable
      ref={ref}
      onLayout={measure}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={hint}
      hitSlop={8}
      className={cn(GAME_BUTTON_CLASS, faceClassName)}
      onPress={() => router.push(route)}
    >
      <Icon as={icon} size={22} strokeWidth={GAME_ICON_STROKE} className={iconClassName} />
    </Pressable>
  );
}

/**
 * 홈 안내 다시 보기 (사용자 요청 2026-09-23). 첫 진입 안내는 한 번 보면 다시 뜨지 않아, 사이드 버튼 줄 맨 아래에 "?" 로 다시 여는 길을 둔다.
 * 모양은 알림·상점·옷장과 같은 게임 톤 버튼이다. 안내가 가리키는 대상은 아니라 자리를 재지 않는다.
 */
export const HOME_HELP_LABEL = "홈 안내 다시 보기";

function HelpButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={HOME_HELP_LABEL}
      accessibilityHint="홈 화면 사용법을 처음부터 다시 보여 줍니다"
      hitSlop={8}
      className={cn(GAME_BUTTON_CLASS, "bg-highlight")}
      onPress={onPress}
    >
      <Icon as={CircleQuestionMark} size={22} strokeWidth={GAME_ICON_STROKE} className="text-highlight-foreground" />
    </Pressable>
  );
}

// 누르면 알림함(PAGE-28)으로 간다.
function NotificationButton({ onMeasure }: { onMeasure: (id: GuideTargetId, rect: SceneRect) => void }) {
  return (
    <RoomActionButton
      icon={Bell}
      label="알림"
      hint="알림함을 엽니다"
      faceClassName="bg-info"
      iconClassName="text-info-foreground"
      route={NOTIFICATION_ROUTE}
      guideId="notification"
      onMeasure={onMeasure}
    />
  );
}

/** 잰 자리가 그대로면 상태를 두어 무한 갱신을 막는다 */
function sameRect(left: SceneRect | undefined, right: SceneRect): boolean {
  return left !== undefined && left.x === right.x && left.y === right.y && left.width === right.width && left.height === right.height;
}

export { HomeScreen };
