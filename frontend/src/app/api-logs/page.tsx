"use client";
import { useEffect, useState } from "react";
import { Trash2, Webhook } from "lucide-react";
import { api, apiQueryCropUrl } from "@/lib/api";
import type { ApiQuery } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { fmtDate } from "@/lib/utils";

export default function ApiLogsPage() {
  const [items, setItems] = useState<ApiQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      setItems(await api.listApiQueries({ limit: 200 }));
    } catch (e) {
      setErr((e as Error).message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const remove = async (id: number) => {
    if (!confirm("この受信画像と判定記録を削除しますか？")) return;
    setBusyId(id);
    try {
      await api.deleteApiQuery(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Webhook className="h-5 w-5" />
        <h1 className="text-2xl font-bold">API 受信ログ</h1>
      </div>
      <p className="text-sm text-muted-foreground">
        外部API（顔判定のみ・学習なし）で受け取った画像と判定結果。任意で削除できます。
      </p>

      {err && <p className="text-sm text-destructive">{err}</p>}

      {loading && items.length === 0 ? (
        <LoadingState label="読み込み中..." />
      ) : items.length === 0 ? (
        <p className="text-muted-foreground">受信ログなし。</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((q) => (
            <div key={q.id} className="flex flex-col overflow-hidden rounded-lg border bg-card">
              <div className="relative aspect-video overflow-hidden bg-muted">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={apiQueryCropUrl(q.id)}
                  alt={`api query ${q.id}`}
                  className="h-full w-full object-cover"
                  onError={(e) => (e.currentTarget.style.display = "none")}
                />
                <Badge className="absolute right-1 top-1" variant="secondary">
                  顔{q.faces_detected}
                </Badge>
              </div>
              <div className="flex flex-1 flex-col gap-2 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{fmtDate(q.created_at)}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busyId === q.id}
                    onClick={() => remove(q.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                {q.note && <p className="truncate text-xs text-muted-foreground">{q.note}</p>}
                <div className="space-y-1.5">
                  {q.result.length === 0 && (
                    <p className="text-xs text-muted-foreground">顔未検出</p>
                  )}
                  {q.result.map((face, i) => {
                    const top = face.candidates[0];
                    return (
                      <div key={i} className="rounded-md border px-2 py-1 text-xs">
                        {top ? (
                          <span className={top.matched ? "font-medium" : "text-muted-foreground"}>
                            {top.matched ? top.name : `未一致（最有力: ${top.name}）`}
                            <span className="ml-1 text-muted-foreground">
                              {(top.score * 100).toFixed(1)}%
                            </span>
                          </span>
                        ) : (
                          <span className="text-muted-foreground">候補なし</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
