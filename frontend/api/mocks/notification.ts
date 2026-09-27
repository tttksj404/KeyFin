import { ApiError } from "@/api/error";
import {
  isInstallationId,
  toPushDeviceRequest,
  type CoachFeedbackDto,
  type NotificationItemDto,
  type NotificationListDto,
  type PushDeviceRequest,
} from "@/features/notification/model";
import { currentDateKey, parseKSTDateKey, toKSTDateKey } from "@/lib/date";

/**
 * GET /notifications · PATCH /notifications/{id}/read 목 (백엔드 NotificationService, 2026-09-17).
 * 최근 5건은 Pencil PAGE-28 알림함 (XZ84O) 과 같다: 오늘 예산 알림·이체 요청(안 읽음), 어제 미확정 정리·코칭, 사흘 전 미납 경고.
 * 그 앞으로 20일 전까지 미확정 정리·코칭을 채워 모두 27건이라 한 쪽(20건)을 넘긴다 — 스크롤 끝에서 다음 쪽을 부르는지 보기 위한 값이다.
 * refId 는 다른 목과 잇는다: 이체 501(api/mocks/transfer.ts), 봉투 1 외식(api/mocks/budget.ts), 미확정 거래 501(api/mocks/transaction.ts).
 * COACHING 은 서버가 실제로 만드는 "새로 정리할 거래가 있어요"(TransactionNotificationService, refId = 거래 id) 모양이다 —
 * 누르면 미확정 정리 화면에서 그 거래의 분류 창이 열린다(2026-09-21).
 * 서버처럼 읽음 상태를 들고 있어 다시 들어와도 읽은 건은 읽은 채로 남는다.
 */
type MockNotification = Omit<NotificationItemDto, "id" | "createdAt"> & { daysAgo: number; time: string };

const RECENT: MockNotification[] = [
  {
    daysAgo: 3,
    time: "09:00",
    type: "WARNING",
    title: "카드 대금 출금일이 다가와요",
    body: "신한카드 대금 214,000원이 곧 나가요. 출금 계좌 잔액을 확인해 주세요.",
    refId: null,
    requiresAction: false,
    isRead: true,
  },
  {
    daysAgo: 1,
    time: "20:00",
    type: "COACHING",
    title: "새로 정리할 거래가 있어요",
    body: "메가커피 역삼점 4,500원을 분류해 주세요.",
    refId: "501",
    requiresAction: true,
    isRead: false,
  },
  {
    daysAgo: 1,
    time: "21:00",
    type: "CLEANUP",
    title: "확인할 거래 3건이 있어요",
    body: "오늘 결제한 거래의 봉투를 정해 주세요.",
    refId: null,
    requiresAction: true,
    isRead: true,
  },
  {
    daysAgo: 0,
    time: "07:00",
    type: "TRANSFER_REQUEST",
    title: "월세 결제 준비가 필요해요",
    body: "내일 월세 550,000원이 나가요. 230,000원을 미리 옮길까요?",
    refId: "501",
    requiresAction: true,
    isRead: false,
  },
  {
    daysAgo: 0,
    time: "12:40",
    type: "BUDGET_ALERT",
    title: "외식 봉투가 30% 남았어요",
    body: "이번 달 외식에 32,000원 남았어요.",
    refId: "1",
    requiresAction: false,
    isRead: false,
  },
];

const OLDER_DAYS = 20;
const FIRST_OLDER_DAY = 4;

