import { apiUrl } from "./config";

const TOKEN_KEY = "veloclip_access_token";

export interface MembershipInfo {
  plan: string;
  plan_label: string;
  expires_at?: string | null;
  is_premium: boolean;
  has_subscription?: boolean;
  can_manage_subscription?: boolean;
}

export interface UserPublic {
  id: string;
  email: string;
  email_verified: boolean;
  membership: MembershipInfo;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface AuthMessageResponse {
  message: string;
  email?: string;
  need_verify?: boolean;
  already_verified?: boolean;
  dev_code?: string | null;
}

export function formatAuthMessage(res: AuthMessageResponse): string {
  if (res.dev_code) {
    return `${res.message}（开发模式验证码：${res.dev_code}）`;
  }
  return res.message;
}

export interface BillingPlan {
  id: string;
  name: string;
  price_display: string;
  period: string;
  stripe_price_id?: string | null;
  checkout_mode?: string | null;
  currency_note?: string | null;
  renewal_note?: string | null;
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") {
      if (data.detail === "Not Found") {
        return "后端接口不存在，请确认 backend 已重启且运行在 8000（访问 /health 应含 auth 功能）";
      }
      return data.detail;
    }
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg?: string }) => d.msg).join("; ");
    return "请求失败，请稍后重试";
  } catch {
    return "请求失败，请稍后重试";
  }
}

export async function authRegister(email: string, password: string): Promise<AuthMessageResponse> {
  const res = await fetch(apiUrl("/api/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function authVerifyEmail(email: string, code: string): Promise<AuthTokenResponse> {
  const res = await fetch(apiUrl("/api/auth/verify-email"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function authResendVerification(email: string): Promise<AuthMessageResponse> {
  const res = await fetch(apiUrl("/api/auth/resend-verification"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function authLogin(email: string, password: string): Promise<AuthTokenResponse> {
  const res = await fetch(apiUrl("/api/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function authMagicLink(email: string): Promise<{ message: string }> {
  const res = await fetch(apiUrl("/api/auth/magic-link"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function authVerifyMagicLink(token: string): Promise<AuthTokenResponse> {
  const res = await fetch(apiUrl("/api/auth/magic-link/verify"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function authMe(): Promise<UserPublic> {
  const res = await fetch(apiUrl("/api/auth/me"), { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchBillingPlans(): Promise<BillingPlan[]> {
  const res = await fetch(apiUrl("/api/billing/plans"));
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createCheckout(plan: "pro" | "ultimate"): Promise<{ checkout_url: string; session_id: string }> {
  const res = await fetch(apiUrl("/api/billing/checkout"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ plan }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function syncCheckoutSession(sessionId: string): Promise<{
  status: "pending" | "synced";
  message: string;
  membership?: MembershipInfo;
}> {
  const res = await fetch(apiUrl("/api/billing/sync-checkout"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createPortal(): Promise<{ portal_url: string }> {
  const res = await fetch(apiUrl("/api/billing/portal"), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchBillingStatus(): Promise<{ membership: MembershipInfo; stripe_customer_id?: string | null }> {
  const res = await fetch(apiUrl("/api/billing/status"), { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
