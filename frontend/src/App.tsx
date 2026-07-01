import { useState } from "react";
import {
  Download,
  Zap,
  Globe2,
  ShieldCheck,
  Smartphone,
  Layers,
  Sparkles,
  Check,
  ChevronDown,
  Menu,
  X,
  Youtube,
  Music2,
  Play,
} from "lucide-react";
import Downloader from "./components/Downloader";

const SITE_NAME = "VeloClip";

const PLATFORMS = [
  "YouTube",
  "哔哩哔哩",
  "抖音 / TikTok",
  "X / Twitter",
  "Instagram",
  "微博",
  "西瓜视频",
  "Facebook",
];

const FEATURES = [
  {
    icon: Globe2,
    title: "全平台覆盖",
    desc: "基于业界最强开源引擎，支持上千个站点，一个网站搞定所有视频来源。",
  },
  {
    icon: ShieldCheck,
    title: "高清画质",
    desc: "自动匹配可用最高清晰度，支持 1080p / 4K 等档位，按需选择仅音频 MP3。",
  },
  {
    icon: Zap,
    title: "极速下载",
    desc: "服务端多线程拉取与智能合流，解析快、下载快，告别漫长等待。",
  },
  {
    icon: Smartphone,
    title: "手机也能用",
    desc: "纯网页操作，无需安装任何 App，手机、平板、电脑随时随地下载。",
  },
  {
    icon: Layers,
    title: "清晰度自选",
    desc: "1080P、720P、仅音频 MP3 …… 按需选择，流量与画质你说了算。",
  },
  {
    icon: Sparkles,
    title: "零门槛上手",
    desc: "粘贴链接、点一下、即下载。三步完成，长辈都会用。",
  },
];

const STEPS = [
  { num: "01", title: "复制视频链接", desc: "在任意平台复制你想保存的视频地址。" },
  { num: "02", title: "粘贴并解析", desc: "贴进输入框，一键解析出可下载的清晰度。" },
  { num: "03", title: "选清晰度下载", desc: "选择画质，点击下载，文件直达你的设备。" },
];

const PLANS = [
  {
    name: "免费版",
    price: "¥0",
    period: "/ 永久",
    desc: "适合偶尔下载的轻度用户",
    features: ["每日 5 次下载*", "最高 720P 画质*", "标准解析速度", "全平台支持"],
    cta: "免费开始",
    ctaHref: "#download",
    highlight: false,
  },
  {
    name: "Pro 会员",
    price: "¥19",
    period: "/ 月",
    desc: "追求高清与效率的创作者首选",
    features: [
      "无限次下载",
      "最高 4K 超清画质",
      "极速通道 · 优先解析",
      "批量下载",
      "无广告纯净体验",
    ],
    cta: "升级 Pro",
    ctaHref: "#download",
    highlight: true,
  },
  {
    name: "旗舰版",
    price: "¥149",
    period: "/ 年",
    desc: "重度用户与团队的超值之选",
    features: ["Pro 全部权益", "全年立省 40%", "AI 字幕翻译（即将上线）", "视频智能总结 · 思维导图", "专属客服支持"],
    cta: "立省 40%",
    ctaHref: "#download",
    highlight: false,
  },
];

const FAQS = [
  {
    q: "支持哪些视频平台？",
    a: "我们基于业界领先的开源下载引擎，支持 YouTube、哔哩哔哩、抖音、TikTok、X (Twitter)、Instagram、微博等上千个主流平台。",
  },
  {
    q: "下载的视频有水印吗？",
    a: "取决于来源平台与视频本身。我们会尽量获取平台提供的最高可用清晰度；部分平台可能仍带水印或为硬字幕，请以实际解析结果为准。",
  },
  {
    q: "需要安装软件吗？",
    a: "完全不需要。VeloClip 是纯网页工具，打开浏览器即可使用，手机和电脑都支持。",
  },
  {
    q: "有些视频无法下载怎么办？",
    a: "需要登录、会员或受版权保护（DRM）的内容可能无法下载。请确认链接为公开可访问的视频。",
  },
  {
    q: "下载的内容可以商用吗？",
    a: "请遵守各平台的服务条款与版权规定，本工具仅供个人学习与合规使用，下载内容的使用责任由用户自行承担。",
  },
];

export default function App() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <Hero />
      <Platforms />
      <Steps />
      <Features />
      <Pricing />
      <FAQ />
      <CTA />
      <Footer />
    </div>
  );
}