/** 오래된 순으로 만든다. 사흘마다 코칭, 매일 미확정 정리 */
function olderNotifications(): MockNotification[] {
  const older: MockNotification[] = [];
  for (let daysAgo = OLDER_DAYS; daysAgo >= FIRST_OLDER_DAY; daysAgo -= 1) {
    if (daysAgo % 3 === 0) {
      older.push({
        daysAgo,
        time: "20:00",
        type: "COACHING",
        title: "소비 코칭이 도착했어요",
        body: "이번 주 봉투 흐름을 정리했어요.",
        refId: null,
        requiresAction: false,
        isRead: true,
      });
    }
    older.push({
      daysAgo,
      time: "21:00",
      type: "CLEANUP",
      title: "확인할 거래가 있어요",
      body: "봉투를 정하지 않은 거래를 정리해 주세요.",
      refId: null,
      requiresAction: true,
      isRead: true,
    });
  }
  return older;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function build(todayKey: string): NotificationItemDto[] {
  const today = parseKSTDateKey(todayKey).getTime();
  return [...olderNotifications(), ...RECENT].map(({ daysAgo, time, ...rest }, index) => ({
    ...rest,
    id: index + 1,
    createdAt: `${toKSTDateKey(new Date(today - daysAgo * DAY_MS))}T${time}:00`,
  }));
}

let notifications: NotificationItemDto[] | null = null;

function store(): NotificationItemDto[] {
  notifications ??= build(currentDateKey());
  return notifications;
}

/** 서버처럼 id 내림차순, cursor 보다 작은 id 만, 마지막 쪽이면 nextCursor null */
export function notificationListMock(page: { cursor: number | null; size: number }): NotificationListDto {
  const sorted = [...store()].sort((a, b) => b.id - a.id).filter((item) => page.cursor === null || item.id < page.cursor);
  const items = sorted.slice(0, page.size);
  const hasNext = sorted.length > page.size;
  return { items: items.map((item) => ({ ...item })), nextCursor: hasNext ? items[items.length - 1].id : null };
}

/** GET /notifications/{id}/coach-feedback 목. 예산 알림이면 코치 문장을, 그 외는 NONE 을 준다 */
export function coachFeedbackMock(notificationId: number): CoachFeedbackDto {
  const target = store().find((item) => item.id === notificationId);
  if (target?.type !== "BUDGET_ALERT") return { status: "NONE", text: null };
  return { status: "READY", text: "외식 봉투가 30% 남았다냥. 주기 끝까지 12일 남았으니 하루 2,600원 안쪽으로 쓰면 버틸 수 있다냥." };
}

/** 이미 읽은 알림도 성공. 없는 id 는 404 NOTI_001 */
export function markNotificationReadMock(notificationId: number): void {
  const target = store().find((item) => item.id === notificationId);
  if (target === undefined) throw new ApiError(404, "NOTI_001", "알림을 찾을 수 없습니다.");
  target.isRead = true;
}

/** 활성 푸시 기기: 설치 UUID(소문자) → FCM 토큰. 서버 push_devices 의 활성 행 자리 */
const pushDevices = new Map<string, string>();

function invalidInput(): ApiError {
  return new ApiError(400, "COMMON_001", "입력값이 올바르지 않습니다.");
}

/**
 * PUT /me/push-devices/{installationId} 목. 서버처럼 UUID·토큰 모양을 검사하고,
 * 같은 설치는 덮어쓰고 같은 토큰이 다른 설치에 있으면 그 연결을 푼다.
 */
export function registerPushDeviceMock(installationId: string, request: PushDeviceRequest): void {
  if (!isInstallationId(installationId) || toPushDeviceRequest(request.token) === null || request.platform !== "ANDROID") {
    throw invalidInput();
  }
  for (const [installation, token] of pushDevices) {
    if (token === request.token) pushDevices.delete(installation);
  }
  pushDevices.set(installationId.toLowerCase(), request.token);
}

/** DELETE /me/push-devices/{installationId} 목. 없는 설치여도 성공(멱등) */
export function unregisterPushDeviceMock(installationId: string): void {
  if (!isInstallationId(installationId)) throw invalidInput();
  pushDevices.delete(installationId.toLowerCase());
}

/** 테스트용: 지금 활성인 설치 UUID 목록 */
export function activePushInstallationsMock(): string[] {
  return [...pushDevices.keys()];
}

/** 테스트·개발 재시작용. todayKey 를 주면 그날 기준으로 다시 만든다 */
export function resetNotificationMocks(todayKey?: string): void {
  notifications = todayKey === undefined ? null : build(todayKey);
  pushDevices.clear();
}
