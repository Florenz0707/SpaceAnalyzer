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

it('opens the partial snapshot when cancellation immediately returns a terminal job', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
    () => null,
  );
  let cancelled = false;
  const partial = {
    ...snapshot,
    status: 'cancelled',
    total_bytes: 0,
    file_count: 0,
  };
  const job = {
    ...snapshot,
    id: 'j1',
    snapshot_id: 's1',
    status: 'running',
    failure_message: null,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      let body: object;
      if (url.endsWith('/scans/j1/cancel')) {
        cancelled = true;
        body = { ...job, status: 'cancelled' };
      } else if (url === '/api/scans' && init?.method === 'POST') body = job;
      else if (url === '/api/scans/j1')
        body = { ...job, status: cancelled ? 'cancelled' : 'running' };
      else if (url === '/api/snapshots/s1') body = partial;
      else if (url.includes('/nodes/1/children'))
        body = { ...page([]), total_bytes: 0, returned_bytes: 0 };
      else
        body = {
          items: cancelled ? [partial] : [],
          total: cancelled ? 1 : 0,
          offset: 0,
          limit: 50,
        };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  render(<App />);
  await screen.findByText('还没有快照。输入目录开始扫描。');
  fireEvent.change(screen.getByLabelText('扫描目录或盘符'), {
    target: { value: 'D:\\fixture' },
  });
  fireEvent.click(screen.getByRole('button', { name: '创建快照' }));
  fireEvent.click(await screen.findByRole('button', { name: '取消扫描' }));
  expect(await screen.findByText(/部分快照：已取消/)).toBeTruthy();
  expect(
    screen.getByRole('button', { name: /D:\\fixture.*已取消/ }),
  ).toBeTruthy();
});

it('continues polling when cancellation is acknowledged before it finishes', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
    () => null,
  );
  let cancellationRequested = false;
  const partial = { ...snapshot, status: 'cancelled' };
  const job = {
    ...snapshot,
    id: 'j1',
    snapshot_id: 's1',
    status: 'running',
    failure_message: null,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      let body: object;
      if (url.endsWith('/scans/j1/cancel')) {
        cancellationRequested = true;
        body = job;
      } else if (url === '/api/scans' && init?.method === 'POST') body = job;
      else if (url === '/api/scans/j1')
        body = {
          ...job,
          status: cancellationRequested ? 'cancelled' : 'running',
        };
      else if (url === '/api/snapshots/s1') body = partial;
      else if (url.includes('/nodes/1/children')) body = page([directory]);
      else
        body = {
          items: cancellationRequested ? [partial] : [],
          total: cancellationRequested ? 1 : 0,
          offset: 0,
          limit: 50,
        };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  render(<App />);
  await screen.findByText('还没有快照。输入目录开始扫描。');
  fireEvent.change(screen.getByLabelText('扫描目录或盘符'), {
    target: { value: 'D:\\fixture' },
  });
  fireEvent.click(screen.getByRole('button', { name: '创建快照' }));
  fireEvent.click(await screen.findByRole('button', { name: '取消扫描' }));
  expect(await screen.findByText(/部分快照：已取消/)).toBeTruthy();
});

it('keeps a scan active and shows the error when cancellation fails', async () => {
  const job = {
    ...snapshot,
    id: 'j1',
    snapshot_id: 's1',
    status: 'running',
    failure_message: null,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/cancel'))
        return new Response(JSON.stringify({ detail: 'cancel denied' }), {
          status: 409,
        });
      const body = url.includes('/scans')
        ? job
        : { items: [], total: 0, offset: 0, limit: 50 };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  render(<App />);
  await screen.findByText('还没有快照。输入目录开始扫描。');
  fireEvent.change(screen.getByLabelText('扫描目录或盘符'), {
    target: { value: 'D:\\fixture' },
  });
  fireEvent.click(screen.getByRole('button', { name: '创建快照' }));
  fireEvent.click(await screen.findByRole('button', { name: '取消扫描' }));
  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    expect.stringContaining('cancel denied'),
  );
  expect(screen.getByRole('button', { name: '取消扫描' })).toBeTruthy();
  expect(screen.queryByText('已取消')).toBeNull();
});

it.each([true, false])(
  'recovers a disconnected scan when retry returns terminal=%s',
  async (terminalOnRetry) => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
      () => null,
    );
    const job = {
      ...snapshot,
      id: 'j1',
      snapshot_id: 's1',
      status: 'running',
      failure_message: null,
    };
    let retrying = false;
    let retriedOnce = false;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        let body: object;
        if (url === '/api/scans' && init?.method === 'POST') body = job;
        else if (url === '/api/scans/j1') {
          if (!retrying) throw new Error('progress offline');
          body = {
            ...job,
            status: terminalOnRetry || retriedOnce ? 'completed' : 'running',
          };
          retriedOnce = true;
        } else if (url === '/api/snapshots/s1') body = snapshot;
        else if (url.includes('/nodes/1/children')) body = page([directory]);
        else
          body = {
            items: retrying ? [snapshot] : [],
            total: retrying ? 1 : 0,
            offset: 0,
            limit: 50,
          };
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );
    render(<App />);
    await screen.findByText('还没有快照。输入目录开始扫描。');
    fireEvent.change(screen.getByLabelText('扫描目录或盘符'), {
      target: { value: 'D:\\fixture' },
    });
    fireEvent.click(screen.getByRole('button', { name: '创建快照' }));
    expect(await screen.findByRole('alert')).toHaveProperty(
      'textContent',
      expect.stringContaining('progress offline'),
    );
    retrying = true;
    fireEvent.click(screen.getByRole('button', { name: '重试连接' }));
    expect(
      await screen.findByRole('heading', { name: '逻辑大小 10 B' }),
    ).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  },
);
