"use client";
import { useEffect, useState } from "react";
import { Layers } from "lucide-react";
import { api, getCurrentEnvId, setCurrentEnvId } from "@/lib/api";
import type { Environment } from "@/lib/types";

/** 環境（テナント）切替セレクタ。切替時は全データ再取得のためリロード。 */
export function EnvSwitcher({ compact = false }: { compact?: boolean }) {
  const [envs, setEnvs] = useState<Environment[]>([]);
  const [current, setCurrent] = useState<number | null>(null);

  useEffect(() => {
    api
      .listEnvironments()
      .then((list) => {
        setEnvs(list);
        const saved = getCurrentEnvId();
        const valid = saved != null && list.some((e) => e.id === saved);
        const id = valid ? saved : list[0]?.id ?? null;
        setCurrent(id);
        if (!valid && id != null) setCurrentEnvId(id);
      })
      .catch(() => {});
  }, []);

  if (envs.length === 0) return null;

  const onChange = (id: number) => {
    setCurrentEnvId(id);
    setCurrent(id);
    window.location.reload();
  };

  return (
    <label
      className={
        compact
          ? "flex items-center gap-1"
          : "mb-4 flex items-center gap-2 px-2"
      }
      title="環境（データ分離単位）"
    >
      <Layers className="h-4 w-4 shrink-0 text-muted-foreground" />
      <select
        value={current ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded-md border bg-background px-2 py-1 text-sm"
      >
        {envs.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
          </option>
        ))}
      </select>
    </label>
  );
}
