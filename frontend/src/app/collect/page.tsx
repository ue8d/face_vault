"use client";
import { useEffect, useState } from "react";
import { Plus, Trash2, Play, Save, DownloadCloud } from "lucide-react";
import { api } from "@/lib/api";
import type { CollectSource, CollectSourceInput, CrawlMode } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";

const MODE_LABEL: Record<CrawlMode, string> = {
  page: "ページのみ",
  shallow: "1階層クロール",
  domain: "ドメイン巡回",
};

/** スキーム未指定なら https:// を補う（追加時の取りこぼし防止）。 */
function normalizeUrl(url: string): string {
  const u = url.trim();
  if (!u) return u;
  if (/^https?:\/\//i.test(u)) return u;
  return `https://${u}`;
}

const EMPTY: CollectSourceInput = {
  name: "",
  start_url: "",
  crawl_mode: "page",
  max_pages: 20,
  max_images: 100,
  same_domain_only: true,
  respect_robots: true,
  enabled: true,
  interval_minutes: 0,
};

export default function CollectPage() {
  const [sources, setSources] = useState<CollectSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState<CollectSourceInput>(EMPTY);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | "new" | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setSources(await api.listCollectSources());
    } catch (e) {
      setMsg(`読み込み失敗: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!creating.name.trim() || !creating.start_url.trim()) return;
    setBusy("new");
    setMsg(null);
    try {
      await api.createCollectSource({
        ...creating,
        name: creating.name.trim(),
        start_url: normalizeUrl(creating.start_url),
      });
      setCreating(EMPTY);
      setMsg("収集元を追加しました");
      await load();
    } catch (e) {
      setMsg(`追加失敗: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const saveSource = async (s: CollectSource) => {
    setBusy(s.id);
    setMsg(null);
    try {
      await api.updateCollectSource(s.id, {
        name: s.name.trim(),
        start_url: normalizeUrl(s.start_url),
        crawl_mode: s.crawl_mode,
        max_pages: s.max_pages,
        max_images: s.max_images,
        same_domain_only: s.same_domain_only,
        respect_robots: s.respect_robots,
        enabled: s.enabled,
        interval_minutes: s.interval_minutes,
      });
      setMsg("保存しました");
      await load();
    } catch (e) {
      setMsg(`保存失敗: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const run = async (s: CollectSource) => {
    setBusy(s.id);
    setMsg(`「${s.name}」を収集中…（ドメイン巡回は時間がかかります）`);
    try {
      const r = await api.runCollectSource(s.id);
      setMsg(
        `「${s.name}」完了: 発見${r.found_urls} / 新規保存${r.saved} / ` +
          `重複${r.skipped_duplicate} / 失敗${r.failed}。確認画面で照合してください。`,
      );
      await load();
    } catch (e) {
      setMsg(`収集失敗: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const remove = async (s: CollectSource) => {
    if (!window.confirm(`収集元「${s.name}」を削除しますか？（収集済み画像は残ります）`)) return;
    setBusy(s.id);
    try {
      await api.deleteCollectSource(s.id);
      await load();
    } catch (e) {
      setMsg(`削除失敗: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const patch = (id: number, p: Partial<CollectSource>) =>
    setSources((list) => list.map((s) => (s.id === id ? { ...s, ...p } : s)));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <DownloadCloud className="h-6 w-6" />
        <h1 className="text-2xl font-bold">自動収集</h1>
      </div>
      <p className="text-sm text-muted-foreground">
        登録したURL/ドメインから画像を集めて取り込みます。集めた顔は
        <strong>確認画面</strong>に未照合で入ります（人物は自動作成しません）。
        定期巡回は最小1分。収集先の規約・robots を尊重してください。
      </p>
      {msg && <p className="text-sm text-primary">{msg}</p>}

      {/* 新規追加 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">収集元を追加</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>名前</Label>
            <Input
              value={creating.name}
              onChange={(e) => setCreating((s) => ({ ...s, name: e.target.value }))}
              placeholder="例: 大学サークルのギャラリー"
            />
          </div>
          <div className="space-y-1">
            <Label>開始URL (http/https)</Label>
            <Input
              value={creating.start_url}
              onChange={(e) => setCreating((s) => ({ ...s, start_url: e.target.value }))}
              placeholder="https://example.com/gallery"
              className="font-mono"
            />
          </div>
          <div className="space-y-1">
            <Label>クロール方式</Label>
            <select
              value={creating.crawl_mode}
              onChange={(e) =>
                setCreating((s) => ({ ...s, crawl_mode: e.target.value as CrawlMode }))
              }
              className="w-full rounded-md border bg-background px-2 py-2 text-sm"
            >
              {(["page", "shallow", "domain"] as CrawlMode[]).map((m) => (
                <option key={m} value={m}>
                  {MODE_LABEL[m]}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label>最大ページ</Label>
              <Input
                type="number"
                value={creating.max_pages}
                onChange={(e) =>
                  setCreating((s) => ({ ...s, max_pages: Number(e.target.value) }))
                }
              />
            </div>
            <div className="space-y-1">
              <Label>最大枚数</Label>
              <Input
                type="number"
                value={creating.max_images}
                onChange={(e) =>
                  setCreating((s) => ({ ...s, max_images: Number(e.target.value) }))
                }
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>定期巡回（分・0=手動のみ）</Label>
            <Input
              type="number"
              min={0}
              value={creating.interval_minutes}
              onChange={(e) =>
                setCreating((s) => ({ ...s, interval_minutes: Number(e.target.value) }))
              }
            />
          </div>
          <div className="flex items-end gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={creating.same_domain_only}
                onChange={(e) =>
                  setCreating((s) => ({ ...s, same_domain_only: e.target.checked }))
                }
              />
              同一ドメインのみ
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={creating.respect_robots}
                onChange={(e) =>
                  setCreating((s) => ({ ...s, respect_robots: e.target.checked }))
                }
              />
              robots尊重
            </label>
          </div>
          <div className="sm:col-span-2">
            <Button onClick={create} disabled={busy === "new"}>
              <Plus className="h-4 w-4" /> 追加
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 一覧 */}
      {loading ? (
        <LoadingState label="読み込み中..." />
      ) : sources.length === 0 ? (
        <p className="text-muted-foreground">収集元なし。</p>
      ) : (
        <div className="space-y-3">
          {sources.map((s) => (
            <Card key={s.id}>
              <CardContent className="space-y-3 pt-6">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label>名前</Label>
                    <Input value={s.name} onChange={(e) => patch(s.id, { name: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <Label>開始URL</Label>
                    <Input
                      value={s.start_url}
                      onChange={(e) => patch(s.id, { start_url: e.target.value })}
                      className="font-mono"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>クロール方式</Label>
                    <select
                      value={s.crawl_mode}
                      onChange={(e) =>
                        patch(s.id, { crawl_mode: e.target.value as CrawlMode })
                      }
                      className="w-full rounded-md border bg-background px-2 py-2 text-sm"
                    >
                      {(["page", "shallow", "domain"] as CrawlMode[]).map((m) => (
                        <option key={m} value={m}>
                          {MODE_LABEL[m]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="space-y-1">
                      <Label>ページ</Label>
                      <Input
                        type="number"
                        value={s.max_pages}
                        onChange={(e) => patch(s.id, { max_pages: Number(e.target.value) })}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label>枚数</Label>
                      <Input
                        type="number"
                        value={s.max_images}
                        onChange={(e) => patch(s.id, { max_images: Number(e.target.value) })}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label>分間隔</Label>
                      <Input
                        type="number"
                        min={0}
                        value={s.interval_minutes}
                        onChange={(e) =>
                          patch(s.id, { interval_minutes: Number(e.target.value) })
                        }
                      />
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={s.enabled}
                      onChange={(e) => patch(s.id, { enabled: e.target.checked })}
                    />
                    有効
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={s.same_domain_only}
                      onChange={(e) => patch(s.id, { same_domain_only: e.target.checked })}
                    />
                    同一ドメインのみ
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={s.respect_robots}
                      onChange={(e) => patch(s.id, { respect_robots: e.target.checked })}
                    />
                    robots尊重
                  </label>
                  {s.last_status && (
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-xs font-semibold " +
                        (s.last_status === "error"
                          ? "bg-destructive text-destructive-foreground"
                          : "bg-secondary text-secondary-foreground")
                      }
                    >
                      {s.last_status}
                    </span>
                  )}
                  {s.last_run_at && (
                    <span className="text-xs text-muted-foreground">
                      最終: {new Date(s.last_run_at).toLocaleString()}
                    </span>
                  )}
                </div>
                {s.last_error && (
                  <p className="text-xs text-destructive">{s.last_error}</p>
                )}
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => run(s)} disabled={busy === s.id}>
                    <Play className="h-4 w-4" /> 今すぐ収集
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => saveSource(s)}
                    disabled={busy === s.id}
                  >
                    <Save className="h-4 w-4" /> 保存
                  </Button>
                  <button
                    onClick={() => remove(s)}
                    disabled={busy === s.id}
                    className="ml-auto text-muted-foreground hover:text-destructive"
                    title="削除"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
