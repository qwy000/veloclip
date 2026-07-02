import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { authVerifyMagicLink } from "../lib/auth";

export default function MagicLinkPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("链接无效");
      return;
    }
    authVerifyMagicLink(token)
      .then((res) => {
        login(res);
        navigate("/", { replace: true });
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "登录失败");
      });
  }, [params, login, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="card max-w-md p-8 text-center">
        {error ? (
          <>
            <p className="text-red-600">{error}</p>
            <a href="/" className="btn-primary mt-6 inline-flex h-11 px-6">
              返回首页
            </a>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-brand" />
            <p className="mt-4 text-sm text-ink-muted">正在登录…</p>
          </>
        )}
      </div>
    </div>
  );
}
