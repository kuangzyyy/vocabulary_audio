import assert from 'node:assert/strict';
import test from 'node:test';

import {
  accentLabel,
  accentOptions,
  sourceLicenseText,
} from '../src/audio/audioMeta.js';

test('both available accents produce a real US/UK choice', () => {
  const options = accentOptions({ available_accents: ['us', 'uk'] });

  assert.deepEqual(options.available, ['us', 'uk']);
  assert.equal(options.canChoose, true);
});

test('a single accent does not fabricate a second choice', () => {
  const options = accentOptions({ available_accents: ['us'] });

  assert.deepEqual(options.available, ['us']);
  assert.equal(options.canChoose, false);
});

test('unknown accent is shown as unlabeled, not as US or UK', () => {
  const options = accentOptions({ available_accents: ['unknown'] });

  assert.deepEqual(options.available, ['unknown']);
  assert.equal(options.canChoose, false);
  assert.equal(accentLabel('unknown'), '口音未标注');
});

test('unsupported and duplicate accents are filtered out', () => {
  const options = accentOptions({ available_accents: ['us', 'de', 'us', 'uk'] });

  assert.deepEqual(options.available, ['us', 'uk']);
  assert.equal(accentLabel('de'), '口音未标注');
});

test('missing accent metadata is safe', () => {
  const options = accentOptions(undefined);

  assert.deepEqual(options.available, []);
  assert.equal(options.canChoose, false);
});

test('license and attribution text is assembled for display', () => {
  assert.equal(
    sourceLicenseText({ license: 'CC BY-SA 3.0', attribution: 'Tester' }),
    'CC BY-SA 3.0 · Tester',
  );
  assert.equal(sourceLicenseText({ license: 'Public domain' }), 'Public domain');
  assert.equal(sourceLicenseText(null), '');
});
