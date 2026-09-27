import { ApiError, NETWORK_ERROR_CODE } from "@/api/error";
import {
  activePushInstallationsMock,
  markNotificationReadMock,
  notificationListMock,
  registerPushDeviceMock,
  resetNotificationMocks,
  unregisterPushDeviceMock,
} from "@/api/mocks/notification";
import { isRetryablePushError } from "@/features/notification/errors";
import {
  groupNotificationsByDate,
  isInstallationId,
  markNotificationReadInPage,
  needsAction,
  notificationDateLabel,
  notificationHref,
  notificationTimeLabel,
  pushNotificationHref,
  pushNotificationId,
  budgetAlertCopy,
  shouldShowPushBanner,
  toCoachFeedback,
  toInboxNotification,
  toNotificationPage,
  toPushDataType,
  toPushDeviceRequest,
  type NotificationItemDto,
} from "@/features/notification/model";
import { ContractMismatchError } from "@/lib/contract";

const TODAY = "2026-09-17";

/** 계약 예시(Swagger NotificationControllerDocs)의 이체 승인 요청 */
function dto(overrides: Partial<NotificationItemDto> = {}): NotificationItemDto {
  return {
    id: 123,
    type: "TRANSFER_REQUEST",
    title: "이체 승인 요청",
    body: "확인이 필요한 이체 요청이 있습니다.",
    refId: "456",
    requiresAction: true,
    isRead: false,
    createdAt: "2026-09-16T22:00:00",
    ...overrides,
  };
}

describe("toNotificationPage", () => {
  it("계약 예시를 화면 모델로 옮기고 날짜 키를 붙인다", () => {
    const page = toNotificationPage({ items: [dto()], nextCursor: null });

    expect(page.nextCursor).toBeNull();
    expect(page.items[0]).toMatchObject({ id: 123, type: "TRANSFER_REQUEST", refId: "456", dateKey: "2026-09-16" });
    expect(notificationTimeLabel(page.items[0])).toBe("22:00");
  });

  it("모르는 종류는 UNKNOWN 으로 흡수하고, 본문·refId 는 null 을 허용한다", () => {
    expect(toInboxNotification(dto({ type: "PROMOTION", body: null, refId: null }))).toMatchObject({
      type: "UNKNOWN",
      body: null,
      refId: null,
    });
  });

  it("id·createdAt 형식이 틀리면 계약 불일치다", () => {
    expect(() => toInboxNotification(dto({ id: 0 }))).toThrow(ContractMismatchError);
    expect(() => toInboxNotification(dto({ createdAt: "2026-09-16T22:00:00+09:00" }))).toThrow(ContractMismatchError);
  });
});

describe("notificationHref — 종류별 이동 (frontend-spec §3)", () => {
  it("refId 가 id 면 그 대상 화면으로 간다", () => {
    expect(notificationHref({ type: "TRANSFER_REQUEST", refId: "501" })).toBe("/payment/transfer/501");
    expect(notificationHref({ type: "BUDGET_ALERT", refId: "1" })).toBe("/budget/1");
    expect(notificationHref({ type: "CLEANUP", refId: null })).toBe("/transaction/pending");
    expect(notificationHref({ type: "WARNING", refId: "11" })).toBe("/payment/calendar");
    expect(notificationHref({ type: "SUBSCRIPTION_CARD", refId: "12" })).toBe("/payment/fixed-expense/12");
    expect(notificationHref({ type: "SUBSCRIPTION_CARD", refId: null })).toBe("/payment/fixed-expense");
    // 서버의 COACHING 은 "새로 정리할 거래가 있어요" 이고 refId 가 거래 id 다 — 미확정 정리에서 그 거래의 분류 창을 연다
    expect(notificationHref({ type: "COACHING", refId: "31" })).toBe("/transaction/pending?focus=31");
    expect(notificationHref({ type: "COACHING", refId: null })).toBe("/");
    expect(notificationHref({ type: "COACHING", refId: "../my/settings" })).toBe("/");
  });

  it("refId 가 없거나 id 모양이 아니면 목록 화면으로, 모르는 종류는 갈 곳이 없다", () => {
    expect(notificationHref({ type: "TRANSFER_REQUEST", refId: null })).toBe("/payment/calendar");
    expect(notificationHref({ type: "TRANSFER_REQUEST", refId: "../settings" })).toBe("/payment/calendar");
    expect(notificationHref({ type: "BUDGET_ALERT", refId: "0" })).toBe("/budget");
    expect(notificationHref({ type: "UNKNOWN", refId: "1" })).toBeNull();
  });
});

