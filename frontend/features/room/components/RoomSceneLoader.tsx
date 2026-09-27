import * as React from "react";

import RoomScene from "@/features/room/components/RoomScene";
import { RoomSceneFrame } from "@/features/room/components/RoomSceneFrame";

/** 네이티브: Skia 가 바로 준비돼 있으므로 씬을 직접 그린다. 웹 구현은 RoomSceneLoader.web.tsx 에 있다. */
function RoomSceneLoader() {
  return <RoomSceneFrame>{(width) => <RoomScene width={width} />}</RoomSceneFrame>;
}

export { RoomSceneLoader };
