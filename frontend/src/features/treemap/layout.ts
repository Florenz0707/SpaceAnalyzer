export interface Weight {
  id: number;
  size: number;
}
export interface Rectangle {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Balanced binary treemap; area is proportional to positive finite weight. */
export function layoutTreemap(
  input: Weight[],
  width: number,
  height: number,
): Rectangle[] {
  if (!(
    width > 0 &&
    height > 0 &&
    Number.isFinite(width) &&
    Number.isFinite(height)
  ))
    return [];
  const started = performance.now();
  const items = input
    .filter((item) => item.size > 0 && Number.isFinite(item.size))
    .sort((a, b) => b.size - a.size || a.id - b.id);
  if (!items.length) return [];
  const prefix = [0];
  for (const item of items) prefix.push(prefix[prefix.length - 1] + item.size);
  const pending = [{ start: 0, end: items.length, x: 0, y: 0, width, height }];
  const result: Rectangle[] = [];
  while (pending.length) {
    const box = pending.pop()!;
    const { start, end } = box;
    if (end - start === 1) {
      result.push({ ...box, id: items[start].id });
      continue;
    }
    const sum = prefix[end] - prefix[start];
    const middle = prefix[start] + sum / 2;
    let split = start + 1;
    while (split < end - 1 && prefix[split] < middle) split++;
    if (
      split > start + 1 &&
      Math.abs(prefix[split - 1] - middle) < Math.abs(prefix[split] - middle)
    )
      split--;
    const ratio = (prefix[split] - prefix[start]) / sum;
    if (box.width >= box.height) {
      const first = box.width * ratio;
      pending.push({
        ...box,
        start: split,
        x: box.x + first,
        width: box.width - first,
      });
      pending.push({ ...box, end: split, width: first });
    } else {
      const first = box.height * ratio;
      pending.push({
        ...box,
        start: split,
        y: box.y + first,
        height: box.height - first,
      });
      pending.push({ ...box, end: split, height: first });
    }
  }
  if (typeof performance.measure === 'function') {
    performance.clearMeasures('treemap-layout');
    performance.measure('treemap-layout', {
      start: started,
      end: performance.now(),
    });
  }
  return result;
}