describe("읽음 상태", () => {
  it("'확인 필요' 는 안 읽은 조치 필요 건에만 붙는다 — 서버가 requiresAction 을 풀지 않아도 읽으면 뗀다", () => {
    expect(needsAction(toInboxNotification(dto()))).toBe(true);
    expect(needsAction(toInboxNotification(dto({ isRead: true })))).toBe(false);
    expect(needsAction(toInboxNotification(dto({ requiresAction: false })))).toBe(false);
  });

  it("낙관적 읽음 반영은 해당 알림만 바꾸고, 바꿀 게 없으면 같은 쪽을 돌려준다", () => {
    const page = toNotificationPage({ items: [dto({ id: 2 }), dto({ id: 1, isRead: true })], nextCursor: null });
    const read = markNotificationReadInPage(page, 2);

    expect(read.items.map((item) => item.isRead)).toEqual([true, true]);
    expect(page.items[0].isRead).toBe(false);
    expect(markNotificationReadInPage(page, 1)).toBe(page);
    expect(markNotificationReadInPage(page, 999)).toBe(page);
  });
});

describe("날짜 묶음", () => {
  it("서버 순서(최신순)를 유지하며 이어진 같은 날짜만 묶는다", () => {
    const items = [
      dto({ id: 5, createdAt: "2026-09-17T12:40:00" }),
      dto({ id: 4, createdAt: "2026-09-17T07:00:00" }),
      dto({ id: 3, createdAt: "2026-09-16T21:00:00" }),
    ].map(toInboxNotification);

    expect(groupNotificationsByDate(items).map((group) => [group.dateKey, group.notifications.map((n) => n.id)])).toEqual([
      ["2026-09-17", [5, 4]],
      ["2026-09-16", [3]],
    ]);
  });

  it("제목은 오늘 · 어제 · 월일(요일)이고, 달이 바뀌어도 어제를 맞춘다", () => {
    expect(notificationDateLabel(TODAY, TODAY)).toBe("오늘");
    expect(notificationDateLabel("2026-09-16", TODAY)).toBe("어제");
    expect(notificationDateLabel("2026-09-14", TODAY)).toBe("9월 14일 (월)");
    expect(notificationDateLabel("2026-08-31", "2026-09-01")).toBe("어제");
  });
});

describe("알림 목 — 서버처럼 쪽을 나누고 읽음을 기억한다", () => {
  beforeEach(() => resetNotificationMocks(TODAY));

  it("최신순 20건씩, 마지막 쪽은 nextCursor 가 null 이다", () => {
    const first = notificationListMock({ cursor: null, size: 20 });
    const second = notificationListMock({ cursor: first.nextCursor, size: 20 });

    expect(first.items).toHaveLength(20);
    expect(first.items[0]).toMatchObject({ type: "BUDGET_ALERT", isRead: false, createdAt: "2026-09-17T12:40:00" });
    expect(first.items[1]).toMatchObject({ type: "TRANSFER_REQUEST", refId: "501", requiresAction: true });
    expect(second.items).toHaveLength(7);
    expect(second.nextCursor).toBeNull();
    expect(Math.min(...first.items.map((item) => item.id))).toBeGreaterThan(Math.max(...second.items.map((item) => item.id)));
  });

  it("읽음 처리는 다시 조회해도 남고, 이미 읽은 알림도 성공이며, 없는 id 는 404 NOTI_001 이다", () => {
    const [latest] = notificationListMock({ cursor: null, size: 1 }).items;

    markNotificationReadMock(latest.id);
    markNotificationReadMock(latest.id);
    expect(notificationListMock({ cursor: null, size: 1 }).items[0].isRead).toBe(true);

    let code: string | null = null;
    try {
      markNotificationReadMock(9999);
    } catch (error) {
      code = error instanceof ApiError ? error.code : null;
    }
    expect(code).toBe("NOTI_001");
  });
});

