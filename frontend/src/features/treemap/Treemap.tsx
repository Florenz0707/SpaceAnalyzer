import { useEffect, useMemo, useRef, useState } from 'react';
import { bytes, type FileNode } from '../../lib/api';
import { layoutTreemap } from './layout';

interface Props {
  items: FileNode[];
  totalBytes: number;
  omittedBytes: number;
  omittedCount: number;
  selected: number | undefined;
  onSelect: (node: FileNode) => void;
  onOpen: (node: FileNode) => void;
}

function color(node: FileNode | undefined): string {
  if (!node) return '#7e8992';
  if (node.kind === 'directory') return '#456d9a';
  const extension = node.name.split('.').pop()?.toLowerCase();
  if (['zip', '7z', 'rar', 'bin', 'iso'].includes(extension ?? ''))
    return '#9272a3';
  if (['mp4', 'mp3', 'png', 'jpg', 'mkv'].includes(extension ?? ''))
    return '#b57c44';
  return '#398681';
}

export default function Treemap({
  items,
  totalBytes,
  omittedBytes,
  omittedCount,
  selected,
  onSelect,
  onOpen,
}: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(960);
  const [hovered, setHovered] = useState<number>();
  const height = 400;
  const geometry = useMemo(() => {
    const threshold = (totalBytes * 32) / (width * height);
    const visible = items.filter(
      (node) => node.size_bytes > 0 && node.size_bytes >= threshold,
    );
    const small = items.filter(
      (node) => node.size_bytes > 0 && node.size_bytes < threshold,
    );
    const otherBytes =
      omittedBytes + small.reduce((sum, node) => sum + node.size_bytes, 0);
    const weights = visible.map((node) => ({
      id: node.id,
      size: node.size_bytes,
    }));
    if (otherBytes > 0) weights.push({ id: -1, size: otherBytes });
    return {
      rectangles: layoutTreemap(weights, width, height),
      otherBytes,
      otherCount: omittedCount + small.length,
    };
  }, [items, totalBytes, omittedBytes, omittedCount, width]);
  const nodes = useMemo(
    () => new Map(items.map((node) => [node.id, node])),
    [items],
  );
  useEffect(() => {
    const element = canvas.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(1, entries[0].contentRect.width)),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext('2d');
    if (!element || !context) return;
    const started = performance.now();
    const scale = window.devicePixelRatio || 1;
    element.width = Math.round(width * scale);
    element.height = height * scale;
    context.scale(scale, scale);
    context.clearRect(0, 0, width, height);
    for (const rect of geometry.rectangles) {
      const node = nodes.get(rect.id);
      context.fillStyle = color(node);
      context.fillRect(
        rect.x + 1,
        rect.y + 1,
        Math.max(0, rect.width - 2),
        Math.max(0, rect.height - 2),
      );
      if (rect.id === selected || rect.id === hovered) {
        context.strokeStyle = '#163445';
        context.lineWidth = 3;
        context.strokeRect(
          rect.x + 2,
          rect.y + 2,
          Math.max(0, rect.width - 4),
          Math.max(0, rect.height - 4),
        );
      }
      if (rect.width < 70 || rect.height < 34) continue;
      context.save();
      context.beginPath();
      context.rect(rect.x + 8, rect.y + 4, rect.width - 16, rect.height - 8);
      context.clip();
      context.fillStyle = '#fff';
      context.font = '14px "Segoe UI", "Microsoft YaHei", sans-serif';
      context.fillText(
        node
          ? `${node.kind === 'directory' ? '▸ ' : ''}${node.name}`
          : `其他 ${geometry.otherCount} 项`,
        rect.x + 10,
        rect.y + 23,
      );
      if (rect.height > 52) {
        context.font = '12px "Segoe UI", sans-serif';
        context.fillText(
          bytes(node?.size_bytes ?? geometry.otherBytes),
          rect.x + 10,
          rect.y + 44,
        );
      }
      context.restore();
    }
    if (typeof performance.measure === 'function') {
      performance.clearMeasures('treemap-paint');
      performance.measure('treemap-paint', {
        start: started,
        end: performance.now(),
      });
    }
  }, [width, geometry, nodes, selected, hovered]);
  function hit(event: React.MouseEvent<HTMLCanvasElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) * width) / bounds.width;
    const y = ((event.clientY - bounds.top) * height) / bounds.height;
    return geometry.rectangles.find(
      (rect) =>
        x >= rect.x &&
        x < rect.x + rect.width &&
        y >= rect.y &&
        y < rect.y + rect.height,
    );
  }
  const hover =
    hovered === -1
      ? `其他 ${geometry.otherCount} 项，${bytes(geometry.otherBytes)}`
      : nodes.get(hovered ?? 0)?.path;
  return (
    <div className="treemap-frame">
      <canvas
        ref={canvas}
        style={{ height }}
        role="img"
        aria-label="磁盘空间矩形树图，完整内容可在下方列表操作"
        onMouseMove={(event) => setHovered(hit(event)?.id)}
        onMouseLeave={() => setHovered(undefined)}
        onClick={(event) => {
          const node = nodes.get(hit(event)?.id ?? -1);
          if (node) onSelect(node);
        }}
        onDoubleClick={(event) => {
          const node = nodes.get(hit(event)?.id ?? -1);
          if (node?.kind === 'directory') onOpen(node);
        }}
      />
      {geometry.rectangles.length === 0 && (
        <div className="canvas-empty">
          没有可绘制的正大小内容。空目录和零字节文件仍显示在列表中。
        </div>
      )}
      <div className="hover-path" aria-live="polite">
        {hover || '单击查看详情，双击目录进入；也可使用下方列表。'}
      </div>
    </div>
  );
}
