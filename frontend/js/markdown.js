/**
 * AI 답변만 마크다운으로 표시한다. 라이브러리를 불러오지 못한 경우에는 null을 돌려
 * 호출자가 안전한 textContent 표시로 되돌아가게 한다.
 */
export function renderAssistantMarkdown(text) {
  const parser = globalThis.marked;
  const purifier = globalThis.DOMPurify;
  if (typeof parser?.parse !== "function" || typeof purifier?.sanitize !== "function") {
    return null;
  }

  const html = parser.parse(text, { breaks: true, gfm: true });
  return purifier.sanitize(html, { USE_PROFILES: { html: true } });
}
