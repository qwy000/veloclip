import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { syncCheckoutSession } from "../lib/auth";

export default function BillingSuccessPage() {
  const { refreshUser, user } = useAuth();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [refreshing, setRefreshing] = useState(true);
  const [syncMessage, setSyncMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function syncMembership() {
      try {
        if (sessionId) {
          const result = await syncCheckoutSession(sessionId);
          if (!cancelled) setSyncMessage(result.message);
          if (result.status === "pending" && !cancelled) {
            await new Promise((r) => setTimeout(r, 2000));
            const retry = await syncCheckoutSession(sessionId);
            if (!cancelled) setSyncMessage(retry.message);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setSyncMessage(err instanceof Error ? err.message : "同步会员状态失败");
        }
      } finally {
        if (!cancelled) {
          await refreshUser();
          setRefreshing(false);
        }
      }
    }

    syncMembership();
    return () => {
      cancelled = true;
    };
  }, [sessionId, refreshUser]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="card max-w-md p-8 text-center">
        <CheckCircle2 className="mx-auto h-14 w-14 text-green-500" />
        <h1 className="mt-4 text-2xl font-bold text-ink">支付成功</h1>
        <p className="mt-2 text-sm text-ink-muted">
          {syncMessage || "会员权益将在 Stripe 确认后生效（通常数秒内）。"}
        </p>
        {refreshing ? (
          <div className="mt-6 flex items-center justify-center gap-2 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> 正在同步会员状态…
          </div>
        ) : user ? (
          <p className="mt-6 rounded-lg bg-brand-50 px-4 py-3 text-sm text-brand">
            当前会员：{user.membership.plan_label}
            {user.membership.expires_at && (
              <span className="block text-xs text-ink-muted mt-1">
                到期：{new Date(user.membership.expires_at).toLocaleDateString("zh-CN")}
              </span>
            )}
          </p>
        ) : null}
        <Link to="/#pricing" className="btn-primary mt-8 inline-flex h-11 px-6">
          返回首页
        </Link>
      </div>
    </div>
  );
}

export function BillingCancelPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="card max-w-md p-8 text-center">
        <XCircle className="mx-auto h-14 w-14 text-slate-400" />
        <h1 className="mt-4 text-2xl font-bold text-ink">支付已取消</h1>
        <p className="mt-2 text-sm text-ink-muted">你未完成付款，可随时返回重新选择方案。</p>
        <Link to="/#pricing" className="btn-primary mt-8 inline-flex h-11 px-6">
          返回定价
        </Link>
      </div>
    </div>
  );
}
