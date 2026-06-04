"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Images, LinkIcon, Upload } from "lucide-react";
import { api, photoRawUrl } from "@/lib/api";
import type { EventItem, Photo } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { fmtDate } from "@/lib/utils";

const parseUrlInput = (value: string) =>
  value
    .split(/[\n,]+/)
    .map((url) => url.trim())
    .filter(Boolean);

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      setPhotos(await api.listPhotos({ limit: 500 }));
    } catch (e) {
      setErr((e as Error).message);
      setPhotos([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
    setEventsLoading(true);
    api
      .listEvents()
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setEventsLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">写真</h1>
        <Button onClick={() => setOpen(true)}>
          <Upload className="h-4 w-4" />
          取り込み
        </Button>
      </div>

      {err && <p className="text-sm text-destructive">{err}</p>}

      {loading && photos.length > 0 && <LoadingState compact label="写真を更新中..." />}

      {loading && photos.length === 0 ? (
        <LoadingState label="写真を読み込み中..." />
      ) : photos.length === 0 ? (
        <p className="text-muted-foreground">写真なし。アップロードから追加。</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {photos.map((p) => (
            <Link key={p.id} href={`/photos/${p.id}`} className="group">
              <div className="relative aspect-square overflow-hidden rounded-lg border bg-muted">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={photoRawUrl(p.id)}
                  alt={`photo ${p.id}`}
                  className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  onError={(e) => (e.currentTarget.style.display = "none")}
                />
                {p.person_links.length > 0 && (
                  <Badge className="absolute right-1 top-1" variant="secondary">
                    顔{p.person_links.length}
                  </Badge>
                )}
              </div>
              <p className="mt-1 truncate text-xs text-muted-foreground">{fmtDate(p.taken_at)}</p>
            </Link>
          ))}
        </div>
      )}

      <UploadDialog
        open={open}
        onClose={() => setOpen(false)}
        events={events}
        eventsLoading={eventsLoading}
        onImported={load}
      />
    </div>
  );
}

function UploadDialog({
  open,
  onClose,
  events,
  eventsLoading,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  events: EventItem[];
  eventsLoading: boolean;
  onImported: () => void;
}) {
  const [mode, setMode] = useState<"files" | "url">("files");
  const [files, setFiles] = useState<File[]>([]);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [imageUrls, setImageUrls] = useState("");
  const [memo, setMemo] = useState("");
  const [eventId, setEventId] = useState("");
  const [takenAt, setTakenAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const urlCount = parseUrlInput(imageUrls).length;
  const canSubmit = mode === "files" ? files.length > 0 : urlCount > 0;
  let submitLabel = "取り込み";
  if (busy) {
    submitLabel = "取り込み中...";
  } else if (mode === "files" && files.length > 1) {
    submitLabel = `${files.length}件取り込み`;
  } else if (mode === "url" && urlCount > 1) {
    submitLabel = `${urlCount}件取り込み`;
  }

  const reset = () => {
    setFiles([]);
    setFileInputKey((key) => key + 1);
    setImageUrls("");
    setMemo("");
    setEventId("");
    setTakenAt("");
  };

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setErr(null);
    try {
      if (mode === "files") {
        const fd = new FormData();
        files.forEach((selected) => fd.append("files", selected));
        if (memo) fd.append("memo", memo);
        if (eventId) fd.append("event_id", eventId);
        if (takenAt) fd.append("taken_at", new Date(takenAt).toISOString());
        const result = await api.uploadPhotosBulk(fd);
        onImported();
        if (result.errors.length > 0) {
          setFiles([]);
          setFileInputKey((key) => key + 1);
          setErr(
            `${result.created.length}件取り込みました。失敗: ${result.errors
              .map((item) => `${item.source} (${item.detail})`)
              .join(" / ")}`,
          );
          return;
        }
      } else {
        const result = await api.importPhotoUrls({
          urls: parseUrlInput(imageUrls),
          memo: memo || undefined,
          event_id: eventId ? Number(eventId) : undefined,
          taken_at: takenAt ? new Date(takenAt).toISOString() : undefined,
        });
        onImported();
        if (result.errors.length > 0) {
          setImageUrls(result.errors.map((item) => item.source).join("\n"));
          setErr(
            `${result.created.length}件取り込みました。失敗: ${result.errors
              .map((item) => `${item.source} (${item.detail})`)
              .join(" / ")}`,
          );
          return;
        }
      }
      reset();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="写真取り込み">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-1 rounded-md border bg-muted p-1">
          <Button
            type="button"
            variant={mode === "files" ? "secondary" : "ghost"}
            onClick={() => {
              setMode("files");
              setErr(null);
            }}
          >
            <Images className="h-4 w-4" />
            ファイル
          </Button>
          <Button
            type="button"
            variant={mode === "url" ? "secondary" : "ghost"}
            onClick={() => {
              setMode("url");
              setErr(null);
            }}
          >
            <LinkIcon className="h-4 w-4" />
            URL
          </Button>
        </div>
        <div className="space-y-1.5">
          {mode === "files" ? (
            <>
              <Label>画像ファイル</Label>
              <Input
                key={fileInputKey}
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
              {files.length > 0 && (
                <p className="text-xs text-muted-foreground">{files.length}件選択中</p>
              )}
            </>
          ) : (
            <>
              <Label>画像URL</Label>
              <Textarea
                value={imageUrls}
                placeholder={"https://example.com/a.jpg, https://example.com/b.jpg"}
                onChange={(e) => setImageUrls(e.target.value)}
              />
            </>
          )}
        </div>
        <div className="space-y-1.5">
          <Label>撮影日時</Label>
          <Input type="datetime-local" value={takenAt} onChange={(e) => setTakenAt(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>イベント</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            value={eventId}
            onChange={(e) => setEventId(e.target.value)}
            disabled={eventsLoading}
          >
            <option value="">{eventsLoading ? "イベントを読み込み中..." : "（なし）"}</option>
            {events.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label>メモ</Label>
          <Textarea value={memo} onChange={(e) => setMemo(e.target.value)} />
        </div>
        {err && <p className="text-sm text-destructive">{err}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            キャンセル
          </Button>
          <Button onClick={submit} disabled={!canSubmit || busy}>
            {submitLabel}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
