import { loadData, Skia, type SkImage } from "@shopify/react-native-skia";

/** Skia useImage의 같은 디코더를 쓰되 파일 읽기 실패도 빈 이미지로 처리한다.
 * 페널티 같은 선택 에셋의 실패가 처리되지 않은 Promise 오류로 방까지 가리지 않게 한다.
 */
export async function loadSceneImage(source: number): Promise<SkImage | null> {
  try {
    return await loadData(source, (data) => Skia.Image.MakeImageFromEncoded(data));
  } catch {
    return null;
  }
}
