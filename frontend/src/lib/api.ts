export interface FormatOption {
  quality: string;
  label: string;
  ext: string;
  filesize?: number | null;
  type: "video" | "audio";
}

export interface VideoInfo {
  title: string;
  thumbnail?: string | null;
  duration?: number | null;
  uploader?: string | null;
  webpage_url?: string | null;
  resolved_url?: string | null;
  formats: FormatOption[];
}

export interface Progress {
  status: "queued" | "downloading" | "processing" | "finished" | "error" | "cancelled";
  percent: number;
  speed?: string | null;
  eta?: string | null;
  filename?: string | null;
  error?: string | null;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return data?.detail || "请求失败，请稍后重试";
  } catch {
    return "请求失败，请稍后重试";
  }
}

export async function fetchInfo(url: string): Promise<VideoInfo> {
  const res = await fetch("/api/info", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function startDownload(url: string, quality: string): Promise<string> {
  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, quality }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.task_id as string;
}

export async function fetchProgress(taskId: string): Promise<Progress> {
  const res = await fetch(`/api/progress/${taskId}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function cancelDownload(taskId: string): Promise<void> {
  const res = await fetch(`/api/cancel/${taskId}`, { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
}

export function fileUrl(taskId: string): string {
  return `/api/file/${taskId}`;
}

export function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(1)} ${units[i]}`;
}

export function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const pad = (x: number) => x.toString().padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/* ------------------------------------------------------------------ */
/*  AI Analysis                                                        */
/* ------------------------------------------------------------------ */

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface AiAnalyzeResult {
  title: string;
  language?: string | null;
  segments: TranscriptSegment[];
  full_text: string;
  summary: string;
  mindmap: string;
  truncated: boolean;
  subtitle_source?: string | null;
}

export interface AiChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function fetchAiAnalyze(url: string): Promise<AiAnalyzeResult> {
  const res = await fetch("/api/ai/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchAiChat(
  url: string,
  question: string,
  transcriptText: string,
  history: AiChatMessage[] = [],
): Promise<string> {
  const res = await fetch("/api/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      question,
      transcript_text: transcriptText,
      history,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.answer as string;
}
