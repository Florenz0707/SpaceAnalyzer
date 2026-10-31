import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import ChatPanel from './ChatPanel';

class Stream {
  static all: Stream[] = [];
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  onopen: (() => void) | null = null;
  close = vi.fn();
  constructor() {
    Stream.all.push(this);
  }
  emit(data: object) {
    this.onmessage?.(
      new MessageEvent('message', { data: JSON.stringify(data) }),
    );
  }
}
const model = { key: 'cloud', provider: 'deepseek_api', model_id: 'fixture' };
const conversation = {
  id: 'c1',
  snapshot_id: 's1',
  model_key: 'cloud',
  allow_cloud: true,
};
const run = {
  id: 'r1',
  conversation_id: 'c1',
  question: '分析',
  status: 'queued',
  text: '',
  evidence: [],
  usage: {},
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  Stream.all = [];
});

it('shows missing configuration without making a model request', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => ({
      ok: true,
      json: async () =>
        input === '/api/models' ? { items: [], diagnostics: [] } : [],
    })),
  );
  render(
    <ChatPanel
      snapshot={{ id: 's1', status: 'completed' }}
      onClose={() => {}}
      onLocate={() => {}}
    />,
  );
  expect(await screen.findByText(/尚未配置模型/)).toBeTruthy();
  expect(screen.getByRole('button', { name: '发送问题' })).toHaveProperty(
    'disabled',
    true,
  );
});

it('requires cloud consent and displays streamed answer and evidence navigation', async () => {
  const locate = vi.fn();
  const calls: object[] = [];
  const evidence = [
    {
      id: 'E1',
      query: 'largest_files',
      snapshot_id: 's1',
      data: { items: [{ id: 2, name: 'fixture.bin', size_bytes: 3 }] },
    },
  ];
  vi.stubGlobal('EventSource', Stream);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, options?: RequestInit) => {
      let data: unknown = [];
      if (input === '/api/models') data = { items: [model], diagnostics: [] };
      else if (input === '/api/conversations' && options?.body) {
        calls.push(JSON.parse(String(options.body)));
        data = conversation;
      } else if (input === '/api/conversations/c1/runs' && options?.body)
        data = run;
      else if (input === '/api/runs/r1')
        data = { ...run, status: 'completed', text: '检查 [E1]', evidence };
      return { ok: true, json: async () => data };
    }),
  );
  render(
    <ChatPanel
      snapshot={{ id: 's1', status: 'completed' }}
      onClose={() => {}}
      onLocate={locate}
    />,
  );
  await screen.findByRole('option', { name: /fixture/ });
  fireEvent.change(screen.getByLabelText('问题'), {
    target: { value: '分析' },
  });
  expect(screen.getByRole('button', { name: '发送问题' })).toHaveProperty(
    'disabled',
    true,
  );
  fireEvent.click(screen.getByLabelText(/同意将问题/));
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }));
  await waitFor(() => expect(Stream.all.length).toBe(1));
  act(() =>
    Stream.all[0].emit({
      run_id: 'r1',
      sequence: 1,
      kind: 'text',
      data: { text: '检查 [E1]' },
    }),
  );
  expect(await screen.findByText('检查', { exact: false })).toBeTruthy();
  act(() =>
    Stream.all[0].emit({
      run_id: 'r1',
      sequence: 2,
      kind: 'terminal',
      data: { status: 'completed' },
    }),
  );
  fireEvent.click(
    await screen.findByRole('button', { name: /定位 fixture.bin/ }),
  );
  expect(locate).toHaveBeenCalledWith(2);
  expect(screen.queryByText(/"size_bytes"/)).toBeNull();
  expect(calls[0]).toHaveProperty('allow_cloud', true);
  expect(Stream.all[0].close).toHaveBeenCalled();
});

it('keeps a run active after cancellation fails and deduplicates replayed deltas', async () => {
  vi.stubGlobal('EventSource', Stream);
  const saved = { ...run, status: 'running', text: '已保存' };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, options?: RequestInit) => {
      if (input === '/api/runs/r1/cancel')
        return { ok: false, json: async () => ({ detail: '取消请求失败' }) };
      const data =
        input === '/api/models'
          ? {
              items: [{ ...model, key: 'local', provider: 'ollama' }],
              diagnostics: [],
            }
          : input.startsWith('/api/conversations?')
            ? [{ ...conversation, model_key: 'local' }]
            : input === '/api/conversations/c1/runs' && !options
              ? [saved]
              : saved;
      return { ok: true, json: async () => data };
    }),
  );
  render(
    <ChatPanel
      snapshot={{ id: 's1', status: 'cancelled' }}
      onClose={() => {}}
      onLocate={() => {}}
    />,
  );
  await waitFor(() => expect(Stream.all.length).toBe(1));
  const delta = {
    run_id: 'r1',
    sequence: 1,
    kind: 'text',
    data: { text: '已保存' },
  };
  act(() => {
    Stream.all[0].emit(delta);
    Stream.all[0].emit(delta);
  });
  expect(screen.getByText('已保存')).toBeTruthy();
  expect(screen.queryByText('已保存已保存')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '取消生成' }));
  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    expect.stringContaining('取消请求失败'),
  );
  expect(screen.getByRole('button', { name: '取消生成' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '发送问题' })).toHaveProperty(
    'disabled',
    true,
  );
});
