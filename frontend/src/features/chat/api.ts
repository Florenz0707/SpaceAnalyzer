export interface ModelInfo {
  key: string;
  provider: 'deepseek_api' | 'ollama';
  model_id: string;
}
export interface Conversation {
  id: string;
  snapshot_id: string;
  model_key: string;
  allow_cloud: boolean;
}
export interface Evidence {
  id: string;
  query: string;
  snapshot_id: string;
  data: Record<string, unknown>;
}
export interface AnalysisRun {
  id: string;
  conversation_id: string;
  question: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  text: string;
  evidence: Evidence[];
  usage: Record<string, number | null>;
  warning?: string | null;
  error_message?: string | null;
}
export interface RunEvent {
  run_id: string;
  sequence: number;
  kind: string;
  data: {
    status?: AnalysisRun['status'];
    text?: string;
    evidence?: Evidence[];
  };
}
export const running = (run: AnalysisRun) =>
  run.status === 'queued' || run.status === 'running';
export const runStatus = {
  queued: '准备分析',
  running: '生成中',
  completed: '已完成',
  failed: '失败或中断',
  cancelled: '已取消',
};
