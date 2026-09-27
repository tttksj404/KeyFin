import { loadData } from "@shopify/react-native-skia";
import { loadSceneImage } from "@/features/room/sceneImages";

jest.mock("@shopify/react-native-skia", () => ({ loadData: jest.fn(), Skia: { Image: { MakeImageFromEncoded: jest.fn() } } }));

it("선택 이미지의 파일 읽기 실패와 디코딩 실패는 빈 이미지로 끝난다", async () => {
  jest.mocked(loadData).mockRejectedValueOnce(new Error("asset unavailable")).mockResolvedValueOnce(null);
  await expect(loadSceneImage(1)).resolves.toBeNull();
  await expect(loadSceneImage(2)).resolves.toBeNull();
});
