import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clampScale,
  normalizeBbox,
  toCssBox,
  toPercentBox,
} from '../src/pdf/coordinates.js';

test('toCssBox maps normalized boxes to page pixels', () => {
  const box = toCssBox([0.1, 0.2, 0.5, 0.6], 1000, 500);

  assert.ok(Math.abs(box.left - 100) < 1e-9);
  assert.ok(Math.abs(box.top - 100) < 1e-9);
  assert.ok(Math.abs(box.width - 400) < 1e-9);
  assert.ok(Math.abs(box.height - 200) < 1e-9);
});

test('toCssBox follows page size changes after zoom', () => {
  const atOneX = toCssBox([0.25, 0.5, 0.5, 0.75], 400, 800);
  const atTwoX = toCssBox([0.25, 0.5, 0.5, 0.75], 800, 1600);

  assert.equal(atTwoX.left, atOneX.left * 2);
  assert.equal(atTwoX.top, atOneX.top * 2);
  assert.equal(atTwoX.width, atOneX.width * 2);
  assert.equal(atTwoX.height, atOneX.height * 2);
});

test('toPercentBox produces CSS percentages independent of pixels', () => {
  assert.deepEqual(toPercentBox([0.1, 0.2, 0.5, 0.6]), {
    left: '10.0000%',
    top: '20.0000%',
    width: '40.0000%',
    height: '40.0000%',
  });
});

test('normalizeBbox clamps boxes that slightly exceed the page', () => {
  assert.deepEqual(normalizeBbox([-0.1, 0.2, 1.2, 0.9]), [0, 0.2, 1, 0.9]);
});

test('invalid boxes are rejected instead of silently misaligned', () => {
  assert.throws(() => normalizeBbox([0.1, 0.2, 0.3]), TypeError);
  assert.throws(() => normalizeBbox([0.1, 0.2, Number.NaN, 0.4]), TypeError);
  assert.throws(() => normalizeBbox([0.5, 0.5, 0.5, 0.8]), RangeError);
  assert.throws(() => toCssBox([0.1, 0.2, 0.3, 0.4], 0, 500), RangeError);
});

test('clampScale keeps zoom within usable bounds', () => {
  assert.equal(clampScale(0.1), 0.4);
  assert.equal(clampScale(10), 3);
  assert.equal(clampScale(1.25), 1.25);
  assert.equal(clampScale(Number.NaN), 0.4);
});
