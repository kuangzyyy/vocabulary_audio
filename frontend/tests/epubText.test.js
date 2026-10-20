import test from 'node:test';
import assert from 'node:assert/strict';

import {
  cleanText,
  extractWordAt,
  flattenToc,
  hrefMatches,
  normalizeHref,
  sentenceAtOffset,
  splitSentences,
} from '../src/epub/text.js';

test('extractWordAt finds the word under a caret offset', () => {
  const text = 'The quick brown fox.';
  assert.deepEqual(extractWordAt(text, 6), {
    text: 'quick',
    start: 4,
    end: 9,
  });
  assert.deepEqual(extractWordAt(text, 9), {
    text: 'quick',
    start: 4,
    end: 9,
  });
});

test('extractWordAt handles apostrophes, hyphens and curly quotes', () => {
  const text = 'A well-known writer’s “story” ends.';
  assert.equal(extractWordAt(text, 3).text, 'well-known');
  assert.equal(extractWordAt(text, 19).text, "writer's");
  assert.equal(extractWordAt(text, 25).text, 'story');
});

test('extractWordAt handles whitespace and punctuation boundaries', () => {
  assert.equal(extractWordAt('Hello world', 5).text, 'Hello');
  assert.equal(extractWordAt('Hello ... world', 7), null);
  assert.equal(extractWordAt('', 0), null);
});

test('splitSentences returns source offsets and text', () => {
  const text = 'Hello world. This is a test! Is it?';
  const sentences = splitSentences(text);
  assert.deepEqual(
    sentences.map((sentence) => sentence.text),
    ['Hello world.', 'This is a test!', 'Is it?'],
  );
  assert.equal(sentences[0].start, 0);
  assert.equal(sentences[0].end, 12);
  assert.equal(text.slice(sentences[1].start, sentences[1].end), 'This is a test!');
});

test('splitSentences keeps common abbreviations inside a sentence', () => {
  const text = 'Dr. Smith arrived. He met Prof. Jones in the U.S. today.';
  assert.deepEqual(
    splitSentences(text).map((sentence) => sentence.text),
    ['Dr. Smith arrived.', 'He met Prof. Jones in the U.S. today.'],
  );
});

test('splitSentences does not split decimal numbers', () => {
  const text = 'Pi is 3.14 and e is 2.71. That is all.';
  assert.deepEqual(
    splitSentences(text).map((sentence) => sentence.text),
    ['Pi is 3.14 and e is 2.71.', 'That is all.'],
  );
});

test('splitSentences handles closing quotes and no punctuation', () => {
  assert.deepEqual(
    splitSentences('“Go now.” Then wait.').map((sentence) => sentence.text),
    ['“Go now.”', 'Then wait.'],
  );
  assert.deepEqual(
    splitSentences('A paragraph without a period').map((sentence) => sentence.text),
    ['A paragraph without a period'],
  );
});

test('sentenceAtOffset returns the sentence containing the offset', () => {
  const text = 'One sentence. Two sentence! Three?';
  assert.equal(sentenceAtOffset(text, 3).text, 'One sentence.');
  assert.equal(sentenceAtOffset(text, 23).text, 'Two sentence!');
  assert.equal(sentenceAtOffset(text, 999).text, 'Three?');
  assert.equal(sentenceAtOffset('', 0), null);
});

test('cleanText collapses whitespace for playback', () => {
  assert.equal(cleanText('  Hello\n\n world\tagain  '), 'Hello world again');
});

test('normalizeHref ignores fragments and leading dot slash', () => {
  assert.equal(normalizeHref('./chapter1.xhtml#section-2'), 'chapter1.xhtml');
  assert.equal(normalizeHref('chapter2.xhtml'), 'chapter2.xhtml');
  assert.equal(normalizeHref(null), '');
});

test('hrefMatches tolerates OPF-relative paths and fragments', () => {
  assert.equal(
    hrefMatches('OEBPS/chapter1.xhtml#part', './chapter1.xhtml'),
    true,
  );
  assert.equal(hrefMatches('chapter1.xhtml', 'chapter2.xhtml'), false);
  assert.equal(hrefMatches('', 'chapter1.xhtml'), false);
});

test('flattenToc preserves order and nesting depth', () => {
  const toc = [
    {
      href: 'chapter1.xhtml',
      label: 'Chapter 1',
      subitems: [{ href: 'chapter1.xhtml#part', label: 'Part 1' }],
    },
    { href: 'chapter2.xhtml', label: 'Chapter 2' },
  ];
  assert.deepEqual(flattenToc(toc), [
    { href: 'chapter1.xhtml', label: 'Chapter 1', depth: 0 },
    { href: 'chapter1.xhtml#part', label: 'Part 1', depth: 1 },
    { href: 'chapter2.xhtml', label: 'Chapter 2', depth: 0 },
  ]);
});
