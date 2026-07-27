import { useEffect, useState } from "react";
import { apiUrl } from "../lib/config";

export default function BackendHealthBanner() {
  const [warning, setWarning] = useState<string | null>(null);

  useEffect(() => {
    fetch(apiUrl("/health"))
      .then((r) => r.json())
      .then((data) => {
        const features: string[] = data?.features ?? [];
        if (!features.includes("auth")) {
          setWarning(
            "检测到 8000 端口可能是旧版后端（/health 无 auth）。请在任务管理器结束所有 python.exe 后重启 uvicorn。",
          );
        }
      })
      .catch(() => {
        setWarning("无法连接后端（8000）。请先启动：cd backend && uvicorn app.main:app --reload --port 8000");
      });
  }, []);

  if (!warning) return null;

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-800">
      {warning}
    </div>
  );
}
