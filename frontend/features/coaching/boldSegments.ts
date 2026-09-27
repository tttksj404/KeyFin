export type TextSegment = { text: string; bold: boolean };

const BOLD = /\*\*([^*]+?)\*\*/g;

/**
 * 코치 답변의 `**…**`(서버가 제안 문장에 붙이는 굵게 표시)만 해석한다. 마크다운 라이브러리 없이
 * 굵게 조각과 일반 조각으로 나누며, 짝이 맞지 않는 `**`는 글자 그대로 둔다.
 */
export function boldSegments(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(BOLD)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ text: text.slice(last, start), bold: false });
    segments.push({ text: match[1], bold: true });
    last = start + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), bold: false });
  return segments;
}
