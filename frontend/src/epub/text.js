/**
 * Text helpers for EPUB click reading.
 *
 * These functions are deliberately independent of EPUB.js and the DOM so the
 * word/sentence heuristics can be tested in Node.
 */

const WORD_CHAR_RE = /[A-Za-z'’\-]/;
const LETTER_RE = /[A-Za-z]/;
const DIGIT_RE = /[0-9]/;
const CLOSERS = new Set(['"', "'", '”', '’', ')', ']']);
const ABBREVIATIONS = new Set([
  'mr',
  'mrs',
  'ms',
  'dr',
  'prof',
  'sr',
  'jr',
  'st',
  'vs',
  'etc',
  'fig',
  'no',
  'vol',
  'ch',
  'pp',
  'e.g',
  'i.e',
]);

function charAt(text, index) {
  return index >= 0 && index < text.length ? text[index] : '';
}

function isWordChar(char) {
  return char !== '' && WORD_CHAR_RE.test(char);
}

function isDigit(char) {
  return char !== '' && DIGIT_RE.test(char);
}

/**
 * Find the English word around a caret offset.
 *
 * Returns null when the offset is on whitespace or punctuation without a
 * nearby letter, so clicks in the margin do not play a random word.
 */
export function extractWordAt(text, offset) {
  if (typeof text !== 'string' || text.length === 0) {
    return null;
  }

  let index = Number.isFinite(offset) ? Math.trunc(offset) : 0;
  index = Math.max(0, Math.min(text.length, index));

  if (!isWordChar(charAt(text, index))) {
    if (index > 0 && isWordChar(charAt(text, index - 1))) {
      index -= 1;
    } else if (isWordChar(charAt(text, index + 1))) {
      index += 1;
    } else {
      return null;
    }
  }

  let start = index;
  while (start > 0 && isWordChar(charAt(text, start - 1))) {
    start -= 1;
  }
  let end = index + 1;
  while (end < text.length && isWordChar(charAt(text, end))) {
    end += 1;
  }

  while (start < end && !LETTER_RE.test(text[start])) {
    start += 1;
  }
  while (end > start && !LETTER_RE.test(text[end - 1])) {
    end -= 1;
  }
  if (start >= end) {
    return null;
  }

  const word = text.slice(start, end);
  return {
    text: word.replace(/’/g, "'"),
    start,
    end,
  };
}

/**
 * Split a block of text into sentence ranges while keeping source offsets.
 *
 * This is a heuristic for click-to-read, not linguistic parsing. Common
 * abbreviations and dotted initials are kept inside the sentence, but unusual
 * punctuation can still produce a shorter sentence.
 */
export function splitSentences(text) {
  if (typeof text !== 'string' || text.length === 0) {
    return [];
  }

  const sentences = [];
  let start = 0;
  let index = 0;

  while (index < text.length) {
    const char = text[index];
    if (char !== '.' && char !== '!' && char !== '?') {
      index += 1;
      continue;
    }

    if (
      char === '.' &&
      isDigit(charAt(text, index - 1)) &&
      isDigit(charAt(text, index + 1))
    ) {
      index += 1;
      continue;
    }

    let end = index + 1;
    while (end < text.length && /[.!?]/.test(text[end])) {
      end += 1;
    }
    while (end < text.length && CLOSERS.has(text[end])) {
      end += 1;
    }

    const next = charAt(text, end);
    if (next !== '' && !/\s/.test(next)) {
      index = end;
      continue;
    }
    if (isAbbreviation(text.slice(start, index))) {
      index = end;
      continue;
    }

    pushSentence(sentences, text, start, end);
    start = end;
    while (start < text.length && /\s/.test(text[start])) {
      start += 1;
    }
    index = start;
  }

  pushSentence(sentences, text, start, text.length);
  return sentences;
}

export function sentenceAtOffset(text, offset) {
  const sentences = splitSentences(text);
  if (sentences.length === 0) {
    return null;
  }

  const index = Number.isFinite(offset)
    ? Math.max(0, Math.min(text.length, Math.trunc(offset)))
    : 0;
  for (const sentence of sentences) {
    if (index >= sentence.start && index <= sentence.end) {
      return sentence;
    }
  }
  return (
    sentences.find((sentence) => sentence.start > index) ??
    sentences[sentences.length - 1]
  );
}

export function cleanText(text) {
  return String(text ?? '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function normalizeHref(href) {
  if (typeof href !== 'string') {
    return '';
  }
  return href.split('#', 1)[0].replace(/^\.\//, '');
}

export function hrefMatches(left, right) {
  const normalizedLeft = normalizeHref(left);
  const normalizedRight = normalizeHref(right);
  if (!normalizedLeft || !normalizedRight) {
    return false;
  }
  if (normalizedLeft === normalizedRight) {
    return true;
  }
  return (
    normalizedLeft.split('/').pop() === normalizedRight.split('/').pop()
  );
}

/** Flatten a nested EPUB.js TOC while retaining indentation depth. */
export function flattenToc(items, depth = 0, result = [], seen = new Set()) {
  if (!Array.isArray(items)) {
    return result;
  }
  for (const item of items) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const href = typeof item.href === 'string' ? item.href : '';
    const rawLabel = typeof item.label === 'string' ? item.label.trim() : '';
    const fallback = href.split('/').pop()?.split('#')[0] || '未命名章节';
    const label = rawLabel || fallback;
    const key = `${href}|${label}|${depth}`;
    if (href && !seen.has(key)) {
      seen.add(key);
      result.push({ href, label, depth });
    }
    if (Array.isArray(item.subitems) && item.subitems.length > 0) {
      flattenToc(item.subitems, depth + 1, result, seen);
    }
  }
  return result;
}

function pushSentence(sentences, text, start, end) {
  let sentenceStart = start;
  let sentenceEnd = end;
  while (sentenceStart < sentenceEnd && /\s/.test(text[sentenceStart])) {
    sentenceStart += 1;
  }
  while (sentenceEnd > sentenceStart && /\s/.test(text[sentenceEnd - 1])) {
    sentenceEnd -= 1;
  }
  if (sentenceStart >= sentenceEnd) {
    return;
  }

  const value = text.slice(sentenceStart, sentenceEnd);
  if (!/[A-Za-z0-9]/.test(value)) {
    return;
  }
  sentences.push({ text: value, start: sentenceStart, end: sentenceEnd });
}

function isAbbreviation(prefix) {
  const match = prefix.match(/([A-Za-z][A-Za-z.]*)\s*$/);
  if (!match) {
    return false;
  }
  const token = match[1].toLowerCase().replace(/\.+$/, '');
  if (ABBREVIATIONS.has(token)) {
    return true;
  }
  return lowerDottedInitials(token);
}

function lowerDottedInitials(token) {
  return /^(?:[a-z]\.)+[a-z]?$/.test(token);
}
