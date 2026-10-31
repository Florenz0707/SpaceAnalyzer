import { useEffect, useRef, useState, type FormEvent } from 'react';
import { bytes, request, type Snapshot } from '../../lib/api';
import {
  running,
  runStatus,
  type AnalysisRun,
  type Conversation,
  type Evidence,
  type ModelInfo,
  type RunEvent,
} from './api';

interface Props {
  snapshot: Pick<Snapshot, 'id' | 'status'>;
  onClose: () => void;
  onLocate: (nodeId: number) => void;
}
const labels: Record<string, string> = {
  overview: '快照总览',
  children: '根目录分布',
  largest_files: '最大文件',
  extensions: '文件类型',
  errors: '遗漏记录',
};

function EvidenceCard({
  runId,
  evidence,
  onLocate,
}: {
  runId: string;
  evidence: Evidence;
  onLocate: Props['onLocate'];
}) {
  const items = Array.isArray(evidence.data.items)
    ? (evidence.data.items as Record<string, unknown>[])
    : [];
  return (
    <details id={`${runId}-${evidence.id}`} className="evidence-card">
      <summary>
        {evidence.id} · {labels[evidence.query] || evidence.query}
      </summary>
      {items.map(
        (item) =>
          typeof item.id === 'number' && (
            <button
              key={item.id}
              type="button"
              className="text-button"
              onClick={() => onLocate(item.id as number)}
            >
              定位 {String(item.name || `节点 ${item.id}`)} ·{' '}
              {bytes(Number(item.size_bytes) || 0)}
            </button>
          ),
      )}
      <pre>{JSON.stringify(evidence.data, null, 2)}</pre>
    </details>
  );
}

