/** 백엔드 응답이 OpenAPI 계약과 다를 때 화면 모델 변환 단계에서 던진다. 클라이언트에서 우회하지 않고 불일치를 보고한다. */
export class ContractMismatchError extends Error {
  constructor(field: string) {
    super(`백엔드 계약 불일치: ${field}`);
    this.name = "ContractMismatchError";
  }
}
