import { useEffect, useRef, useState } from "react";
import {
  Clipboard,
  Download,
  Loader2,
  Music,
  Sparkles,
  Video as VideoIcon,
  AlertCircle,
  CheckCircle2,
  XCircle,
  X,
  RotateCcw,
  TextSelect,
} from "lucide-react";
import {
  fetchInfo,
  startDownload,
  fetchProgress,
  cancelDownload,
  fileUrl,
  formatBytes,
  formatDuration,
  type VideoInfo,
} from "../lib/api";
import AiAnalysisPanel from "./AiAnalyzer";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ParsePhase = "idle" | "parsing" | "ready" | "error";

interface DownloadTask {
  taskId: string;
  title: string;
  thumbnail?: string | null;
  qualityLabel: string;
  status: "queued" | "downloading" | "processing" | "finished" | "error" | "cancelled";
  percent: number;
  speed?: string | null;
  eta?: string | null;
  filename?: string | null;
  error?: string | null;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function Downloader() {
  const [url, setUrl] = useState("");
  const [parsePhase, setParsePhase] = useState<ParsePhase>("idle");
  const [parseError, setParseError] = useState<string | null>(null);
  const [info, setInfo] = useState<VideoInfo | null>(null);
  const [quality, setQuality] = useState("best");
  const [tasks, setTasks] = useState<DownloadTask[]>([]);

  const pollsRef = useRef<Map<string, number>>(new Map());
  const triggeredRef = useRef<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      pollsRef.current.forEach((id) => window.clearInterval(id));
    };
  }, []);

  /* ---------- input helpers ---------- */

  async function handlePaste() {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setUrl(text.trim());
    } catch {
      /* browser may deny clipboard */
    }
  }

  function handleSelectAll() {
    inputRef.current?.focus();
    inputRef.current?.select();
  }

  async function handleParse() {
    const trimmed = url.trim();
    if (!trimmed) {
      setParseError("请输入或粘贴视频链接");
      setParsePhase("error");
      return;
    }
    setParseError(null);
    setInfo(null);
    setParsePhase("parsing");
    try {
      const data = await fetchInfo(trimmed);
      setInfo(data);
      setQuality(data.formats[0]?.quality ?? "best");
      setParsePhase("ready");
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "解析失败");
      setParsePhase("error");
    }
  }

  /* ---------- download ---------- */

  async function handleDownload() {
    if (!info) return;
    const fmt = info.formats.find((f) => f.quality === quality);
    try {
      const taskId = await startDownload(url.trim(), quality);
      const task: DownloadTask = {
        taskId,
        title: info.title,
        thumbnail: info.thumbnail,
        qualityLabel: fmt?.label ?? quality,
        status: "queued",
        percent: 0,
      };
      setTasks((prev) => [task, ...prev]);
      startPolling(taskId);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "创建下载失败");
      setParsePhase("error");
    }
  }

  function startPolling(taskId: string) {
    const id = window.setInterval(async () => {
      try {
        const p = await fetchProgress(taskId);
        setTasks((prev) =>
          prev.map((t) =>
            t.taskId === taskId
              ? { ...t, status: p.status, percent: p.percent, speed: p.speed, eta: p.eta, filename: p.filename, error: p.error }
              : t,
          ),
        );
        if (p.status === "finished") {
          stopPolling(taskId);
          if (!triggeredRef.current.has(taskId)) {
            triggeredRef.current.add(taskId);
            triggerSave(taskId, p.filename);
          }
        } else if (p.status === "error" || p.status === "cancelled") {
          stopPolling(taskId);
        }
      } catch {
        /* polling failure — retry next tick */
      }
    }, 1000);
    pollsRef.current.set(taskId, id);
  }

  function stopPolling(taskId: string) {
    const id = pollsRef.current.get(taskId);
    if (id != null) {
      window.clearInterval(id);
      pollsRef.current.delete(taskId);
    }
  }

  function triggerSave(taskId: string, filename?: string | null) {
    const a = document.createElement("a");
    a.href = fileUrl(taskId);
    a.download = filename || "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function handleCancel(taskId: string) {
    stopPolling(taskId);
    setTasks((prev) =>
      prev.map((t) => (t.taskId === taskId ? { ...t, status: "cancelled" as const, error: "下载已取消" } : t)),
    );
    try {
      await cancelDownload(taskId);
    } catch {
      /* best-effort */
    }
  }

  function handleRemove(taskId: string) {
    stopPolling(taskId);
    triggeredRef.current.delete(taskId);
    setTasks((prev) => prev.filter((t) => t.taskId !== taskId));
  }

  /* ---------- render ---------- */

  const parsing = parsePhase === "parsing";

  return (
    <div className="mx-auto w-full max-w-3xl space-y-3">
      {/* ====== input card ====== */}
      <div className="card p-2 shadow-cardHover">
        <div className="flex flex-col gap-2 rounded-2xl bg-white p-2 sm:flex-row sm:items-center">
          <div className="flex flex-1 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2.5">
            <VideoIcon className="h-5 w-5 shrink-0 text-brand" />
            <input
              ref={inputRef}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleParse()}
              placeholder="粘贴视频链接或课程/文章页面，支持自动识别嵌入的 B站 / YouTube / 抖音 等视频"
              className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-slate-400 sm:text-base"
            />
            <button
              onClick={handleSelectAll}
              title="全选"
              className="shrink-0 rounded-full p-1.5 text-slate-400 transition hover:bg-slate-200 hover:text-brand"
            >
              <TextSelect className="h-4 w-4" />
            </button>
            <button
              onClick={handlePaste}
              title="粘贴"
              className="shrink-0 rounded-full p-1.5 text-slate-400 transition hover:bg-slate-200 hover:text-brand"
            >
              <Clipboard className="h-4 w-4" />
            </button>
          </div>
          <button onClick={handleParse} disabled={parsing} className="btn-primary h-12 px-7 text-base">
            {parsing ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" /> 解析中
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5" /> 立即解析
              </>
            )}
          </button>
        </div>

        {/* parse error */}
        {parsePhase === "error" && parseError && (
          <div className="mx-2 mt-2 flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{parseError}</span>
          </div>
        )}

        {/* parse result */}
        {info && parsePhase === "ready" && (
          <div className="mx-2 mb-2 mt-2 rounded-2xl border border-slate-100 bg-slate-50/60 p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
              {info.thumbnail && (
                <div className="relative w-full shrink-0 overflow-hidden rounded-xl bg-slate-200 sm:w-48 sm:self-start">
                  <div className="aspect-video w-full">
                    <img
                      src={info.thumbnail}
                      alt={info.title}
                      className="h-full w-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                  </div>
                  {info.duration ? (
                    <span className="absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
                      {formatDuration(info.duration)}
                    </span>
                  ) : null}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <h3 className="line-clamp-2 text-left text-base font-semibold text-ink">{info.title}</h3>
                {info.uploader && <p className="mt-1 text-left text-sm text-ink-muted">{info.uploader}</p>}
                {info.resolved_url && (
                  <p className="mt-1 text-left text-xs text-brand">
                    已从页面识别视频链接：{info.resolved_url}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {info.formats.map((f) => {
                    const active = quality === f.quality;
                    return (
                      <button
                        key={f.quality}
                        onClick={() => setQuality(f.quality)}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition ${
                          active ? "border-brand bg-brand text-white shadow-sm" : "border-slate-200 bg-white text-ink hover:border-brand-100"
                        }`}
                      >
                        {f.type === "audio" ? <Music className="h-3.5 w-3.5" /> : <VideoIcon className="h-3.5 w-3.5" />}
                        {f.label}
                        {f.filesize ? (
                          <span className={active ? "text-white/80" : "text-slate-400"}>· {formatBytes(f.filesize)}</span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button onClick={handleDownload} className="btn-primary h-11 w-full sm:w-auto sm:px-8">
                    <Download className="h-5 w-5" /> 开始下载
                  </button>
                </div>
              </div>
            </div>

            <AiAnalysisPanel url={url.trim()} videoTitle={info.title} />
          </div>
        )}
      </div>

      {/* ====== task list ====== */}
      {tasks.length > 0 && (
        <div className="space-y-2">
          {tasks.map((task) => (
            <TaskCard
              key={task.taskId}
              task={task}
              onCancel={() => handleCancel(task.taskId)}
              onSave={() => triggerSave(task.taskId, task.filename)}
              onRemove={() => handleRemove(task.taskId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Task card                                                          */
/* ------------------------------------------------------------------ */

function TaskCard({
  task,
  onCancel,
  onSave,
  onRemove,
}: {
  task: DownloadTask;
  onCancel: () => void;
  onSave: () => void;
  onRemove: () => void;
}) {
  const active = task.status === "queued" || task.status === "downloading" || task.status === "processing";
  const done = task.status === "finished";
  const failed = task.status === "error" || task.status === "cancelled";
  const processing = task.status === "processing";

  return (
    <div className="card flex items-center gap-3 px-4 py-3">
      {/* mini thumbnail */}
      {task.thumbnail && (
        <img
          src={task.thumbnail}
          alt=""
          className="hidden h-10 w-16 shrink-0 rounded-lg object-cover sm:block"
          referrerPolicy="no-referrer"
        />
      )}

      {/* info + progress */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-ink">{task.title}</span>
          <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">{task.qualityLabel}</span>
        </div>

        {active && (
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand to-[#6D5DFB] transition-all duration-500 ease-out"
                style={{ width: `${Math.max(task.percent, processing ? 98 : 2)}%` }}
              />
            </div>
            <span className="shrink-0 text-xs tabular-nums text-slate-400">{task.percent.toFixed(0)}%</span>
          </div>
        )}

        {active && (
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400">
            <Loader2 className="h-3 w-3 animate-spin text-brand" />
            <span>{processing ? "合并处理中…" : task.status === "queued" ? "排队中…" : "下载中…"}</span>
            {task.speed && <span>· {task.speed}</span>}
            {task.eta && <span>· 剩余 {task.eta}</span>}
          </div>
        )}

        {done && (
          <p className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" /> 下载完成
          </p>
        )}

        {failed && (
          <p className="mt-1 inline-flex items-center gap-1 text-xs text-red-500">
            <XCircle className="h-3.5 w-3.5" /> {task.error || "下载失败"}
          </p>
        )}
      </div>

      {/* actions */}
      <div className="flex shrink-0 items-center gap-1">
        {active && (
          <button onClick={onCancel} title="取消下载" className="rounded-full p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-500">
            <X className="h-4 w-4" />
          </button>
        )}
        {done && (
          <button onClick={onSave} title="重新保存" className="btn-ghost h-8 gap-1 px-3 text-xs">
            <Download className="h-3.5 w-3.5" /> 保存
          </button>
        )}
        {failed && (
          <button onClick={onRemove} title="移除" className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-ink">
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
        {done && (
          <button onClick={onRemove} title="移除" className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-ink">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
