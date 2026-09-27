import { TriangleAlert } from "lucide-react-native";
import * as React from "react";
import { Pressable, View } from "react-native";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Text } from "@/components/ui/text";
import { useDeleteAccount } from "@/features/auth/api/queries";
import { accountDeletionErrorMessage } from "@/features/auth/errors";
import { canSubmitAccountDeletion } from "@/features/auth/model";
import { cn } from "@/lib/utils";

/**
 * 회원 탈퇴 (DELETE /users/me). 되돌릴 수 없는 일이라 확인 창에서 무엇이 사라지는지 먼저 알리고,
 * 서버가 요구하는 현재 비밀번호를 받은 뒤에만 보낸다.
 * 성공하면 세션이 끝나 (tabs) 레이아웃이 로그인 화면으로 보낸다. 실패하면 계정이 그대로 남으므로 창을 닫지 않고 이유를 보여 준다.
 * 비밀번호는 창을 닫을 때마다 지운다 (규칙 80: 민감한 값을 화면 상태에 오래 두지 않는다).
 */
function WithdrawAccountButton() {
  const withdraw = useDeleteAccount();
  const [open, setOpen] = React.useState(false);
  const [password, setPassword] = React.useState("");

  const canSubmit = canSubmitAccountDeletion(password) && !withdraw.isPending;

  const close = () => {
    if (withdraw.isPending) return;
    setPassword("");
    withdraw.reset();
    setOpen(false);
  };

  const submit = () => {
    if (!canSubmit) return;
    withdraw.mutate({ password });
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="회원 탈퇴"
        hitSlop={8}
        className="h-touch items-center justify-center active:opacity-70"
        onPress={() => setOpen(true)}
      >
        <Text className="text-caption text-card-foreground underline">회원 탈퇴</Text>
      </Pressable>

      <Dialog open={open} onOpenChange={(next) => !next && close()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-h3 text-foreground">정말 탈퇴할까요?</DialogTitle>
            <DialogDescription className="text-body-sm text-card-foreground">
              소비 내역·예산·방 꾸미기가 모두 사라지고 되돌릴 수 없어요. 탈퇴한 이메일로는 다시 가입할 수 없어요.
            </DialogDescription>
          </DialogHeader>

          <View className="flex-row items-start gap-2 rounded-lg bg-destructive-muted p-3.5">
            <Icon as={TriangleAlert} size={18} className="text-destructive" />
            <Text className="flex-1 text-caption text-foreground">계속하려면 지금 쓰는 비밀번호를 넣어 주세요.</Text>
          </View>

          <Input
            className={cn("h-input rounded-lg", withdraw.isError && "border-destructive")}
            value={password}
            onChangeText={setPassword}
            placeholder="비밀번호"
            secureTextEntry
            autoCapitalize="none"
            autoComplete="current-password"
            textContentType="password"
            editable={!withdraw.isPending}
            accessibilityLabel="비밀번호"
            returnKeyType="done"
            onSubmitEditing={submit}
          />

          {withdraw.isError ? (
            <Text className="text-caption text-destructive" accessibilityLiveRegion="polite">
              {accountDeletionErrorMessage(withdraw.error)}
            </Text>
          ) : null}

          <DialogFooter>
            <Button variant="secondary" disabled={withdraw.isPending} onPress={close}>
              <Text>취소</Text>
            </Button>
            <Button
              variant="destructive"
              disabled={!canSubmit}
              accessibilityState={{ disabled: !canSubmit }}
              accessibilityLabel="탈퇴하기"
              onPress={submit}
            >
              <Text>{withdraw.isPending ? "탈퇴하는 중" : "탈퇴"}</Text>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export { WithdrawAccountButton };
