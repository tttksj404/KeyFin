import { Check, ChevronDown, X } from "lucide-react-native";
import * as React from "react";
import { Pressable, ScrollView, View } from "react-native";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { cn } from "@/lib/utils";

export type SelectOption = {
  key: string;
  label: string;
  /** 같은 section 이 이어지면 첫 줄 위에 구역 제목을 한 번 단다 */
  section?: string;
};

type FilterSelectProps = {
  /** 시트 제목. 선택값을 못 찾으면 버튼에도 이 이름을 쓴다 */
  title: string;
  options: SelectOption[];
  selectedKey: string;
  disabled?: boolean;
  onSelect: (key: string) => void;
};

// 거래 내역 필터 선택(사용자 결정 2026-09-11: 칩 두 줄 대신 선택창 두 개를 나란히).
// 버튼은 지금 선택값을 보여 주고, 누르면 분류 시트(SubcategorySheet)와 같은 모양의 바텀시트에서 고른다.
function FilterSelect({ title, options, selectedKey, disabled = false, onSelect }: FilterSelectProps) {
  const [open, setOpen] = React.useState(false);
  const label = options.find((option) => option.key === selectedKey)?.label ?? title;

  const handleSelect = (key: string) => {
    setOpen(false);
    if (key !== selectedKey) onSelect(key);
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${title}: ${label}`}
        accessibilityHint="눌러서 고릅니다"
        accessibilityState={{ disabled, expanded: open }}
        disabled={disabled}
        onPress={() => setOpen(true)}
        className={cn(
          "h-10 flex-1 flex-row items-center justify-between gap-1.5 rounded-md border border-border bg-card px-3",
          disabled && "opacity-50"
        )}
      >
        <Text className="shrink text-label text-foreground" numberOfLines={1}>
          {label}
        </Text>
        <Icon as={ChevronDown} size={16} className="text-card-foreground" />
      </Pressable>

      <BottomSheet visible={open} onClose={() => setOpen(false)} closeLabel={`${title} 닫기`}>
            <View className="flex-row items-center justify-between px-5 pt-5">
              <Text className="text-h3 text-popover-foreground" accessibilityRole="header">
                {title}
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="닫기"
                onPress={() => setOpen(false)}
                hitSlop={8}
                className="h-touch w-touch items-center justify-center"
              >
                <Icon as={X} size={20} className="text-card-foreground" />
              </Pressable>
            </View>
            <ScrollView className="max-h-96" contentContainerClassName="px-5 pt-2">
              {options.map((option, index) => (
                <React.Fragment key={option.key}>
                  {option.section !== undefined && option.section !== options[index - 1]?.section ? (
                    <Text className="pb-1 pt-4 text-caption text-card-foreground" accessibilityRole="header">
                      {option.section}
                    </Text>
                  ) : null}
                  <OptionRow option={option} selected={option.key === selectedKey} onPress={() => handleSelect(option.key)} />
                </React.Fragment>
              ))}
            </ScrollView>
      </BottomSheet>
    </>
  );
}

type OptionRowProps = {
  option: SelectOption;
  selected: boolean;
  onPress: () => void;
};

function OptionRow({ option, selected, onPress }: OptionRowProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      className="h-touch flex-row items-center justify-between gap-3"
    >
      <Text className={cn("shrink text-body", selected ? "text-primary" : "text-popover-foreground")} numberOfLines={1}>
        {option.label}
      </Text>
      {selected ? <Icon as={Check} size={18} className="text-primary" /> : null}
    </Pressable>
  );
}

export { FilterSelect };
