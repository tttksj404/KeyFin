import { ArrowLeftRight, Bell, CreditCard, ListChecks, MessageCircle, TriangleAlert, Wallet, type LucideIcon } from "lucide-react-native";

import type { NotificationType } from "@/features/notification/model";

/** 알림 종류별 아이콘 (Pencil PAGE-28 알림함 XZ84O Icon tile). 종류 값은 계약이고 아이콘은 클라이언트 상수다 */
const NOTIFICATION_ICONS: Record<NotificationType, LucideIcon> = {
  BUDGET_ALERT: Wallet,
  TRANSFER_REQUEST: ArrowLeftRight,
  CLEANUP: ListChecks,
  COACHING: MessageCircle,
  WARNING: TriangleAlert,
  SUBSCRIPTION_CARD: CreditCard,
  UNKNOWN: Bell,
};

export function notificationIcon(type: NotificationType): LucideIcon {
  return NOTIFICATION_ICONS[type];
}