describe("푸시 기기 등록 (PUT·DELETE /me/push-devices/{installationId})", () => {
  const INSTALLATION = "3f2b8c1e-9d4a-4e6b-8a1f-2c3d4e5f6a7b";
  const TOKEN = "fcm-token:APA91b_example";

  beforeEach(() => resetNotificationMocks(TODAY));

  it("설치 UUID 는 하이픈 있는 표준 36자만 받는다(대소문자 무관)", () => {
    expect(isInstallationId(INSTALLATION)).toBe(true);
    expect(isInstallationId(INSTALLATION.toUpperCase())).toBe(true);
    expect(isInstallationId(INSTALLATION.replaceAll("-", ""))).toBe(false);
    expect(isInstallationId("../me")).toBe(false);
    expect(isInstallationId(null)).toBe(false);
  });

  it("토큰은 서버 검증과 같은 모양일 때만 요청이 되고 platform 은 ANDROID 로 고정이다", () => {
    expect(toPushDeviceRequest(TOKEN)).toEqual({ token: TOKEN, platform: "ANDROID" });
    expect(toPushDeviceRequest("")).toBeNull();
    expect(toPushDeviceRequest("has space")).toBeNull();
    expect(toPushDeviceRequest("가".repeat(3))).toBeNull();
    expect(toPushDeviceRequest("a".repeat(2049))).toBeNull();
    expect(toPushDeviceRequest(undefined)).toBeNull();
  });

  it("목은 같은 설치를 덮어쓰고, 같은 토큰이 다른 설치에 있으면 그 연결을 푼다", () => {
    const other = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";

    registerPushDeviceMock(other, { token: TOKEN, platform: "ANDROID" });
    registerPushDeviceMock(INSTALLATION, { token: TOKEN, platform: "ANDROID" });
    registerPushDeviceMock(INSTALLATION, { token: TOKEN, platform: "ANDROID" });

    expect(activePushInstallationsMock()).toEqual([INSTALLATION]);
  });

  it("해제는 없는 설치여도 성공하고, UUID 가 아니면 등록·해제 모두 400 COMMON_001 이다", () => {
    const codeOf = (run: () => void) => {
      try {
        run();
        return null;
      } catch (error) {
        return error instanceof ApiError ? error.code : "NOT_API_ERROR";
      }
    };

    registerPushDeviceMock(INSTALLATION, { token: TOKEN, platform: "ANDROID" });
    unregisterPushDeviceMock(INSTALLATION);
    unregisterPushDeviceMock(INSTALLATION);
    expect(activePushInstallationsMock()).toEqual([]);

    expect(codeOf(() => registerPushDeviceMock("not-a-uuid", { token: TOKEN, platform: "ANDROID" }))).toBe("COMMON_001");
    expect(codeOf(() => unregisterPushDeviceMock("not-a-uuid"))).toBe("COMMON_001");
  });

  it("다시 보낼 오류는 동시 변경(PUSH_001)과 연결 끊김뿐이다", () => {
    expect(isRetryablePushError(new ApiError(409, "PUSH_001", "기기 정보가 변경 중입니다."))).toBe(true);
    expect(isRetryablePushError(new ApiError(0, NETWORK_ERROR_CODE, ""))).toBe(true);
    expect(isRetryablePushError(new ApiError(400, "COMMON_001", ""))).toBe(false);
    expect(isRetryablePushError(new ApiError(404, "USER_001", ""))).toBe(false);
    expect(isRetryablePushError(new Error("x"))).toBe(false);
  });
});

