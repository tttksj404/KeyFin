import { Platform as SkiaPlatform } from "@shopify/react-native-skia/lib/module/Platform";
import { LoadSkiaWeb } from "@shopify/react-native-skia/lib/module/web";
import * as React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RoomSceneFrame } from "@/features/room/components/RoomSceneFrame";

// 웹에서는 CanvasKit(wasm)을 먼저 내려받아야 Skia 컴포넌트를 쓸 수 있다.
// canvaskit-wasm 은 pnpm 격리 때문에 앱 코드에서 직접 참조할 수 없어, Skia 패키지가 고정한 버전을 읽어 CDN 경로를 만든다.
const CANVASKIT_VERSION: string = require("@shopify/react-native-skia/package.json").dependencies["canvaskit-wasm"];
const locateFile = (file: string) => `https://cdn.jsdelivr.net/npm/canvaskit-wasm@${CANVASKIT_VERSION}/bin/full/${file}`;

/**
 * Skia 캔버스가 버퍼 크기에 곱하는 픽셀 비율. 캔버스 버퍼가 맞는지 검사할 때 기준으로 쓴다.
 * Skia 는 이 값을 `Platform.PixelRatio` 로 **앱 시작 때**(이 파일이 `lib/module/web` 을 import 하는 순간) 읽어 두고,
 * 캔버스 모듈(`SkiaPictureView.web.js`)이 처음 로드될 때 그 값을 상수로 굳힌다. 그 사이(로그인 화면 등)에 기기 에뮬레이션·줌을 켜면
 * 예전 비율로 굳어 방이 흐려지고 새로고침해야 나았다(2026-09-19). 그래서 씬 모듈을 부르기 직전에 현재 값으로 다시 써 준다.
 */
let skiaPixelRatio = 1;

/**
 * `WithSkiaWeb` 과 같은 일(CanvasKit 로드 → 씬 모듈 lazy import)을 하되 lazy 를 모듈 스코프에 둔다.
 * 씬을 다시 붙여도 wasm 과 청크를 그대로 재사용하므로 스켈레톤이 다시 깜빡이지 않는다.
 */
const RoomScene = React.lazy(async () => {
  await LoadSkiaWeb({ locateFile });
  skiaPixelRatio = window.devicePixelRatio || 1;
  SkiaPlatform.PixelRatio = skiaPixelRatio;
  return import("@/features/room/components/RoomScene");
});

/** 버퍼 검사 간격(ms). Skia 의 onLayout 은 ResizeObserver → setTimeout 0 을 거쳐 오므로 그보다 넉넉히 둔다 */
const CHECK_DELAY = 120;
/** 한 번 붙은 캔버스에서 다시 흔들어 보는 횟수. 넘으면 포기한다(무한 루프 방지) */
const MAX_HEAL_TRIES = 6;

/** 캔버스 버퍼가 화면 크기 × Skia 픽셀 비율과 맞는지. 1~2px 반올림 차이는 봐준다 */
function isBufferSharp(canvas: HTMLCanvasElement): boolean {
  const { clientWidth, clientHeight } = canvas;
  if (clientWidth === 0 || clientHeight === 0) return true; // 아직 안 보이는 캔버스는 판단하지 않는다
  const tolerance = skiaPixelRatio + 2;
  return (
    Math.abs(canvas.width - clientWidth * skiaPixelRatio) <= tolerance &&
    Math.abs(canvas.height - clientHeight * skiaPixelRatio) <= tolerance
  );
}