export default function ChatPanel({ snapshot, onClose, onLocate }: Props) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [diagnostics, setDiagnostics] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [modelKey, setModelKey] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState<Conversation>();
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [question, setQuestion] = useState('');
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [connection, setConnection] = useState('');
  const [retry, setRetry] = useState(0);
  const [loadRetry, setLoadRetry] = useState(0);
  const cursors = useRef(new Map<string, number>());
  const buffers = useRef(new Map<string, string>());
  const requestKey = useRef<
    { conversation: string; question: string; key: string } | undefined
  >(undefined);
  const activeId = runs.find(running)?.id;
  const model = models.find((item) => item.key === modelKey);
  const cloud = model?.provider === 'deepseek_api';

  useEffect(() => {
    let disposed = false;
    const timer = setTimeout(() => {
      void Promise.all([
        request<{ items: ModelInfo[]; diagnostics: string[] }>('/models'),
        request<Conversation[]>(`/conversations?snapshot_id=${snapshot.id}`),
      ])
        .then(async ([catalog, history]) => {
          if (disposed) return;
          setModels(catalog.items);
          setDiagnostics(catalog.diagnostics);
          setConversations(history);
          setModelKey(catalog.items[0]?.key || '');
          setLoaded(true);
          const previous = history[0];
          if (previous) {
            const records = await request<AnalysisRun[]>(
              `/conversations/${previous.id}/runs`,
            );
            if (disposed) return;
            setConversation(previous);
            setModelKey(previous.model_key);
            setConsent(previous.allow_cloud);
            setRuns(records);
          }
        })
        .catch((cause: Error) => {
          if (!disposed) {
            setError(cause.message);
            setLoaded(true);
          }
        });
    }, 0);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [snapshot.id, loadRetry]);

  useEffect(() => {
    if (!activeId) return;
    let disposed = false;
    const source = new EventSource(
      `/api/runs/${activeId}/events?after=${cursors.current.get(activeId) || 0}`,
    );
    source.onopen = () => setConnection('');
    source.onerror = () =>
      setConnection('连接中断，正在重新连接；不会重复生成。');
    source.onmessage = (message) => {
      let event: RunEvent;
      try {
        event = JSON.parse(message.data) as RunEvent;
      } catch {
        setConnection('事件解析失败，请重新连接。');
        return;
      }
      if (
        event.run_id !== activeId ||
        event.sequence <= (cursors.current.get(activeId) || 0)
      )
        return;
      cursors.current.set(activeId, event.sequence);
      if (event.kind === 'status' && event.data.status)
        setRuns((current) =>
          current.map((run) =>
            run.id === activeId ? { ...run, status: event.data.status! } : run,
          ),
        );
      if (event.kind === 'text') {
        const text =
          (buffers.current.get(activeId) || '') + (event.data.text || '');
        buffers.current.set(activeId, text);
        setRuns((current) =>
          current.map((run) => (run.id === activeId ? { ...run, text } : run)),
        );
      }
      if (event.kind === 'evidence')
        setRuns((current) =>
          current.map((run) =>
            run.id === activeId
              ? { ...run, evidence: event.data.evidence || [] }
              : run,
          ),
        );
      if (event.kind === 'terminal') {
        source.close();
        void request<AnalysisRun>(`/runs/${activeId}`)
          .then((result) => {
            if (!disposed) {
              setRuns((current) =>
                current.map((run) => (run.id === activeId ? result : run)),
              );
              setConnection('');
            }
          })
          .catch((cause: Error) => {
            if (!disposed) setError(cause.message);
          });
      }
    };
    return () => {
      disposed = true;
      source.close();
    };
  }, [activeId, retry]);

  async function selectConversation(id: string) {
    setError('');
    setPending(true);
    try {
      const selected = conversations.find((item) => item.id === id);
      if (!selected) {
        setConversation(undefined);
        setRuns([]);
        setConsent(false);
        return;
      }
      const records = await request<AnalysisRun[]>(`/conversations/${id}/runs`);
      setConversation(selected);
      setModelKey(selected.model_key);
      setConsent(selected.allow_cloud);
      setRuns(records);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setPending(false);
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    setError('');
    setPending(true);
    try {
      let selected = conversation;
      if (!selected) {
        selected = await request<Conversation>('/conversations', {
          snapshot_id: snapshot.id,
          model_key: modelKey,
          allow_cloud: consent,
        });
        setConversation(selected);
        setConversations((current) => [selected!, ...current]);
      }
      const previous = requestKey.current;
      const key =
        previous?.conversation === selected.id && previous.question === question
          ? previous.key
          : crypto.randomUUID();
      requestKey.current = { conversation: selected.id, question, key };
      const result = await request<AnalysisRun>(
        `/conversations/${selected.id}/runs`,
        { question, request_key: key },
      );
      setRuns((current) =>
        current.some((item) => item.id === result.id)
          ? current
          : [...current, result],
      );
      setQuestion('');
      requestKey.current = undefined;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setPending(false);
    }
  }

  async function reconnect() {
    setError('');
    if (!activeId) {
      setLoadRetry((value) => value + 1);
      return;
    }
    try {
      const result = await request<AnalysisRun>(`/runs/${activeId}`);
      setRuns((current) =>
        current.map((item) => (item.id === activeId ? result : item)),
      );
      setRetry((value) => value + 1);
    } catch (cause) {
      setError(String(cause));
    }
  }

  async function cancel() {
    if (!activeId) return;
    setPending(true);
    setError('');
    try {
      const result = await request<AnalysisRun>(`/runs/${activeId}/cancel`, {});
      setRuns((current) =>
        current.map((item) => (item.id === activeId ? result : item)),
      );
    } catch (cause) {
      setError(String(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <aside className="chat-panel" aria-label="快照分析对话">
      <div className="chat-heading">
        <h2>快照分析</h2>
        <button onClick={onClose} type="button">
          关闭分析
        </button>
      </div>
      <p className="hint">依据当前快照解释占用，建议均需人工确认。</p>
      {snapshot.status !== 'completed' && (
        <p className="partial-notice">当前为部分快照，未读取内容的占用未知。</p>
      )}
      <label htmlFor="chat-model">模型</label>
      <select
        id="chat-model"
        value={modelKey}
        disabled={!!activeId || pending}
        onChange={(event) => {
          setModelKey(event.target.value);
          setConversation(undefined);
          setRuns([]);
          setConsent(false);
          setError('');
        }}
      >
        {!models.length && <option value="">尚未配置模型</option>}
        {models.map((item) => (
          <option key={item.key} value={item.key}>
            {item.provider === 'ollama' ? '本地' : '云端'} · {item.model_id}
          </option>
        ))}
      </select>
      {loaded && !models.length && <p>尚未配置模型，请先配置后端模型连接。</p>}
      {diagnostics.length > 0 && (
        <p role="status">部分模型配置不可用，请检查后端配置。</p>
      )}
      <label htmlFor="chat-history">历史会话（最近 50 个）</label>
      <select
        id="chat-history"
        disabled={pending || !!activeId}
        value={conversation?.id || ''}
        onChange={(event) => void selectConversation(event.target.value)}
      >
        <option value="">新会话</option>
        {conversations.map((item, index) => (
          <option key={item.id} value={item.id}>
            会话 {conversations.length - index} · {item.model_key}
          </option>
        ))}
      </select>
      <p className="hint">
        {cloud
          ? '云端接收问题、近期对话和脱敏统计。文件名与路径从快照证据中移除；你主动输入的路径仍会发送。'
          : '本地模型仅连接本机 Ollama，不自动转用云端。'}
      </p>
      {cloud && (
        <label className="cloud-consent">
          <input
            type="checkbox"
            checked={consent}
            disabled={!!activeId}
            onChange={(event) => setConsent(event.target.checked)}
          />
          同意将问题、近期对话和脱敏统计发送至 DeepSeek
        </label>
      )}
      <div className="chat-transcript" aria-label="对话记录">
        {!runs.length && (
          <p className="chat-empty">可以问：哪些文件或目录值得优先检查？</p>
        )}
        {runs.map((run) => (
          <article key={run.id} className="chat-turn">
            <p className="chat-question">{run.question}</p>
            <span className="chat-status">{runStatus[run.status]}</span>
            <div className="chat-answer">
              {run.text.split(/(\[E\d+\])/g).map((part, index) =>
                /^\[E\d+\]$/.test(part) ? (
                  <a key={index} href={`#${run.id}-${part.slice(1, -1)}`}>
                    {part}
                  </a>
                ) : (
                  part
                ),
              )}
            </div>
            {run.error_message && (
              <p role="alert">
                {run.error_message}；已生成内容未完成或未验证。
              </p>
            )}
            {run.warning && <p className="partial-notice">{run.warning}</p>}
            {run.status === 'cancelled' && (
              <p>已停止生成，以上内容可能不完整。</p>
            )}
            {run.evidence.map((evidence) => (
              <EvidenceCard
                key={evidence.id}
                runId={run.id}
                evidence={evidence}
                onLocate={onLocate}
              />
            ))}
          </article>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      {connection && <p role="status">{connection}</p>}
      {(error || connection) && (
        <button type="button" onClick={() => void reconnect()}>
          重新连接
        </button>
      )}
      <form onSubmit={(event) => void send(event)}>
        <label htmlFor="chat-question">问题</label>
        <textarea
          id="chat-question"
          maxLength={2000}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={pending || !!activeId}
          rows={3}
        />
        <div className="chat-actions">
          <button
            type="submit"
            disabled={
              !model ||
              !question.trim() ||
              pending ||
              !!activeId ||
              (cloud && !consent)
            }
          >
            发送问题
          </button>
          {activeId && (
            <button
              type="button"
              onClick={() => void cancel()}
              disabled={pending}
            >
              取消生成
            </button>
          )}
        </div>
      </form>
    </aside>
  );
}