describe("포그라운드 푸시 표시 (FCM data 규약)", () => {
  it("data.type 을 그대로 읽고(Notion 9종 + 지금 서버의 WARNING), 모르는 값·없는 값·잘못된 모양은 UNKNOWN 이다", () => {
    expect(toPushDataType({ type: "TRANSFER_REQUEST", transferId: "501" })).toBe("TRANSFER_REQUEST");
    expect(toPushDataType({ type: "PAYMENT_RISK", fixedExpenseId: "7" })).toBe("PAYMENT_RISK");
    expect(toPushDataType({ type: "WARNING", refId: "11" })).toBe("WARNING");
    expect(toPushDataType({ type: "REFUND" })).toBe("UNKNOWN");
    expect(toPushDataType({ type: 3 })).toBe("UNKNOWN");
    expect(toPushDataType({})).toBe("UNKNOWN");
    expect(toPushDataType(undefined)).toBe("UNKNOWN");
    expect(toPushDataType(null)).toBe("UNKNOWN");
    expect(toPushDataType("TRANSFER_REQUEST")).toBe("UNKNOWN");
  });

  it("방 연출·코인 지급만 배너 없이 지나가고 나머지는 모르는 종류까지 띄운다", () => {
    expect(shouldShowPushBanner("REACTION")).toBe(false);
    expect(shouldShowPushBanner("COIN_GRANTED")).toBe(false);
    expect(shouldShowPushBanner("TRANSFER_REQUEST")).toBe(true);
    expect(shouldShowPushBanner("CLASSIFY_QUESTION")).toBe(true);
    expect(shouldShowPushBanner("UNKNOWN")).toBe(true);
  });
});

describe("푸시 탭 딥링크 (frontend-spec §3 · 푸시 전용 4종은 2026-09-20 결정)", () => {
  it("id 가 있는 종류는 상세로, 없거나 모양이 아니면 목록으로 보낸다", () => {
    expect(pushNotificationHref({ type: "TRANSFER_REQUEST", transferId: "501" })).toBe("/payment/transfer/501");
    expect(pushNotificationHref({ type: "TRANSFER_REQUEST" })).toBe("/payment/calendar");
    expect(pushNotificationHref({ type: "TRANSFER_REQUEST", transferId: "0" })).toBe("/payment/calendar");
    expect(pushNotificationHref({ type: "BUDGET_ALERT", envelopeId: "3", threshold: "30" })).toBe("/budget/3");
    expect(pushNotificationHref({ type: "BUDGET_ALERT", envelopeId: "../my/settings" })).toBe("/budget");
    expect(pushNotificationHref({ type: "CLASSIFY_QUESTION", transactionId: "77" })).toBe("/transaction/pending?focus=77");
    expect(pushNotificationHref({ type: "CLASSIFY_QUESTION" })).toBe("/transaction/pending");
  });

  it("지금 서버가 보내는 모양(type 5종 + refId)도 같은 화면으로 간다", () => {
    const server = (type: string, refId?: string) => ({ notificationId: "9", type, requiresAction: "true", ...(refId === undefined ? {} : { refId }) });

    expect(pushNotificationHref(server("COACHING", "77"))).toBe("/transaction/pending?focus=77");
    expect(pushNotificationHref(server("COACHING"))).toBe("/");
    expect(pushNotificationHref(server("BUDGET_ALERT", "3"))).toBe("/budget/3");
    expect(pushNotificationHref(server("SUBSCRIPTION_CARD", "12"))).toBe("/payment/fixed-expense/12");
    expect(pushNotificationHref(server("SUBSCRIPTION_CARD", "../x"))).toBe("/payment/fixed-expense");
    expect(pushNotificationHref(server("CLEANUP"))).toBe("/transaction/pending");
    expect(pushNotificationHref(server("WARNING", "11"))).toBe("/payment/calendar");
  });

  it("이체 푸시는 refId 를 이체 id 로 믿지 않는다 — 서버가 '승인 필요'에는 받는 계좌 id 를 넣는다", () => {
    expect(pushNotificationHref({ type: "TRANSFER_REQUEST", refId: "12" })).toBe("/payment/calendar");
    expect(pushNotificationHref({ type: "TRANSFER_REQUEST", refId: "12", transferId: "501" })).toBe("/payment/transfer/501");
  });

  it("id 를 쓰지 않는 종류는 정해진 화면으로 가고, 모르는 종류는 갈 곳이 없다", () => {
    expect(pushNotificationHref({ type: "CLEANUP", pendingCount: "4" })).toBe("/transaction/pending");
    expect(pushNotificationHref({ type: "PAYMENT_RISK", fixedExpenseId: "7" })).toBe("/payment/calendar");
    expect(pushNotificationHref({ type: "NEW_LINK_FOUND", kind: "CARD" })).toBe("/my/links");
    expect(pushNotificationHref({ type: "COIN_GRANTED", reasonCode: "ATTEND" })).toBe("/coin");
    expect(pushNotificationHref({ type: "COACHING", coachingLogId: "9" })).toBe("/");
    expect(pushNotificationHref({ type: "REACTION", reactionType: "HAPPY" })).toBe("/");
    expect(pushNotificationHref({ type: "REFUND" })).toBeNull();
    expect(pushNotificationHref(null)).toBeNull();
  });
});

