export type Status =
  | 'queued'
  | 'running'
  | 'completed'
  | 'completed_with_errors'
  | 'cancelled'
  | 'failed';
export interface Counts {
  total_bytes: number;
  file_count: number;
  directory_count: number;
  error_count: number;
  skipped_count: number;
}
export interface Snapshot extends Counts {
  id: string;
  job_id: string;
  root_path: string;
  root_node_id: number;
  status: Status;
  created_at: string;
  ended_at: string | null;
  metric: 'logical';
  policy_version: number;
}
export interface Job extends Counts {
  id: string;
  snapshot_id: string;
  root_path: string;
  status: Status;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  failure_message: string | null;
}
export interface FileNode {
  id: number;
  parent_id: number | null;
  snapshot_id: string;
  name: string;
  path: string;
  kind: 'directory' | 'file';
  size_bytes: number;
  modified_ns: number;
  readable: boolean;
}
export interface ScanError {
  id: number;
  snapshot_id: string;
  path: string;
  code: string;
  message: string;
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface ChildrenPage extends Page<FileNode> {
  total_bytes: number;
  returned_bytes: number;
  omitted_bytes: number;
}
export const statusText: Record<Status, string> = {
  queued: '排队中',
  running: '扫描中',
  completed: '扫描完成',
  completed_with_errors: '部分完成',
  cancelled: '已取消',
  failed: '失败或中断',
};
export const isActive = (status: Status) =>
  status === 'queued' || status === 'running';

export async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    body
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === 'string'
        ? error.detail
        : `请求失败（${response.status}）`,
    );
  }
  return response.json() as Promise<T>;
}

export function bytes(value: number): string {
  if (value === 0) return '0 B';
  const unit = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4);
  return `${(value / 1024 ** unit).toLocaleString('zh-CN', { maximumFractionDigits: unit ? 2 : 0 })} ${['B', 'KiB', 'MiB', 'GiB', 'TiB'][unit]}`;
}
