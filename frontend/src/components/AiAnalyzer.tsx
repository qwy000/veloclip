import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Brain,
  Expand,
  GitBranch,
  ImageDown,
  Loader2,
  Maximize2,
  MessageCircle,
  Send,
  Shrink,
  Sparkles,
  Subtitles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { toPng } from "html-to-image";
import {
  fetchAiAnalyze,
  fetchAiChat,
  formatDuration,
  type AiAnalyzeResult,
  type AiChatMessage,
} from "../lib/api";

type Tab = "summary" | "mindmap" | "transcript" | "chat";
type Phase = "idle" | "analyzing" | "ready" | "error";

const TABS: { id: Tab; label: string; icon: typeof Brain }[] = [
  { id: "summary", label: "AI 总结", icon: Brain },
  { id: "mindmap", label: "思维导图", icon: GitBranch },
  { id: "transcript", label: "字幕文本", icon: Subtitles },
  { id: "chat", label: "AI 提问", icon: MessageCircle },
];

interface AiAnalysisPanelProps {
  url: string;
  videoTitle?: string;
}

export default function AiAnalysisPanel({ url, videoTitle }: AiAnalysisPanelProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AiAnalyzeResult | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const preserveScrollY = useRef<number | null>(null);

  useEffect(() => {
    setPhase("idle");
    setError(null);
    setResult(null);
    setTab("summary");
  }, [url]);

  async function handleAnalyze() {
    const trimmed = url.trim();
    if (!trimmed) return;
    setError(null);
    setResult(null);
    setPhase("analyzing");
    try {
      const data = await fetchAiAnalyze(trimmed);
      setResult(data);
      setPhase("ready");
      setTab("summary");
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI 分析失败");
      setPhase("error");
    }
  }

  const analyzing = phase === "analyzing";

  useLayoutEffect(() => {
    if (preserveScrollY.current !== null) {
      window.scrollTo(0, preserveScrollY.current);
      preserveScrollY.current = null;
    }
  }, [tab]);

  function handleTabChange(next: Tab) {
    preserveScrollY.current = window.scrollY;
    setTab(next);
  }

  return (
    <div className="mt-5 border-t border-slate-200 pt-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-left">
          <h4 className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
            <Brain className="h-4 w-4 text-[#6D5DFB]" />
            AI 视频分析
          </h4>
          <p className="mt-0.5 text-xs text-ink-muted">
            提取字幕 · 智能总结 · 思维导图 · 问答
          </p>
        </div>
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={analyzing}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#6D5DFB] to-brand px-5 text-sm font-medium text-white shadow-glow transition hover:-translate-y-0.5 disabled:opacity-60"
        >
          {analyzing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> 分析中…
            </>
          ) : phase === "ready" ? (
            <>
              <Sparkles className="h-4 w-4" /> 重新分析
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" /> 开始 AI 分析
            </>
          )}
        </button>
      </div>

      {analyzing && (
        <div className="mt-3 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
          <p className="font-medium">正在处理，请稍候…</p>
          <p className="mt-1 text-brand-600/80">
            ① 提取平台字幕 → ② DeepSeek 生成总结 → ③ 生成思维导图（约 30–90 秒）
          </p>
        </div>
      )}

      {phase === "error" && error && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && phase === "ready" && (
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-100 bg-white">
          <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-3">
            <p className="text-left text-xs text-ink-muted">
              {result.language ? `字幕语言：${result.language}` : result.subtitle_source === "metadata" ? "无字幕" : "已提取字幕"}
              {result.subtitle_source === "danmaku" && " · B 站弹幕（非官方 CC）"}
              {result.subtitle_source === "cc" && " · 官方字幕"}
              {result.subtitle_source === "auto" && " · 自动生成字幕"}
              {result.subtitle_source === "metadata" && " · 无字幕（元数据分析）"}
              {result.truncated ? " · 字幕较长，已截取前半部分" : ""}
              {" · "}
              共 {result.segments.length} 条
            </p>
          </div>

          <div className="flex flex-wrap gap-1 border-b border-slate-100 px-2 pt-2">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleTabChange(id)}
                className={`inline-flex items-center gap-1.5 rounded-t-lg px-3 py-2 text-sm font-medium transition ${
                  tab === id
                    ? "bg-white text-brand shadow-sm ring-1 ring-slate-100"
                    : "text-ink-muted hover:text-brand"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          <div className="min-h-[280px] p-4">
            {tab === "summary" && <MarkdownView content={result.summary} />}
            {tab === "mindmap" && (
              <MindMapView markdown={result.mindmap} title={result.title || videoTitle || "mindmap"} />
            )}
            {tab === "transcript" && <TranscriptView segments={result.segments} />}
            {tab === "chat" && (
              <ChatPanel
                url={url.trim()}
                transcriptText={result.full_text}
                subtitleSource={result.subtitle_source}
                title={result.title || videoTitle || ""}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Markdown renderer (lightweight)                                    */
/* ------------------------------------------------------------------ */

function MarkdownView({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="prose-sm max-w-none space-y-3 text-left text-sm leading-relaxed text-ink">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-2" />;
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={i} className="mt-4 text-base font-bold text-ink">
              {trimmed.slice(3)}
            </h3>
          );
        }
        if (trimmed.startsWith("# ")) {
          return (
            <h2 key={i} className="text-lg font-bold text-ink">
              {trimmed.slice(2)}
            </h2>
          );
        }
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
          return (
            <li key={i} className="ml-4 list-disc text-ink-muted">
              <InlineBold text={trimmed.slice(2)} />
            </li>
          );
        }
        return (
          <p key={i} className="text-ink-muted">
            <InlineBold text={trimmed} />
          </p>
        );
      })}
    </div>
  );
}

function InlineBold({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i} className="font-semibold text-ink">
            {part.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Mind map tree from markdown                                        */
/* ------------------------------------------------------------------ */

interface TreeNode {
  label: string;
  children: TreeNode[];
}

function parseMarkdownOutline(md: string): TreeNode {
  const root: TreeNode = { label: "主题", children: [] };
  const stack: { level: number; node: TreeNode }[] = [{ level: 0, node: root }];
  const lines = md.split("\n");

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const heading = line.match(/^(#{1,4})\s+(.+)/);
    if (heading) {
      const level = heading[1].length;
      const node: TreeNode = { label: heading[2], children: [] };
      while (stack.length > 1 && stack[stack.length - 1].level >= level) stack.pop();
      stack[stack.length - 1].node.children.push(node);
      stack.push({ level, node });
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.+)/);
    if (bullet) {
      const node: TreeNode = { label: bullet[1], children: [] };
      stack[stack.length - 1].node.children.push(node);
    }
  }
  if (root.children.length === 1) return root.children[0];
  if (root.children.length > 0) {
    return { label: root.children[0].label, children: root.children };
  }
  return { label: "思维导图", children: [] };
}

function MindMapView({ markdown, title }: { markdown: string; title: string }) {
  const tree = parseMarkdownOutline(markdown);
  const fullscreenRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const [exporting, setExporting] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const clampScale = (v: number) => Math.min(2.5, Math.max(0.35, v));

  useEffect(() => {
    function syncFullscreen() {
      setIsFullscreen(document.fullscreenElement === fullscreenRef.current);
    }
    document.addEventListener("fullscreenchange", syncFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncFullscreen);
  }, []);

  async function toggleFullscreen() {
    const el = fullscreenRef.current;
    if (!el) return;
    try {
      if (document.fullscreenElement === el) {
        await document.exitFullscreen();
      } else {
        await el.requestFullscreen();
      }
    } catch {
      /* fullscreen not supported or denied */
    }
  }

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.08 : 0.08;
    setScale((s) => clampScale(s + delta));
  }

  function handlePointerDown(e: React.PointerEvent) {
    if ((e.target as HTMLElement).closest("button")) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (!dragging) return;
    setPan({
      x: dragStart.current.panX + (e.clientX - dragStart.current.x),
      y: dragStart.current.panY + (e.clientY - dragStart.current.y),
    });
  }

  function handlePointerUp(e: React.PointerEvent) {
    setDragging(false);
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }

  async function handleExportPng() {
    if (!canvasRef.current || !containerRef.current || exporting) return;
    setExporting(true);
    const node = canvasRef.current;
    const container = containerRef.current;
    const prevNodeTransform = node.style.transform;
    const prevNodeTransition = node.style.transition;
    const prevContainerOverflow = container.style.overflow;
    try {
      node.style.transform = "none";
      node.style.transition = "none";
      container.style.overflow = "visible";

      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      });

      const dataUrl = await toPng(node, {
        backgroundColor: "#f8fafc",
        pixelRatio: 2,
        cacheBust: true,
        width: node.scrollWidth,
        height: node.scrollHeight,
      });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${title.slice(0, 30).replace(/[\\/:*?"<>|]/g, "_")}-mindmap.png`;
      a.click();
    } catch {
      /* export failed */
    } finally {
      node.style.transform = prevNodeTransform;
      node.style.transition = prevNodeTransition;
      container.style.overflow = prevContainerOverflow;
      setExporting(false);
    }
  }

  return (
    <div
      ref={fullscreenRef}
      className={`space-y-3 ${isFullscreen ? "flex h-screen flex-col bg-gradient-to-br from-slate-50 to-brand-50/30 p-4" : ""}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-left text-xs text-ink-muted">
          滚轮缩放 · 拖拽平移 · 滚动条浏览{isFullscreen ? " · Esc 退出全屏" : ""}
        </p>
        <div className="flex flex-wrap items-center gap-1">
          <button
            type="button"
            onClick={() => setScale((s) => clampScale(s - 0.15))}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-ink-muted hover:border-brand-100 hover:text-brand"
            title="缩小"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <input
            type="range"
            min={35}
            max={250}
            step={5}
            value={Math.round(scale * 100)}
            onChange={(e) => setScale(clampScale(Number(e.target.value) / 100))}
            className="h-1.5 w-24 cursor-pointer accent-brand"
            title="缩放比例"
            aria-label="思维导图缩放"
          />
          <span className="min-w-[3rem] text-center text-xs tabular-nums text-ink-muted">
            {Math.round(scale * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setScale((s) => clampScale(s + 0.15))}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-ink-muted hover:border-brand-100 hover:text-brand"
            title="放大"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              setScale(1);
              setPan({ x: 0, y: 0 });
            }}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-ink-muted hover:border-brand-100 hover:text-brand"
            title="重置视图"
          >
            <Maximize2 className="h-3.5 w-3.5" /> 重置
          </button>
          <button
            type="button"
            onClick={toggleFullscreen}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-ink-muted hover:border-brand-100 hover:text-brand"
            title={isFullscreen ? "退出全屏" : "全屏展示"}
          >
            {isFullscreen ? <Shrink className="h-3.5 w-3.5" /> : <Expand className="h-3.5 w-3.5" />}
            {isFullscreen ? "退出全屏" : "全屏"}
          </button>
          <button
            type="button"
            onClick={handleExportPng}
            disabled={exporting}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-brand bg-brand px-2.5 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-60"
            title="导出 PNG"
          >
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageDown className="h-3.5 w-3.5" />}
            导出 PNG
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className={`relative overflow-auto rounded-xl border border-slate-100 bg-gradient-to-br from-slate-50 to-brand-50/30 ${
          isFullscreen ? "min-h-0 flex-1" : "h-[360px]"
        } ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <div
          ref={canvasRef}
          className="inline-block min-w-max origin-top-left p-8 transition-transform duration-75"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }}
        >
          <TreeNodeView node={tree} depth={0} />
        </div>
      </div>
    </div>
  );
}

