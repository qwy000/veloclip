import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  authLogin,
  authMagicLink,
  authRegister,
  authResendVerification,
  authVerifyEmail,
  formatAuthMessage,
  type AuthMessageResponse,
} from "../lib/auth";

type Mode = "login" | "register" | "verify" | "magic";

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

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    resetMessages();
    setLoading(true);
    try {
      const res = await authMagicLink(email);
      setMessage(res.message + "（开发模式下链接在后端控制台）");
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
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

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4">
      <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-600"
        >
          <X className="h-5 w-5" />
        </button>

        <h2 className="text-xl font-bold text-ink">
          {mode === "login" && "登录 VeloClip"}
          {mode === "register" && "注册账号"}
          {mode === "verify" && "验证邮箱"}
          {mode === "magic" && "魔法链接登录"}
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          购买会员需先注册并验证邮箱
        </p>

        {message && (
          <p className="mt-4 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand whitespace-pre-wrap">{message}</p>
        )}
        {devCode && mode === "verify" && (
          <p className="mt-3 rounded-lg border border-dashed border-brand/40 bg-slate-50 px-3 py-2 text-center text-sm">
            开发模式验证码：<span className="font-mono text-lg font-bold text-brand">{devCode}</span>
          </p>
        )}
        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        {mode === "login" && (
          <form onSubmit={handleLogin} className="mt-5 space-y-4">
            <Field label="邮箱" type="email" value={email} onChange={setEmail} required />
            <Field label="密码" type="password" value={password} onChange={setPassword} required />
            <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
              {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "登录"}
            </button>
            <div className="flex justify-between text-sm">
              <button type="button" className="text-brand" onClick={() => { resetMessages(); setMode("register"); }}>
                注册
              </button>
              <button type="button" className="text-brand" onClick={() => { resetMessages(); setMode("magic"); }}>
                魔法链接登录
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
              已有账号，去验证邮箱
            </button>
          </form>
        )}

        {mode === "register" && (
          <form onSubmit={handleRegister} className="mt-5 space-y-4">
            <Field label="邮箱" type="email" value={email} onChange={setEmail} required />
            <Field label="密码（至少 8 位）" type="password" value={password} onChange={setPassword} required />
            <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
              {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "注册"}
            </button>
            <button type="button" className="text-sm text-brand" onClick={() => { resetMessages(); setMode("login"); }}>
              已有账号？登录
            </button>
            <p className="text-xs text-ink-muted">
              若提示「已注册但未验证」，再次点击注册会用新密码重发验证码。
            </p>
          </form>
        )}

        {mode === "verify" && (
          <form onSubmit={handleVerify} className="mt-5 space-y-4">
            <Field label="邮箱" type="email" value={email} onChange={setEmail} required />
            <Field label="6 位验证码" value={code} onChange={setCode} required maxLength={6} />
            <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
              {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "验证并登录"}
            </button>
            <button type="button" className="text-sm text-brand" onClick={handleResend} disabled={loading}>
              重新发送验证码
            </button>
            <div className="flex justify-between border-t border-slate-100 pt-3 text-sm">
              <button type="button" className="text-brand" onClick={() => { resetMessages(); setMode("login"); }}>
                ← 返回登录
              </button>
              <button type="button" className="text-brand" onClick={() => { resetMessages(); setMode("register"); }}>
                返回注册 →
              </button>
            </div>
          </form>
        )}

        {mode === "magic" && (
          <form onSubmit={handleMagicLink} className="mt-5 space-y-4">
            <Field label="邮箱" type="email" value={email} onChange={setEmail} required />
            <button type="submit" disabled={loading} className="btn-primary h-11 w-full">
              {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : "发送登录链接"}
            </button>
            <button type="button" className="text-sm text-brand" onClick={() => { resetMessages(); setMode("login"); }}>
              返回密码登录
            </button>
          </form>
        )}
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
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  maxLength?: number;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        maxLength={maxLength}
        className="mt-1.5 h-11 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
      />
    </label>
  );
}
