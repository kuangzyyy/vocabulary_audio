/**
 * Coordinate conversion helpers.
 *
 * The backend only sends normalized boxes [x0, y0, x1, y1] in the range 0..1,
 * with the origin at the top-left of the rendered page. These helpers are the
 * only place where screen pixels are derived from those numbers.
 */

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

export function normalizeBbox(bbox) {
  if (!Array.isArray(bbox) || bbox.length !== 4) {
    throw new TypeError('bbox 必须是 [x0, y0, x1, y1] 四个数字');
  }
  const values = bbox.map(Number);
  if (!values.every(Number.isFinite)) {
    throw new TypeError('bbox 包含非数字值');
  }
  const [x0, y0, x1, y1] = values.map(clamp01);
  if (x1 <= x0 || y1 <= y0) {
    throw new RangeError('bbox 的宽高必须大于 0');
  }
  return [x0, y0, x1, y1];
}

export function toCssBox(bbox, width, height) {
  if (!(width > 0) || !(height > 0)) {
    throw new RangeError('页面宽高必须大于 0');
  }
  const [x0, y0, x1, y1] = normalizeBbox(bbox);
  return {
    left: x0 * width,
    top: y0 * height,
    width: (x1 - x0) * width,
    height: (y1 - y0) * height,
  };
}

export function toPercentBox(bbox) {
  const [x0, y0, x1, y1] = normalizeBbox(bbox);
  return {
    left: `${(x0 * 100).toFixed(4)}%`,
    top: `${(y0 * 100).toFixed(4)}%`,
    width: `${((x1 - x0) * 100).toFixed(4)}%`,
    height: `${((y1 - y0) * 100).toFixed(4)}%`,
  };
}

export function clampScale(value, min = 0.4, max = 3) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, value));
}
