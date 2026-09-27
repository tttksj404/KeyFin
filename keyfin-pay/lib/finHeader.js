const pad2 = (n) => String(n).padStart(2, '0');

export function buildFinBody({ url, fields = {}, apiKey, userKey, now = new Date() }) {
  // member API(계정 생성/조회)는 공통 Header 없이 apiKey를 본문에 직접 넣는 규격
  if (url.endsWith('/member') || url.endsWith('/member/search')) {
    return { ...fields, apiKey };
  }
  const apiName = new URL(url).pathname.split('/').filter(Boolean).pop();
  const date = `${now.getFullYear()}${pad2(now.getMonth() + 1)}${pad2(now.getDate())}`;
  const time = `${pad2(now.getHours())}${pad2(now.getMinutes())}${pad2(now.getSeconds())}`;
  const header = {
    apiName,
    transmissionDate: date,
    transmissionTime: time,
    institutionCode: '00100',
    fintechAppNo: '001',
    apiServiceCode: apiName,
    institutionTransactionUniqueNo: date + time + String(Math.floor(Math.random() * 1_000_000)).padStart(6, '0'),
    apiKey,
  };
  if (userKey) header.userKey = userKey;
  return { Header: header, ...fields };
}
