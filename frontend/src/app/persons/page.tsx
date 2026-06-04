"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Search,
  Upload,
  UserPlus,
} from "lucide-react";
import { api } from "@/lib/api";
import type { FaceImportStatus, Person, PersonImportResult } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PersonFormDialog } from "@/components/person-form";

const PAGE_SIZE = 100;

export default function PersonsPage() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [hasNext, setHasNext] = useState(false);
  const [open, setOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const load = async (query = q, nextPage = page) => {
    setLoading(true);
    try {
      const term = query.trim() || undefined;
      const [rows, c] = await Promise.all([
        api.listPersons({ q: term, limit: PAGE_SIZE + 1, offset: nextPage * PAGE_SIZE }),
        api.countPersons(term),
      ]);
      setHasNext(rows.length > PAGE_SIZE);
      setPersons(rows.slice(0, PAGE_SIZE));
      setTotal(c.count);
    } finally {
      setLoading(false);
    }
  };

  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);

  useEffect(() => {
    load("", 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const search = () => {
    setPage(0);
    load(q, 0);
  };

  const movePage = (nextPage: number) => {
    setPage(nextPage);
    load(q, nextPage);
  };

  const firstNo = page * PAGE_SIZE + 1;
  const lastNo = page * PAGE_SIZE + persons.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">人物</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4" /> 取り込み
          </Button>
          <Button onClick={() => setOpen(true)}>
            <UserPlus className="h-4 w-4" /> 登録
          </Button>
        </div>
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="名前・ニックネームで検索"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
        </div>
        <Button variant="outline" onClick={search} disabled={loading}>
          検索
        </Button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {persons.length === 0 ? "0件" : `${firstNo}-${lastNo} / 全${total}件`}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(0)}
            disabled={page === 0 || loading}
            title="最初のページ"
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(page - 1)}
            disabled={page === 0 || loading}
          >
            <ChevronLeft className="h-4 w-4" /> 前へ
          </Button>
          <span className="min-w-20 text-center text-sm text-muted-foreground">
            {page + 1} / {lastPage + 1}ページ
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(page + 1)}
            disabled={!hasNext || loading}
          >
            次へ <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => movePage(lastPage)}
            disabled={page >= lastPage || loading}
            title="最後のページ"
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {persons.length === 0 ? (
        <p className="text-muted-foreground">該当なし</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {persons.map((p) => (
            <Link key={p.id} href={`/persons/${p.id}`}>
              <Card className="h-full transition-colors hover:bg-accent">
                <CardContent className="space-y-2 p-4">
                  <div className="flex items-baseline gap-2">
                    <span className="font-semibold">{p.name}</span>
                    {p.nicknames.length > 0 && (
                      <span className="text-sm text-muted-foreground">
                        ({p.nicknames.join(" / ")})
                      </span>
                    )}
                  </div>
                  {p.relation && <p className="text-sm text-muted-foreground">{p.relation}</p>}
                  <div className="flex flex-wrap gap-1">
                    {p.tags.map((t) => (
                      <Badge key={t.id} variant="secondary">
                        {t.name}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <PersonFormDialog
        open={open}
        onClose={() => setOpen(false)}
        onDone={() => {
          setOpen(false);
          load(q, page);
        }}
      />
      <ImportPersonsDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onDone={() => load(q, page)}
      />
    </div>
  );
}

function ImportPersonsDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<PersonImportResult | null>(null);
  const [faceStatus, setFaceStatus] = useState<FaceImportStatus | null>(null);

  // 参照顔取込が進行中はポーリング
  useEffect(() => {
    if (!faceStatus || faceStatus.pending === 0) return;
    const t = setInterval(() => {
      api.faceImportStatus().then(setFaceStatus).catch(() => {});
    }, 3000);
    return () => clearInterval(t);
  }, [faceStatus]);

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    setFaceStatus(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const imported = await api.importPersons(form);
      setResult(imported);
      onDone();
      if (imported.face_queued > 0) {
        setFaceStatus(await api.faceImportStatus());
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const retryFaces = async () => {
    setFaceStatus(await api.retryFaces());
  };

  return (
    <Dialog open={open} onClose={onClose} title="友達CSVを取り込む">
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="friend-csv">CSVファイル</Label>
          <Input
            id="friend-csv"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        {result && (
          <div className="rounded-md bg-muted p-3 text-sm">
            作成 {result.created} / 更新 {result.updated} / スキップ {result.skipped}
            {result.face_queued > 0 && <> / 参照顔予約 {result.face_queued}</>}
            {result.errors.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-destructive">
                {result.errors.slice(0, 5).map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {faceStatus && (
          <div className="space-y-2 rounded-md border p-3 text-sm">
            <p className="font-medium">
              参照顔取込（img_url）
              {faceStatus.pending > 0 ? "：処理中…" : "：完了"}
            </p>
            <p className="text-muted-foreground">
              残り {faceStatus.pending} / 完了 {faceStatus.done} / 失敗 {faceStatus.failed}
            </p>
            {faceStatus.pending === 0 && faceStatus.failed > 0 && (
              <Button variant="outline" size="sm" onClick={retryFaces}>
                失敗 {faceStatus.failed} 件を再試行
              </Button>
            )}
          </div>
        )}
        {err && <p className="text-sm text-destructive">{err}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            閉じる
          </Button>
          <Button onClick={submit} disabled={!file || busy}>
            <Upload className="h-4 w-4" /> {busy ? "取り込み中..." : "取り込む"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
