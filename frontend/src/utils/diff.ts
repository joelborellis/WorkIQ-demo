/**
 * Word-level diff utilities for comparing AI responses side-by-side.
 */

function tokenizeWords(text: string): string[] {
  return text.toLowerCase().match(/\b[a-z0-9']+\b/g) ?? [];
}

export function buildWordSet(text: string): Set<string> {
  return new Set(tokenizeWords(text));
}

/** Jaccard similarity between two word sets, returns 0–1. */
export function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 1;
  let shared = 0;
  for (const w of a) if (b.has(w)) shared++;
  const union = a.size + b.size - shared;
  return union === 0 ? 1 : shared / union;
}

/**
 * Words that appear in `text` but NOT in any of `otherTexts`.
 * Used to highlight what's unique to each route's response.
 */
export function getUniqueWords(text: string, otherTexts: string[]): Set<string> {
  const mine = buildWordSet(text);
  const others = new Set<string>();
  for (const t of otherTexts) {
    for (const w of buildWordSet(t)) others.add(w);
  }
  return new Set([...mine].filter(w => !others.has(w)));
}

export interface Token {
  type: 'word' | 'gap';
  value: string;
}

/**
 * Splits text into alternating word/gap tokens preserving all whitespace
 * and punctuation so the rendered output is visually identical to the input.
 */
export function splitIntoTokens(text: string): Token[] {
  const parts = text.match(/[a-z0-9']+|[^a-z0-9']+/gi);
  if (!parts) return [];
  return parts.map(p => ({
    type: /^[a-z0-9']+$/i.test(p) ? 'word' : 'gap',
    value: p,
  }));
}