describe("budgetAlertCopy (예산 잔액 알림 표기, 2026-09-23 결정)", () => {
  it("50·20·5% 단계는 제목과 남은 금액을 그대로 둔다", () => {
    expect(budgetAlertCopy("외식 봉투가 20% 남았어요", "남은 금액 32,000원")).toEqual({
      title: "외식 봉투가 20% 남았어요",
      body: "남은 금액 32,000원",
    });
  });

  it("잔액이 정확히 0원이면 '딱 다 썼어요' 한마디로 바꾼다", () => {
    expect(budgetAlertCopy("외식 봉투가 0% 남았어요", "남은 금액 0원")).toEqual({ title: "외식 봉투를 딱 다 썼어요", body: null });
  });

  it("0% 로 내림됐어도 돈이 남았으면 그대로 둔다", () => {
    expect(budgetAlertCopy("외식 봉투가 0% 남았어요", "남은 금액 1,000원")).toEqual({
      title: "외식 봉투가 0% 남았어요",
      body: "남은 금액 1,000원",
    });
  });

  it("초과는 금액 줄 없이 '초과했어요' 한마디로 둔다", () => {
    expect(budgetAlertCopy("외식 봉투를 초과했어요", "8,000원 초과했어요")).toEqual({ title: "외식 봉투를 초과했어요", body: null });
  });

  it("모르는 모양(복구 알림 등)은 그대로 둔다", () => {
    const recovery = { title: "결제가 취소돼 외식 봉투가 돌아왔어요", body: "12,000원이 복구돼 남은 금액 20,000원이에요" };
    expect(budgetAlertCopy(recovery.title, recovery.body)).toEqual(recovery);
  });
});

describe("toInboxNotification 예산 알림 표기", () => {
  it("알림함에서도 0원은 '딱 다 썼어요', 초과는 한마디로 보인다", () => {
    const base = { id: 9, type: "BUDGET_ALERT", refId: "1", requiresAction: false, isRead: false, createdAt: "2026-09-23T10:00:00" };
    expect(toInboxNotification({ ...base, title: "외식 봉투가 0% 남았어요", body: "남은 금액 0원" })).toMatchObject({
      title: "외식 봉투를 딱 다 썼어요",
      body: null,
    });
    expect(toInboxNotification({ ...base, title: "외식 봉투를 초과했어요", body: "8,000원 초과했어요", requiresAction: true })).toMatchObject({
      title: "외식 봉투를 초과했어요",
      body: null,
    });
  });
});

describe("코치 피드백 (-182 계약 · -184)", () => {
  it("READY 는 문장을 다듬어 두고, 문장 없는 READY 와 모르는 상태는 NONE 으로 흡수한다", () => {
    expect(toCoachFeedback({ status: "READY", text: " 멈추는 편이 좋다냥. " })).toEqual({ status: "READY", text: "멈추는 편이 좋다냥." });
    expect(toCoachFeedback({ status: "READY", text: "  " })).toEqual({ status: "NONE", text: null });
    expect(toCoachFeedback({ status: "PENDING", text: null })).toEqual({ status: "PENDING", text: null });
    expect(toCoachFeedback({ status: "EXPIRED", text: "x" })).toEqual({ status: "NONE", text: null });
  });

  it("푸시 data 의 notificationId 는 양수 문자열일 때만 쓴다", () => {
    expect(pushNotificationId({ notificationId: "41", type: "BUDGET_ALERT" })).toBe(41);
    expect(pushNotificationId({ notificationId: "0" })).toBeNull();
    expect(pushNotificationId({ notificationId: 41 })).toBeNull();
    expect(pushNotificationId(null)).toBeNull();
  });
});
