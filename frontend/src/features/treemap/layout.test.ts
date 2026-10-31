import { expect, it } from 'vitest';
import { layoutTreemap } from './layout';

it('preserves area weights and bounds without overlaps', () => {
  const rectangles = layoutTreemap(
    [
      { id: 1, size: 60 },
      { id: 2, size: 30 },
      { id: 3, size: 10 },
      { id: 4, size: 0 },
    ],
    100,
    100,
  );
  expect(rectangles.map((rect) => rect.width * rect.height)).toEqual([
    6000, 3000, 1000,
  ]);
  for (const rect of rectangles) {
    expect(rect.x).toBeGreaterThanOrEqual(0);
    expect(rect.y).toBeGreaterThanOrEqual(0);
    expect(rect.x + rect.width).toBeLessThanOrEqual(100.0001);
    expect(rect.y + rect.height).toBeLessThanOrEqual(100.0001);
  }
  for (let i = 0; i < rectangles.length; i++) {
    for (let j = i + 1; j < rectangles.length; j++) {
      const a = rectangles[i],
        b = rectangles[j];
      const overlap =
        Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x) + 0.0001 &&
        Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y) + 0.0001;
      expect(overlap).toBe(false);
    }
  }
});

it('handles empty, zero, invalid and very wide inputs deterministically', () => {
  expect(layoutTreemap([], 100, 100)).toEqual([]);
  expect(layoutTreemap([{ id: 1, size: 0 }], 100, 100)).toEqual([]);
  expect(layoutTreemap([{ id: 1, size: 1 }], 0, 100)).toEqual([]);
  const input = Array.from({ length: 1000 }, (_, id) => ({ id, size: id + 1 }));
  const result = layoutTreemap(input, 900, 420);
  expect(result).toHaveLength(1000);
  expect(
    result.reduce((sum, rect) => sum + rect.width * rect.height, 0),
  ).toBeCloseTo(378000);
});
