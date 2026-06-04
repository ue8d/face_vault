"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Upload, ImageOff } from "lucide-react";
import { api, photoRawUrl } from "@/lib/api";
import type { EventItem, Photo } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { fmtDate } from "@/lib/utils";

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () => api.listPhotos({ limit: 500 }).then(setPhotos).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
    api.listEvents().then(setEvents).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">写真</h1>
        <Button onClick={() => setOpen(true)}>
          <Upload className="h-4 w-4" />
          アップロード
        </Button>
      </div>

      {err && <p className="text-sm text-destructive">{err}</p>}

      {photos.length === 0 ? (
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
        onDone={() => {
          setOpen(false);
          load();
        }}
      />
    </div>
  );
}

function UploadDialog({
  open,
  onClose,
  events,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  events: EventItem[];
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [memo, setMemo] = useState("");
  const [eventId, setEventId] = useState("");
  const [takenAt, setTakenAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (memo) fd.append("memo", memo);
      if (eventId) fd.append("event_id", eventId);
      if (takenAt) fd.append("taken_at", new Date(takenAt).toISOString());
      await api.uploadPhoto(fd);
      setFile(null);
      setMemo("");
      setEventId("");
      setTakenAt("");
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="写真アップロード">
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label>画像ファイル</Label>
          <Input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
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
          >
            <option value="">（なし）</option>
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
          <Button onClick={submit} disabled={!file || busy}>
            {busy ? "アップロード中…" : "アップロード"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
