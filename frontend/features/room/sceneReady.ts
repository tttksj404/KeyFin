import * as React from "react";

/**
 * "방을 다 그렸다"를 RoomScene 에서 RoomView 를 쓰는 화면으로 올리는 통로.
 * 그림이 다 읽혔는지는 RoomScene 만 아는데(useSceneImages), 그 위로 RoomSceneLoader(네이티브·웹 두 벌)·RoomView 가 끼어 있어
 * prop 으로 내리면 세 파일을 다 거쳐야 한다. 전역 스토어에 두지 않는 이유: 홈과 방 꾸미기가 각자 씬을 하나씩 띄우므로
 * 값이 하나면 방 꾸미기를 닫을 때 홈의 상태까지 되돌아간다. 컨텍스트는 자기 RoomView 아래 씬의 신호만 듣는다.
 */
const SceneReadyContext = React.createContext<(() => void) | null>(null);

export const SceneReadyProvider = SceneReadyContext.Provider;

/** 방을 처음 보여 줄 수 있게 됐을 때 한 번 알린다. 듣는 쪽이 없으면(방 꾸미기) 아무 일도 없다 */
export function useNotifySceneReady(ready: boolean): void {
  const notify = React.useContext(SceneReadyContext);
  React.useEffect(() => {
    if (ready) notify?.();
  }, [ready, notify]);
}
