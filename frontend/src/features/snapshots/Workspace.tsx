import { useCallback, useEffect, useRef, useState } from 'react';
import {
  bytes,
  isActive,
  request,
  statusText,
  type ChildrenPage,
  type FileNode,
  type Job,
  type Page,
  type ScanError,
  type Snapshot,
} from '../../lib/api';
import Treemap from '../treemap/Treemap';

interface Crumb {
  id: number;
  name: string;
}
interface View {
  snapshot: Snapshot;
  trail: Crumb[];
  page: ChildrenPage;
}

export default function Workspace() {
  const [path, setPath] = useState('');
  const [history, setHistory] = useState<Page<Snapshot>>();
  const [view, setView] = useState<View>();
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [pollRetry, setPollRetry] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<FileNode>();
  const [issues, setIssues] = useState<Page<ScanError>>();
  const sequence = useRef(0);
  const jobId = job?.id;
  const active = job ? isActive(job.status) : false;

  const refresh = useCallback(async (offset = 0) => {
    const result = await request<Page<Snapshot>>(
      `/snapshots?offset=${offset}&limit=50`,
    );
    setHistory(result);
  }, []);
  const openSnapshot = useCallback(async (id: string) => {
    const ticket = ++sequence.current;
    setLoading(true);
    setError('');
    setIssues(undefined);
    setSelected(undefined);
    try {
      const snapshot = await request<Snapshot>(`/snapshots/${id}`);
      if (isActive(snapshot.status))
        throw new Error('该快照仍在扫描，请等待扫描结束后打开。');
      const page = await request<ChildrenPage>(
        `/snapshots/${id}/nodes/${snapshot.root_node_id}/children`,
      );
      if (ticket !== sequence.current) return;
      setView({
        snapshot,
        page,
        trail: [{ id: snapshot.root_node_id, name: snapshot.root_path }],
      });
      const url = new URL(window.location.href);
      url.searchParams.set('snapshot', id);
      window.history.replaceState(null, '', url);
    } catch (cause) {
      if (ticket === sequence.current)
        setError(String(cause instanceof Error ? cause.message : cause));
    } finally {
      if (ticket === sequence.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      void refresh().catch((cause: Error) =>
        setError(`无法连接后端：${cause.message}`),
      );
      const snapshot = new URLSearchParams(window.location.search).get(
        'snapshot',
      );
      if (snapshot) void openSnapshot(snapshot);
    }, 0);
    return () => clearTimeout(timer);
  }, [refresh, openSnapshot]);
  useEffect(() => {
    if (!jobId || !active) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const id = jobId;
    async function poll() {
      try {
        const result = await request<Job>(`/scans/${id}`);
        if (disposed) return;
        setJob(result);
        if (isActive(result.status)) timer = setTimeout(() => void poll(), 500);
        else {
          await refresh();
          await openSnapshot(result.snapshot_id);
        }
      } catch (cause) {
        if (!disposed)
          setError(`扫描进度读取失败，请重试连接：${String(cause)}`);
      }
    }
    timer = setTimeout(() => void poll(), 250);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [jobId, active, pollRetry, refresh, openSnapshot]);

  async function recover() {
    setError('');
    try {
      await refresh();
      if (job) {
        const result = await request<Job>(`/scans/${job.id}`);
        setJob(result);
        if (isActive(result.status)) setPollRetry((value) => value + 1);
        else await openSnapshot(result.snapshot_id);
      }
    } catch (cause) {
      setError(String(cause));
    }
  }
  async function start(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setPending(true);
    try {
      const result = await request<Job>('/scans', { root_path: path });
      setJob(result);
    } catch (cause) {
      setError(String(cause instanceof Error ? cause.message : cause));
    } finally {
      setPending(false);
    }
  }
  async function navigate(trail: Crumb[], offset = 0) {
    if (!view) return;
    const ticket = ++sequence.current;
    setLoading(true);
    setSelected(undefined);
    setIssues(undefined);
    setError('');
    try {
      const page = await request<ChildrenPage>(
        `/snapshots/${view.snapshot.id}/nodes/${trail[trail.length - 1].id}/children?offset=${offset}&limit=200`,
      );
      if (ticket === sequence.current)
        setView({ snapshot: view.snapshot, page, trail });
    } catch (cause) {
      if (ticket === sequence.current) setError(String(cause));
    } finally {
      if (ticket === sequence.current) setLoading(false);
    }
  }
  const enter = (node: FileNode) => {
    if (view && node.kind === 'directory')
      void navigate([...view.trail, { id: node.id, name: node.name }]);
  };
  async function showErrors(offset = 0) {
    if (!view) return;
    try {
      setIssues(
        await request<Page<ScanError>>(
          `/snapshots/${view.snapshot.id}/errors?offset=${offset}&limit=50`,
        ),
      );
    } catch (cause) {
      setError(String(cause));
    }
  }
  return (
    <main className="workspace">
      <header className="app-header">
        <div>
          <h1>SpaceAnalyzer</h1>
          <p>本机磁盘快照 · 只读分析</p>
        </div>
        <span className="read-only">不修改、移动或删除被分析的文件</span>
      </header>
      <form className="scan-form" onSubmit={(event) => void start(event)}>
        <label htmlFor="scan-path">扫描目录或盘符</label>
        <div className="form-row">
          <input
            id="scan-path"
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="例如 D:\Downloads 或 D:\"
            required
            disabled={active || pending}
          />
          <button type="submit" disabled={active || pending}>
            {pending ? '正在提交…' : '创建快照'}
          </button>
          {active && (
            <button
              type="button"
              className="secondary"
              onClick={() =>
                void request<Job>(`/scans/${job!.id}/cancel`, {})
                  .then(async (result) => {
                    setJob(result);
                    if (!isActive(result.status)) {
                      await refresh();
                      await openSnapshot(result.snapshot_id);
                    }
                  })
                  .catch((cause: Error) => setError(cause.message))
              }
            >
              取消扫描
            </button>
          )}
        </div>
        <p className="hint">
          只读取元数据，不跟随链接或目录联接。面积代表逻辑大小，可能与系统已用空间不同。
        </p>
      </form>
      {error && (
        <div role="alert" className="error-banner">
          {error}
          <button
            className="secondary"
            onClick={() => {
              void recover();
            }}
          >
            重试连接
          </button>
        </div>
      )}
      {job && (
        <div role="status" className="scan-status">
          <strong>{statusText[job.status]}</strong>
          <span>
            {job.file_count.toLocaleString()} 个文件，{bytes(job.total_bytes)}，
            {job.error_count} 个遗漏或错误
          </span>
          {job.failure_message && <span>{job.failure_message}</span>}
          {active && <span>总量未知，扫描结束后生成可浏览快照。</span>}
        </div>
      )}
      <div className="workbench">
        <aside className="history">
          <div className="section-heading">
            <h2>快照</h2>
            <button
              className="text-button"
              onClick={() =>
                void refresh().catch((cause: Error) => setError(cause.message))
              }
            >
              刷新
            </button>
          </div>
          {!history ? (
            <p>正在加载…</p>
          ) : history.total === 0 ? (
            <p>还没有快照。输入目录开始扫描。</p>
          ) : (
            <>
              <ul>
                {history.items.map((snapshot) => (
                  <li key={snapshot.id}>
                    <button
                      className={`snapshot-button ${view?.snapshot.id === snapshot.id ? 'current' : ''}`}
                      onClick={() => void openSnapshot(snapshot.id)}
                    >
                      <strong title={snapshot.root_path}>
                        {snapshot.root_path}
                      </strong>
                      <span>
                        {bytes(snapshot.total_bytes)} ·{' '}
                        {statusText[snapshot.status]}
                      </span>
                      <time>
                        {new Date(snapshot.created_at).toLocaleString('zh-CN')}
                      </time>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="pagination">
                <button
                  disabled={history.offset === 0}
                  onClick={() =>
                    void refresh(Math.max(0, history.offset - 50)).catch(
                      (cause: Error) => setError(cause.message),
                    )
                  }
                >
                  上一页
                </button>
                <button
                  disabled={
                    history.offset + history.items.length >= history.total
                  }
                  onClick={() =>
                    void refresh(history.offset + 50).catch((cause: Error) =>
                      setError(cause.message),
                    )
                  }
                >
                  下一页
                </button>
              </div>
            </>
          )}
        </aside>
        <section className="snapshot-view" aria-label="磁盘快照详情">
          {loading && <p role="status">正在读取快照…</p>}
          {!view ? (
            <div className="welcome">
              <h2>空间分布，从一次快照开始</h2>
              <p>
                扫描后按面积查看大文件和目录，进入子目录逐层定位。历史快照保留当次结果，不会随磁盘内容自动改变。
              </p>
            </div>
          ) : (
            <>
              <div className="summary">
                <h2>逻辑大小 {bytes(view.snapshot.total_bytes)}</h2>
                <span>
                  {view.snapshot.file_count.toLocaleString()} 个文件 /{' '}
                  {view.snapshot.directory_count.toLocaleString()} 个目录
                </span>
              </div>
              <p className="hint">
                扫描区间：
                {new Date(view.snapshot.created_at).toLocaleString(
                  'zh-CN',
                )} 至{' '}
                {view.snapshot.ended_at
                  ? new Date(view.snapshot.ended_at).toLocaleString('zh-CN')
                  : '未结束'}
                ；硬链接按目录项计数。
              </p>
              {view.snapshot.status !== 'completed' && (
                <div className="partial-banner">
                  部分快照：{statusText[view.snapshot.status]}
                  ，不能视为扫描范围的完整结果。
                  <button
                    className="text-button"
                    onClick={() => void showErrors()}
                  >
                    查看遗漏与错误（{view.snapshot.error_count}）
                  </button>
                </div>
              )}
              {view.snapshot.skipped_count > 0 && (
                <p className="hint">
                  按策略排除自身数据库及辅助文件 {view.snapshot.skipped_count}{' '}
                  项。
                </p>
              )}
              <nav className="breadcrumbs" aria-label="目录导航">
                {view.trail.map((crumb, index) => (
                  <button
                    key={crumb.id}
                    disabled={loading}
                    onClick={() =>
                      void navigate(view.trail.slice(0, index + 1))
                    }
                  >
                    {index ? ' / ' : ''}
                    {crumb.name}
                  </button>
                ))}
              </nav>
              <Treemap
                items={view.page.items}
                totalBytes={view.page.total_bytes}
                omittedBytes={view.page.omitted_bytes}
                omittedCount={view.page.total - view.page.items.length}
                selected={selected?.id}
                onSelect={setSelected}
                onOpen={enter}
              />
              <div className="legend">
                <span>■ 目录</span>
                <span>■ 普通文件</span>
                <span>■ 压缩包 / 镜像</span>
                <span>■ 媒体</span>
                <span>■ 其他 / 未加载项</span>
              </div>
              {selected && (
                <div className="node-detail">
                  <strong>{selected.name}</strong>
                  <span>
                    {bytes(selected.size_bytes)}，当前目录{' '}
                    {view.page.total_bytes
                      ? (
                          (100 * selected.size_bytes) /
                          view.page.total_bytes
                        ).toFixed(2)
                      : 0}
                    %
                  </span>
                  <p>{selected.path}</p>
                  <span>{selected.readable ? '已读取' : '读取不完整'}</span>
                  {selected.kind === 'directory' && (
                    <button onClick={() => enter(selected)}>
                      进入选中目录
                    </button>
                  )}
                </div>
              )}
              <div className="section-heading">
                <h3>按大小排序</h3>
                <span>
                  共 {view.page.total.toLocaleString()} 项，当前加载{' '}
                  {view.page.items.length} 项
                </span>
              </div>
              {view.page.total === 0 ? (
                <p>此目录没有已记录的子项；部分快照可能包含无法读取的内容。</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>名称</th>
                      <th>逻辑大小</th>
                      <th>类型 / 状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.page.items.map((node) => (
                      <tr
                        key={node.id}
                        className={selected?.id === node.id ? 'selected' : ''}
                      >
                        <td>
                          <button
                            className="text-button"
                            onClick={() =>
                              node.kind === 'directory'
                                ? enter(node)
                                : setSelected(node)
                            }
                            title={node.path}
                          >
                            {node.kind === 'directory' ? '▸ ' : ''}
                            {node.name}
                          </button>
                          <button
                            className="detail-button"
                            aria-label={`查看 ${node.name} 详情`}
                            onClick={() => setSelected(node)}
                          >
                            详情
                          </button>
                        </td>
                        <td>{bytes(node.size_bytes)}</td>
                        <td>
                          {node.kind === 'directory' ? '目录' : '文件'}
                          {!node.readable ? ' / 不完整' : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <div className="pagination">
                <button
                  disabled={loading || view.page.offset === 0}
                  onClick={() =>
                    void navigate(
                      view.trail,
                      Math.max(0, view.page.offset - 200),
                    )
                  }
                >
                  上一页子项
                </button>
                <span>
                  {view.page.offset + (view.page.items.length ? 1 : 0)}–
                  {view.page.offset + view.page.items.length} /{' '}
                  {view.page.total}
                </span>
                <button
                  disabled={
                    loading ||
                    view.page.offset + view.page.items.length >= view.page.total
                  }
                  onClick={() =>
                    void navigate(view.trail, view.page.offset + 200)
                  }
                >
                  下一页子项
                </button>
              </div>
              {issues && (
                <section className="issues">
                  <h3>遗漏与错误</h3>
                  <ul>
                    {issues.items.map((issue) => (
                      <li key={issue.id}>
                        <strong>{issue.code}</strong>
                        <p>{issue.path}</p>
                        <p>{issue.message}</p>
                      </li>
                    ))}
                  </ul>
                  <div className="pagination">
                    <button
                      disabled={issues.offset === 0}
                      onClick={() =>
                        void showErrors(Math.max(0, issues.offset - 50))
                      }
                    >
                      上一页错误
                    </button>
                    <button
                      disabled={
                        issues.offset + issues.items.length >= issues.total
                      }
                      onClick={() => void showErrors(issues.offset + 50)}
                    >
                      下一页错误
                    </button>
                  </div>
                </section>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