function Logo() {
  return (
    <a href="#top" className="flex items-center gap-2">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand to-[#6D5DFB] text-white shadow-glow">
        <Download className="h-5 w-5" />
      </span>
      <span className="text-lg font-bold tracking-tight text-ink">
        Velo<span className="text-brand">Clip</span>
      </span>
    </a>
  );
}

function Navbar() {
  const [open, setOpen] = useState(false);
  const links = [
    { label: "功能特性", href: "#features" },
    { label: "使用步骤", href: "#steps" },
    { label: "会员定价", href: "#pricing" },
    { label: "常见问题", href: "#faq" },
  ];
  return (
    <header
      id="top"
      className="sticky top-0 z-50 border-b border-slate-100 bg-white/80 backdrop-blur-md"
    >
      <nav className="section flex h-16 items-center justify-between">
        <Logo />
        <div className="hidden items-center gap-8 md:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-sm font-medium text-ink-muted transition hover:text-brand"
            >
              {l.label}
            </a>
          ))}
        </div>
        <div className="hidden md:block">
          <a href="#pricing" className="btn-primary h-10 px-5 text-sm">
            升级 Pro
          </a>
        </div>
        <button className="md:hidden" onClick={() => setOpen((v) => !v)}>
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </nav>
      {open && (
        <div className="border-t border-slate-100 bg-white px-5 py-3 md:hidden">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="block py-2 text-sm font-medium text-ink-muted"
            >
              {l.label}
            </a>
          ))}
          <a href="#pricing" className="btn-primary mt-2 h-10 w-full text-sm">
            升级 Pro
          </a>
        </div>
      )}
    </header>
  );
}

