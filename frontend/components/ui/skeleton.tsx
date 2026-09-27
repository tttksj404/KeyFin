// vendor: react-native-reusables (nativewind) — 원본 유지. 프로젝트 수정은 "project:" 주석으로 표시한다.
import { cn } from '@/lib/utils';
import { View } from 'react-native';

function Skeleton({
  className,
  ...props
}: React.ComponentProps<typeof View> & React.RefAttributes<View>) {
  return <View className={cn('bg-accent animate-pulse rounded-md', className)} {...props} />;
}

export { Skeleton };
