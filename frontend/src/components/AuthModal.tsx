import { useEffect, useState } from "react";
import { Loader2, Mail, LockKeyhole, ShieldCheck, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  authLogin,
  authRegister,
  authResendVerification,
  authVerifyEmail,
  formatAuthMessage,
  type AuthMessageResponse,
} from "../lib/auth";

type Mode = "login" | "register" | "verify";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  initialMode?: Mode;
  onSuccess?: () => void;
}

export default function AuthModal({
  open,
  onClose,
  initialMode = "login",
  onSuccess,
}: AuthModalProps) {
  const { login } = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setMode(initialMode);
      setError("");
      setMessage("");
      setDevCode(null);
    }
  }, [open, initialMode]);

  if (!open) return null;

  const resetMessages = () => {
    setError("");
    setMessage("");
    setDevCode(null);
  };

  const applyVerificationResponse = (res: AuthMessageResponse) => {
    setMessage(formatAuthMessage(res));
    if (res.dev_code) {
      setDevCode(res.dev_code);
      setCode(res.dev_code);
    }
    setMode("verify");
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    setLoading(true);
    try {
      const res = await authRegister(email, password);
      applyVerificationResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    setLoading(true);
    try {
      const res = await authVerifyEmail(email, code);
      login(res);
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    setLoading(true);
    try {
      const res = await authLogin(email, password);
      login(res);
      onSuccess?.();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "登录失败";
      setError(msg);
      if (msg.includes("验证邮箱")) {
        setMode("verify");
        setMessage("请输入验证码；可点「重新发送验证码」获取（开发模式会显示在页面上）");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    resetMessages();
    setLoading(true);
    try {
      const res = await authResendVerification(email);
      if (res.already_verified) {
        setMessage(res.message);
        setMode("login");
        return;
      }
      applyVerificationResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setLoading(false);
    }
  };

  const title = {
    login: "登录 VeloClip",
    register: "注册账号",
    verify: "验证邮箱",
  }[mode];

  const subtitle = {
    login: "请使用注册邮箱和密码登录",
    register: "先注册账号，再完成邮箱验证后登录",
    verify: "输入邮箱验证码完成登录",
  }[mode];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl shadow-slate-950/20">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand to-[#6D5DFB]" />
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          aria-label="关闭登录窗口"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="px-6 pb-6 pt-8">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand">
            {mode === "verify" ? <ShieldCheck className="h-6 w-6" /> : <Mail className="h-6 w-6" />}
          </div>
          <h2 className="mt-4 text-center text-xl font-bold text-ink">{title}</h2>
          <p className="mt-1 text-center text-sm text-ink-muted">{subtitle}</p>

          {message && (
            <p className="mt-5 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand whitespace-pre-wrap">{message}</p>
          )}
          {devCode && mode === "verify" && (
            <p className="mt-3 rounded-xl border border-dashed border-brand/40 bg-slate-50 px-3 py-2 text-center text-sm">
              开发模式验证码：<span className="font-mono text-lg font-bold text-brand">{devCode}</span>
            </p>
          )}
          {error && (
            <p className="mt-5 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          {mode === "login" && (
            <form onSubmit={handleLogin} className="mt-5 space-y-4">
              <Field label="邮箱" type="email" value={email} onChange={setEmail} placeholder="请输入注册邮箱" required />
              <Field label="密码" type="password" value={password} onChange={setPassword} placeholder="请输入账号密码" required />
              <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
                {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "邮箱密码登录"}
              </button>
              <div className="flex items-center justify-between border-t border-slate-100 pt-4 text-sm">
                <span className="text-ink-muted">还没有账号？</span>
                <button type="button" className="font-medium text-brand" onClick={() => { resetMessages(); setMode("register"); }}>
                  先注册账号
                </button>
              </div>
              <button
                type="button"
                className="w-full text-sm text-brand"
                onClick={() => {
                  resetMessages();
                  setMode("verify");
                  setMessage("请输入验证码；没有收到可点「重新发送验证码」");
                }}
              >
                已注册但未验证邮箱
              </button>
            </form>
          )}

          {mode === "register" && (
            <form onSubmit={handleRegister} className="mt-5 space-y-4">
              <Field label="邮箱" type="email" value={email} onChange={setEmail} placeholder="用于登录和接收验证码" required />
              <Field label="密码（至少 8 位）" type="password" value={password} onChange={setPassword} placeholder="设置登录密码" required />
              <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
                {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "注册并获取验证码"}
              </button>
              <button type="button" className="w-full text-sm text-brand" onClick={() => { resetMessages(); setMode("login"); }}>
                已有账号，去登录
              </button>
              <p className="text-xs leading-relaxed text-ink-muted">
                若提示「已注册但未验证」，再次点击注册会用新密码重发验证码。
              </p>
            </form>
          )}

          {mode === "verify" && (
            <form onSubmit={handleVerify} className="mt-5 space-y-4">
              <Field label="邮箱" type="email" value={email} onChange={setEmail} placeholder="请输入注册邮箱" required />
              <Field label="6 位验证码" value={code} onChange={setCode} placeholder="请输入邮箱验证码" required maxLength={6} />
              <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
                {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "验证并登录"}
              </button>
              <button type="button" className="w-full text-sm text-brand" onClick={handleResend} disabled={loading}>
                重新发送验证码
              </button>
              <div className="flex justify-between border-t border-slate-100 pt-4 text-sm">
                <button type="button" className="text-brand" onClick={() => { resetMessages(); setMode("login"); }}>
                  返回登录
                </button>
                <button type="button" className="text-brand" onClick={() => { resetMessages(); setMode("register"); }}>
                  返回注册
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
  maxLength,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  maxLength?: number;
  placeholder?: string;
}) {
  const Icon = type === "password" ? LockKeyhole : type === "email" ? Mail : ShieldCheck;

  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{label}</span>
      <span className="mt-1.5 flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm transition focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/20">
        <Icon className="h-4 w-4 shrink-0 text-slate-400" />
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          maxLength={maxLength}
          placeholder={placeholder}
          className="h-full min-w-0 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-slate-400"
        />
      </span>
    </label>
  );
}