function Hero() {
  return (
    <section id="download" className="hero-gradient relative overflow-hidden pb-16 pt-14 sm:pt-20 scroll-mt-16">
      <div className="section relative text-center">
        <div className="mx-auto inline-flex">
          <span className="eyebrow">
            <Sparkles className="h-4 w-4" /> 基于十万 Star 开源引擎 · 全平台支持
          </span>
        </div>
        <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight text-ink sm:text-5xl md:text-6xl">
          万能视频下载
          <span className="bg-gradient-to-r from-brand to-[#6D5DFB] bg-clip-text text-transparent">
            ，一键到本地
          </span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-ink-muted sm:text-lg">
          全平台 · 高清多档位 · 手机电脑随时随地。粘贴链接，快速解析，保存你想要的视频。
        </p>

        <div className="mt-9">
          <Downloader />
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-ink-muted">
          {["免费使用", "无需安装", "多平台", "AI 分析"].map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <Check className="h-4 w-4 text-brand" /> {t}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function Platforms() {
  return (
    <section className="border-y border-slate-100 bg-slate-50/50 py-8">
      <div className="section">
        <p className="text-center text-sm font-medium text-ink-muted">
          已支持上千个主流平台，覆盖你常用的每一个
        </p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
          {PLATFORMS.map((p) => (
            <span
              key={p}
              className="inline-flex items-center gap-1.5 text-base font-semibold text-slate-400 transition hover:text-ink"
            >
              {p === "YouTube" && <Youtube className="h-5 w-5" />}
              {p.includes("抖音") && <Music2 className="h-5 w-5" />}
              {p === "哔哩哔哩" && <Play className="h-5 w-5" />}
              {p}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function Steps() {
  return (
    <section id="steps" className="py-20">
      <div className="section">
        <SectionTitle eyebrow="简单三步" title="下载视频，从未如此简单" />
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <div key={s.num} className="relative">
              <div className="card h-full p-7">
                <span className="text-4xl font-extrabold text-brand-100">{s.num}</span>
                <h3 className="mt-3 text-lg font-bold text-ink">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-muted">{s.desc}</p>
              </div>
              {i < STEPS.length - 1 && (
                <div className="absolute -right-3 top-1/2 hidden h-6 w-6 -translate-y-1/2 text-brand-100 md:block">
                  <ChevronDown className="h-6 w-6 -rotate-90" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="bg-slate-50/50 py-20">
      <div className="section">
        <SectionTitle
          eyebrow="为什么选择我们"
          title="不止能下载，更要下得爽"
          subtitle="把复杂留给我们，把简单留给你。每一个细节，都为更好的下载体验而打磨。"
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="card group p-7 transition-all duration-200 hover:-translate-y-1 hover:shadow-cardHover"
            >
              <span className="grid h-12 w-12 place-items-center rounded-xl bg-brand-50 text-brand transition group-hover:bg-brand group-hover:text-white">
                <f.icon className="h-6 w-6" />
              </span>
              <h3 className="mt-4 text-lg font-bold text-ink">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section id="pricing" className="py-16">
      <div className="section max-w-6xl">
        <SectionTitle
          eyebrow="会员定价"
          title="选择适合你的方案"
          subtitle="免费即可上手；Pro / 旗舰为产品规划展示，当前版本下载与 AI 分析均可免费体验。"
        />
        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className={`relative flex min-w-0 flex-col rounded-xl p-4 transition-all duration-200 sm:p-5 ${
                p.highlight
                  ? "border-2 border-brand bg-white shadow-cardHover"
                  : "card hover:shadow-cardHover"
              }`}
            >
              {p.highlight && (
                <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gradient-to-r from-brand to-[#6D5DFB] px-3 py-0.5 text-[10px] font-semibold text-white shadow-glow">
                  最受欢迎
                </span>
              )}
              <h3 className="text-base font-bold text-ink">{p.name}</h3>
              <p className="mt-0.5 line-clamp-2 text-xs text-ink-muted">{p.desc}</p>
              <div className="mt-3 flex items-end gap-1">
                <span className="text-2xl font-extrabold text-ink sm:text-3xl">{p.price}</span>
                <span className="mb-0.5 text-xs text-ink-muted">{p.period}</span>
              </div>
              <ul className="mt-4 flex-1 space-y-1.5 text-xs sm:text-sm">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-1.5 text-ink">
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />
                    <span className="leading-snug">{f}</span>
                  </li>
                ))}
              </ul>
              <a
                href={p.ctaHref}
                className={`mt-5 flex h-9 w-full items-center justify-center text-sm sm:h-10 ${
                  p.highlight ? "btn-primary" : "btn-ghost"
                }`}
              >
                {p.cta}
              </a>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-xs leading-relaxed text-slate-400">
          * 定价与会员权益为产品规划展示；标 * 项尚未接入限流，当前版本下载功能完全免费开放体验。
        </p>
      </div>
    </section>
  );
}

function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="bg-slate-50/50 py-20">
      <div className="section max-w-3xl">
        <SectionTitle eyebrow="常见问题" title="你可能想知道的" />
        <div className="mt-10 space-y-3">
          {FAQS.map((item, i) => {
            const active = open === i;
            return (
              <div key={i} className="card overflow-hidden">
                <button
                  onClick={() => setOpen(active ? null : i)}
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                >
                  <span className="text-base font-semibold text-ink">{item.q}</span>
                  <ChevronDown
                    className={`h-5 w-5 shrink-0 text-brand transition-transform ${
                      active ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {active && (
                  <p className="px-6 pb-5 text-sm leading-relaxed text-ink-muted">{item.a}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="py-20">
      <div className="section">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand to-[#6D5DFB] px-8 py-14 text-center shadow-glow">
          <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/10" />
          <div className="pointer-events-none absolute -bottom-12 -left-8 h-48 w-48 rounded-full bg-white/10" />
          <h2 className="relative mx-auto max-w-2xl text-3xl font-extrabold text-white sm:text-4xl">
            现在就保存你想要的视频
          </h2>
          <p className="relative mx-auto mt-4 max-w-xl text-white/90">
            无需注册、无需安装，粘贴链接即可开始。把每一个精彩瞬间留在本地。
          </p>
          <a
            href="#download"
            className="btn-pill relative mt-8 h-12 bg-white px-8 text-base font-semibold text-brand hover:-translate-y-0.5"
          >
            <Download className="h-5 w-5" /> 立即免费下载
          </a>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-100 bg-white py-10">
      <div className="section">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <Logo />
          <p className="text-sm text-ink-muted">
            {SITE_NAME} · 全平台 · 高清多档位
          </p>
        </div>
        <div className="mt-8 rounded-xl bg-slate-50 px-5 py-4 text-center text-xs leading-relaxed text-slate-400">
          免责声明：本工具仅供个人学习与合规使用，请勿用于侵犯他人版权或违反平台服务条款的用途。
          下载内容的使用责任由用户自行承担，本站不存储任何用户下载的视频文件。
        </div>
        <p className="mt-6 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} {SITE_NAME} · Powered by yt-dlp
        </p>
      </div>
    </footer>
  );
}

function SectionTitle({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="text-center">
      <span className="eyebrow">{eyebrow}</span>
      <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">{title}</h2>
      {subtitle && (
        <p className="mx-auto mt-3 max-w-2xl text-base text-ink-muted">{subtitle}</p>
      )}
    </div>
  );
}