function TreeNodeView({ node, depth }: { node: TreeNode; depth: number }) {
  const colors = [
    "border-brand bg-brand text-white",
    "border-[#6D5DFB] bg-white text-ink",
    "border-slate-200 bg-white text-ink-muted",
  ];
  const cls = colors[Math.min(depth, colors.length - 1)];
  return (
    <div className={`${depth > 0 ? "ml-6 mt-2 border-l-2 border-brand-100 pl-4" : ""}`}>
      <div
        className={`box-border w-fit max-w-[14rem] rounded-xl border px-3 py-2 text-sm font-medium leading-relaxed shadow-sm break-words [overflow-wrap:anywhere] ${cls}`}
      >
        {node.label}
      </div>
      {node.children.length > 0 && (
        <div className="mt-1">
          {node.children.map((child, i) => (
            <TreeNodeView key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Transcript list                                                    */
/* ------------------------------------------------------------------ */

function TranscriptView({ segments }: { segments: AiAnalyzeResult["segments"] }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    listRef.current?.scrollTo(0, 0);
  }, [segments]);
  return (
    <div
      ref={listRef}
      className="max-h-[360px] space-y-1 overflow-y-auto rounded-xl border border-slate-100 bg-slate-50/50 p-2"
    >
      {segments.map((seg, i) => (
        <div key={i} className="flex gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-white">
          <span className="shrink-0 font-mono text-xs tabular-nums text-brand">
            {formatDuration(seg.start)}
          </span>
          <span className="text-sm leading-relaxed text-ink">{seg.text}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  AI Chat                                                            */
/* ------------------------------------------------------------------ */

function ChatPanel({
  url,
  transcriptText,
  subtitleSource,
  title,
}: {
  url: string;
  transcriptText: string;
  subtitleSource?: string | null;
  title: string;
}) {
  const [messages, setMessages] = useState<AiChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    setInput("");
    setChatError(null);
  }, [url]);

  useEffect(() => {
    if (messages.length === 0 && !loading) return;
    const el = chatScrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setChatError(null);
    const userMsg: AiChatMessage = { role: "user", content: q };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    setLoading(true);
    try {
      const answer = await fetchAiChat(url, q, transcriptText, messages, subtitleSource);
      setMessages([...nextHistory, { role: "assistant", content: answer }]);
    } catch (e) {
      setChatError(e instanceof Error ? e.message : "提问失败");
      setMessages(messages);
      setInput(q);
    } finally {
      setLoading(false);
    }
  }

  const suggestions = [
    "这个视频的核心观点是什么？",
    "有哪些值得记笔记的要点？",
    "用三句话概括视频内容",
  ];

  return (
    <div className="flex h-[360px] flex-col">
      <p className="mb-3 text-left text-xs text-ink-muted">
        基于「{title}」字幕内容提问，AI 将结合视频上下文回答
      </p>

      <div
        ref={chatScrollRef}
        className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-slate-100 bg-slate-50/50 p-4"
      >
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-ink-muted">试试这些问题：</p>
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setInput(s)}
                className="block w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-left text-sm text-ink transition hover:border-brand-100 hover:text-brand"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-brand text-white"
                  : "border border-slate-200 bg-white text-ink"
              }`}
            >
              {msg.role === "assistant" ? <MarkdownView content={msg.content} /> : msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin text-brand" />
            思考中…
          </div>
        )}
      </div>

      {chatError && <p className="mt-2 text-left text-xs text-red-500">{chatError}</p>}

      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="输入你的问题…"
          className="flex-1 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand text-white transition hover:bg-brand-600 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
