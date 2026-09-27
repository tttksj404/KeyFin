import type { SpriteFrames } from "@/components/ui/sprite";

// 방 씬 에셋. 스프라이트는 앱 에셋이므로 assets/sprites 에만 둔다(Git LFS 대상). 가구는 features/room/catalog.ts 에 있다.
// 바닥은 Pencil AI 로 만든 세로 긴 방(design/images/ai/floor-tall-c.jpg, 768×1376)을 그대로 쓴다 — 씬 비율 327:586 (2026-09-18).
// 같은 날 흰색 타일 줄(바닥 이음선·벽 타일선)을 빼고 다시 생성했다(사용자 결정) — a 판은 줄이 있어 버렸다.
// 홈이 하단 탭바 위 화면 전체를 방으로 채우게 되면서 327:404 로는 좌우가 17%씩 잘려 코치·화분이 화면 밖으로 나갔다(사용자 결정).
// 벽·바닥 경계선(scene.ts FLOOR_POLYGON·SURFACES)은 이 그림을 픽셀로 다시 재서 얻었다.
// 옛 그림(floor-default.png, 327:404)은 되돌릴 때를 위해 남겨 두었고 지금은 쓰지 않는다.
export const ROOM_FLOOR = require("@/assets/sprites/floors/floor-tall.jpg");
export const SEIZURE_STICKER = require("@/assets/sprites/room/seizure-sticker.png");
export const CHARACTER_IDLE = require("@/assets/sprites/char1-idle.png");
/** 입주 연출(PAGE-08)에서만 쓰는 환호 포즈 */
export const CHARACTER_CELEBRATE = require("@/assets/sprites/char1-celebrate.png");
/** 온보딩 코치 — 손 흔드는 포즈(로그인·회원가입) */
export const CHARACTER_WAVE = require("@/assets/sprites/char1-wave.png");
/** 온보딩 코치 — 휴대폰 보는 포즈(약관·소비 분석 중) */
export const CHARACTER_PHONE = require("@/assets/sprites/char1-phone.png");
/** 온보딩 코치 — 살펴보는 포즈(금융망 이메일) */
export const CHARACTER_SCAN = require("@/assets/sprites/char1-scan.png");

/**
 * 프레임 전환용 포즈 묶음(components/ui/sprite.tsx). 지금은 포즈당 base 1장이라 정지 이미지와 같다.
 * blink(눈 감음)·motion(손 위치 다른 장) PNG 가 오면 여기에만 꽂으면 로그인·회원가입·입주 화면이 움직인다 (2026-09-16).
 * 프레임은 base 와 같은 크기·같은 발끝 위치여야 한다.
 */
export const CHARACTER_FRAMES = {
  wave: { base: CHARACTER_WAVE },
  phone: { base: CHARACTER_PHONE },
  scan: { base: CHARACTER_SCAN },
  celebrate: { base: CHARACTER_CELEBRATE },
} satisfies Record<string, SpriteFrames>;

/**
 * 코치 고양이(AI 챗봇). 방 씬(Skia)에 늘 앉아 있고 탭하면 코치 말풍선이 열린다 (2026-09-22 사용자 결정 — 옛 32pt 원형 아이콘 버튼을 대신한다).
 * 원본 1254×1254 를 512×512 로 줄였다(그려지는 크기의 약 6배). 자리·크기는 features/room/scene.ts COACH_CAT_* 에 있다.
 */
export const COACH_CAT = require("@/assets/sprites/coach-cat.png");
