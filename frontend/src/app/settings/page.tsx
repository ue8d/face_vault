"use client";
import { useEffect, useMemo, useState } from "react";
import { Save, RotateCcw, Plus, Trash2, Check, Layers } from "lucide-react";
import { api, getCurrentEnvId, setCurrentEnvId } from "@/lib/api";
import type { Environment, SettingItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";

function EnvironmentsCard() {
  const [envs, setEnvs] = useState<Environment[]>([]);
  const [names, setNames] = useState<Record<number, string>>({});
  const [newName, setNewName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const currentId = getCurrentEnvId();

  const load = async () => {
    try {
      const list = await api.listEnvironments();
      setEnvs(list);
      setNames(Object.fromEntries(list.map((e) => [e.id, e.name])));
    } catch (e) {
      setMsg(`読み込み失敗: ${(e as Error).message}`);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!newName.trim()) return;
    try {
      const env = await api.createEnvironment(newName.trim());
      setNewName("");
      setMsg(`環境「${env.name}」を追加しました`);
      await load();
    } catch (e) {
      setMsg(`追加失敗: ${(e as Error).message}`);
    }
  };

  const rename = async (env: Environment) => {
    const name = (names[env.id] ?? "").trim();
    if (!name || name === env.name) return;
    try {
      await api.renameEnvironment(env.id, name);
      setMsg(`「${env.name}」→「${name}」に変更しました`);
      await load();
    } catch (e) {
      setMsg(`変更失敗: ${(e as Error).message}`);
    }
  };

  const remove = async (env: Environment) => {
    const ok = window.confirm(
      `環境「${env.name}」を削除します。\n` +
        `人物 ${env.person_count} 件・写真 ${env.photo_count} 件を含む` +
        `この環境の全データ（画像ファイル含む）が完全に削除されます。\n` +
        `この操作は取り消せません。実行しますか？`,
    );
    if (!ok) return;
    try {
      await api.deleteEnvironment(env.id);
      if (currentId === env.id) {
        setCurrentEnvId(null);
        window.location.reload();
        return;
      }
      setMsg(`環境「${env.name}」を削除しました`);
      await load();
    } catch (e) {
      setMsg(`削除失敗: ${(e as Error).message}`);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers className="h-5 w-5" /> 環境管理
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          環境ごとに人物・写真・イベント・タグ・APIログを完全分離。
          左メニューのセレクタで切替。削除は配下の全データを消す（復元不可）。
        </p>
        {msg && <p className="text-sm text-primary">{msg}</p>}
        <div className="space-y-2">
          {envs.map((env) => (
            <div key={env.id} className="flex items-center gap-2">
              <Input
                value={names[env.id] ?? env.name}
                onChange={(e) =>
                  setNames((s) => ({ ...s, [env.id]: e.target.value }))
                }
                className="max-w-xs"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => rename(env)}
                disabled={(names[env.id] ?? env.name).trim() === env.name}
                title="名前を保存"
              >
                <Check className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground">
                人物 {env.person_count} / 写真 {env.photo_count}
              </span>
              {currentId === env.id && <Badge>使用中</Badge>}
              <button
                onClick={() => remove(env)}
                disabled={envs.length <= 1}
                className="ml-auto text-muted-foreground hover:text-destructive disabled:opacity-30"
                title={envs.length <= 1 ? "最後の環境は削除不可" : "環境を削除"}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="新しい環境名"
            className="max-w-xs"
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
          <Button variant="outline" size="sm" onClick={create} disabled={!newName.trim()}>
            <Plus className="h-4 w-4" /> 追加
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const [items, setItems] = useState<SettingItem[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const it = await api.listSettings();
      setItems(it);
      // secret は常に空で初期化（マスク）
      setVals(Object.fromEntries(it.map((i) => [i.key, i.type === "secret" ? "" : i.value])));
    } catch (e) {
      setItems([]);
      setVals({});
      setMsg(`読み込み失敗: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const groups = useMemo(() => {
    const m: Record<string, SettingItem[]> = {};
    for (const i of items) (m[i.group] ??= []).push(i);
    return m;
  }, [items]);

  const save = async () => {
    setBusy(true);
    setMsg(null);
    const orig = Object.fromEntries(items.map((i) => [i.key, i]));
    const payload: Record<string, string> = {};
    for (const [key, v] of Object.entries(vals)) {
      const it = orig[key];
      if (!it) continue;
      if (it.type === "secret") {
        if (v !== "") payload[key] = v; // 入力時のみ更新
      } else if (v !== it.value) {
        payload[key] = v;
      }
    }
    try {
      if (Object.keys(payload).length === 0) {
        setMsg("変更なし");
      } else {
        setItems(await api.updateSettings(payload));
        setMsg(`${Object.keys(payload).length}件 保存しました`);
      }
      await load();
    } catch (e) {
      setMsg(`失敗: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const reset = async (key: string) => {
    await api.updateSettings({ [key]: "" }); // env/デフォルトへ
    await load();
    setMsg(`${key} をデフォルトに戻しました`);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">設定</h1>
        <Button onClick={save} disabled={busy || loading || items.length === 0}>
          <Save className="h-4 w-4" /> {busy ? "保存中…" : "保存"}
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        DB管理の設定。空にして保存（またはリセット）でenv/デフォルトに戻る。
        DB接続・ポートは起動前必須のためenv管理（ここには出ない）。
      </p>
      {msg && <p className="text-sm text-primary">{msg}</p>}

      <EnvironmentsCard />

      {loading && items.length > 0 && <LoadingState compact label="設定を更新中..." />}

      {loading && items.length === 0 ? (
        <LoadingState label="設定を読み込み中..." />
      ) : Object.keys(groups).length === 0 ? (
        <p className="text-muted-foreground">設定項目なし。</p>
      ) : (
        Object.entries(groups).map(([group, gItems]) => (
          <Card key={group}>
            <CardHeader>
              <CardTitle>{group}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {gItems.map((it) => (
                <div key={it.key} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <Label>{it.label}</Label>
                    <div className="flex items-center gap-2">
                      <Badge variant={it.source === "db" ? "default" : "secondary"}>
                        {it.source}
                      </Badge>
                      {it.type === "secret" && it.is_set && (
                        <Badge variant="outline">設定済み</Badge>
                      )}
                      <button
                        onClick={() => reset(it.key)}
                        className="text-muted-foreground hover:text-foreground"
                        title="デフォルトに戻す"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  {it.type === "bool" ? (
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={(vals[it.key] ?? "false") === "true"}
                        onChange={(e) =>
                          setVals((s) => ({ ...s, [it.key]: e.target.checked ? "true" : "false" }))
                        }
                      />
                      {(vals[it.key] ?? "false") === "true" ? "有効" : "無効"}
                    </label>
                  ) : (
                    <Input
                      type={
                        it.type === "secret" ? "password" : it.type === "str" ? "text" : "number"
                      }
                      value={vals[it.key] ?? ""}
                      onChange={(e) => setVals((s) => ({ ...s, [it.key]: e.target.value }))}
                      placeholder={
                        it.type === "secret"
                          ? it.is_set
                            ? "設定済み（変更時のみ入力）"
                            : "未設定"
                          : ""
                      }
                      className="font-mono"
                    />
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
