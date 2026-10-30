import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';

const snapshot = {
  id: 's1',
  job_id: 'j1',
  root_path: 'D:\\fixture',
  root_node_id: 1,
  status: 'completed',
  created_at: '2026-10-30T00:00:00Z',
  ended_at: '2026-10-30T00:00:01Z',
  total_bytes: 10,
  file_count: 1,
  directory_count: 2,
  error_count: 0,
  skipped_count: 0,
  metric: 'logical',
  policy_version: 1,
};
const directory = {
  id: 2,
  parent_id: 1,
  snapshot_id: 's1',
  name: 'nested',
  path: 'D:\\fixture\\nested',
  kind: 'directory',
  size_bytes: 10,
  modified_ns: 0,
  readable: true,
};
const file = {
  ...directory,
  id: 3,
  parent_id: 2,
  name: 'inside.bin',
  kind: 'file',
};
const page = (items: object[]) => ({
  items,
  total: items.length,
  offset: 0,
  limit: 200,
  total_bytes: 10,
  returned_bytes: 10,
  omitted_bytes: 0,
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, '', '/');
});

it('opens a saved snapshot, navigates directories and exposes read-only details', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
    () => null,
  );
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      let body: object;
      if (url.includes('/nodes/2/children')) body = page([file]);
      else if (url.includes('/nodes/1/children')) body = page([directory]);
      else if (url === '/api/snapshots/s1') body = snapshot;
      else body = { items: [snapshot], total: 1, offset: 0, limit: 50 };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  render(<App />);
  expect(screen.getByText('不修改、移动或删除被分析的文件')).toBeTruthy();
  fireEvent.click(
    await screen.findByRole('button', { name: /D:\\fixture.*10 B/ }),
  );
  fireEvent.click(await screen.findByRole('button', { name: '▸ nested' }));
  fireEvent.click(await screen.findByRole('button', { name: 'inside.bin' }));
  expect(screen.getByText(/当前目录 100.00%/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'D:\\fixture' }));
  expect(await screen.findByRole('button', { name: '▸ nested' })).toBeTruthy();
});

it('reports backend disconnection and can retry loading history', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('offline'));
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    expect.stringContaining('offline'),
  );
  fetch.mockResolvedValue(
    new Response(JSON.stringify({ items: [], total: 0, offset: 0, limit: 50 })),
  );
  fireEvent.click(screen.getByRole('button', { name: '重试连接' }));
  await waitFor(() =>
    expect(screen.getByText('还没有快照。输入目录开始扫描。')).toBeTruthy(),
  );
});