/**
 * Skia 웹 캔버스는 **자기 onLayout 이 뜰 때만** WebGL 서피스를 새로 만들면서
 * `canvas.width = clientWidth × devicePixelRatio` 를 잡는다(`views/SkiaPictureView.web.js`).
 * 그 이벤트가 최종 크기로 안 뜨면 캔버스는 예전(또는 기본 300×150) 버퍼로 남고 브라우저가 그걸 늘려 그려서 방이 흐려진다.
 * 2026-09-18 실측: 버퍼 274×339 인데 화면은 412×509. 2026-09-19 실측: 버퍼 300×150(기본값)인데 화면은 1451×2600
 * — 탭이 가려진 동안 붙으면 ResizeObserver·requestAnimationFrame 이 둘 다 멈춰 있어 "붙은 직후 한 번 흔들기"만으로는 못 고쳤다.
 *
 * 그래서 이벤트를 믿지 않고 **결과(버퍼 크기)를 직접 확인**한다: 붙은 뒤·창 크기 변경·탭 복귀 때마다 버퍼를 재서
 * 안 맞으면 씬 폭을 1px 흔들어 Skia 가 서피스를 다시 만들게 하고, 맞을 때까지(최대 MAX_HEAL_TRIES) 되풀이한다.
 * (남은 한계: 픽셀 비율은 씬 모듈이 처음 로드될 때 고정이라, 방을 한 번 본 뒤 브라우저 줌·기기 에뮬레이션을
 *  바꾸면 새로고침해야 원래 해상도로 돌아온다 — 개발 중에는 콘솔 경고로 알린다.)
 */
function SettledRoomScene({ width }: { width: number }) {
  const hostRef = React.useRef<HTMLDivElement>(null);
  // 처음에는 1px 좁게 그려 크기 변화를 한 번 만든다 — Skia 가 최종 크기로 서피스를 만들 계기가 된다
  const [nudged, setNudged] = React.useState(true);
  const triesRef = React.useRef(0);

  React.useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    const check = () => {
      timer = undefined;
      if (nudged) {
        setNudged(false);
        return;
      }
      const canvas = hostRef.current?.querySelector("canvas");
      if (!canvas) {
        schedule(); // 씬 청크가 아직 안 붙었다(Suspense)
        return;
      }
      if (isBufferSharp(canvas)) {
        triesRef.current = 0;
        return;
      }
      // 가려진 탭에서는 흔들어도 ResizeObserver 가 안 돈다 — 횟수를 쓰지 않고 탭 복귀(visibilitychange)를 기다린다
      if (document.visibilityState === "hidden") return;
      if (triesRef.current >= MAX_HEAL_TRIES) return;
      triesRef.current += 1;
      setNudged(true);
    };
    const schedule = () => {
      if (timer === undefined) timer = setTimeout(check, CHECK_DELAY);
    };
    const recheck = () => {
      triesRef.current = 0;
      schedule();
    };

    schedule();
    window.addEventListener("resize", recheck);
    document.addEventListener("visibilitychange", recheck);
    return () => {
      if (timer !== undefined) clearTimeout(timer);
      window.removeEventListener("resize", recheck);
      document.removeEventListener("visibilitychange", recheck);
    };
  }, [nudged]);

  React.useEffect(() => {
    if (__DEV__ && Math.abs((window.devicePixelRatio || 1) - skiaPixelRatio) > 0.01) {
      console.warn(
        `[room] 화면 픽셀 비율(${window.devicePixelRatio})이 Skia 가 읽어 둔 값(${skiaPixelRatio})과 달라 방이 흐릴 수 있어요. 새로고침하면 맞춰집니다.`
      );
    }
  }, []);

  return (
    <div ref={hostRef} style={HOST_STYLE}>
      <RoomScene width={nudged ? Math.max(1, width - 1) : width} />
    </div>
  );
}

/** 레이아웃에 끼어들지 않고 캔버스를 찾을 기준점만 준다 */
const HOST_STYLE = { display: "contents" } as const;

function RoomSceneLoader() {
  return (
    <RoomSceneFrame>
      {(width) => (
        <React.Suspense fallback={<Skeleton className="h-full w-full" />}>
          <SettledRoomScene key={width} width={width} />
        </React.Suspense>
      )}
    </RoomSceneFrame>
  );
}

export { RoomSceneLoader };
