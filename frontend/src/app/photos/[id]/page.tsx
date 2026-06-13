"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check, Pencil, RefreshCw, Trash2, X } from "lucide-react";
import { api, photoRawUrl } from "@/lib/api";
import type { EventItem, Photo } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { Textarea } from "@/components/ui/textarea";
import { PersonCombobox } from "@/components/person-combobox";
import { fmtDate } from "@/lib/utils";

function toDateTimeLocal(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function fromDateTimeLocal(value: string) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function parseBbox(value: string | null): { x: number; y: number; w: number; h: number } | null {
  if (!value) return null;
  const parts = value.split(",").map((v) => Number(v.trim()));
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return null;
  const [x, y, w, h] = parts;
  return { x, y, w, h };
}

// 顔ごとの識別色。番号と色を画像オーバーレイ・リストで共有。
const FACE_COLORS = [
  "#ef4444",
  "#3b82f6",
  "#22c55e",
  "#eab308",
  "#a855f7",
  "#ec4899",
  "#06b6d4",
  "#f97316",
];
const faceColor = (index: number) => FACE_COLORS[index % FACE_COLORS.length];

export default function PhotoDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pid = Number(id);
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [memo, setMemo] = useState("");
  const [takenAt, setTakenAt] = useState("");
  const [eventId, setEventId] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [reprocessBusy, setReprocessBusy] = useState(false);
  const [reprocessErr, setReprocessErr] = useState<string | null>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);
  const [hoveredLink, setHoveredLink] = useState<number | null>(null);

  const resetForm = (target: Photo) => {
    setMemo(target.memo ?? "");
    setTakenAt(toDateTimeLocal(target.taken_at));
    setEventId(target.event_id == null ? "" : String(target.event_id));
    setSaveErr(null);
  };

  const load = async () => {
    try {
      setErr(null);
      setPhoto(await api.getPhoto(pid));
    } catch (e) {
      setErr((e as Error).message);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  useEffect(() => {
    if (photo) resetForm(photo);
  }, [photo]);

  const eventName = (id: number | null) => {
    if (id == null) return "-";
    if (eventsLoading) return "読み込み中...";
    return events.find((event) => event.id === id)?.name ?? `#${id}`;
  };

  const confirm = async (linkId: number, personId: number) => {
    try {
      await api.confirmFace(linkId, personId);
      await api.reindex();
      load();
    } catch (e) {
      alert(`確定失敗: ${(e as Error).message}`);
    }
  };

  const createAndConfirm = async (linkId: number, name: string) => {
    try {
      const created = await api.createPerson({ name });
      await confirm(linkId, created.id);
    } catch (e) {
      alert(`作成失敗: ${(e as Error).message}`);
    }
  };

  const deletePhoto = async () => {
    if (!window.confirm("この写真を削除しますか？\n顔の紐付け・この画像から登録した参照ベクトルも削除されます。")) return;
    try {
      await api.deletePhoto(pid);
      router.push("/photos");
    } catch (e) {
      alert(`削除失敗: ${(e as Error).message}`);
    }
  };

  const cancelEdit = () => {
    if (photo) resetForm(photo);
    setEditing(false);
  };

  const savePhoto = async () => {
    if (!photo) return;
    setBusy(true);
    setSaveErr(null);
    try {
      const updated = await api.updatePhoto(photo.id, {
        memo: memo.trim() ? memo : null,
        taken_at: fromDateTimeLocal(takenAt),
        event_id: eventId ? Number(eventId) : null,
      });
      setPhoto(updated);
      setEditing(false);
    } catch (e) {
      setSaveErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const reprocessPhoto = async () => {
    if (!photo) return;
    setReprocessBusy(true);
    setReprocessErr(null);
    try {
      setPhoto(await api.reprocessPhoto(photo.id));
    } catch (e) {
      setReprocessErr((e as Error).message);
    } finally {
      setReprocessBusy(false);
    }
  };

  if (err) return <p className="text-destructive">{err}</p>;
  if (!photo) return <LoadingState label="写真を読み込み中..." />;

  return (
    <div className="space-y-6">
      <Link href="/photos" className="inline-flex items-center gap-1 text-sm text-muted-foreground">
        <ArrowLeft className="h-4 w-4" /> 写真一覧
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="relative overflow-hidden rounded-lg border bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={photoRawUrl(photo.id)}
            alt={`photo ${photo.id}`}
            className="w-full object-contain"
            onLoad={(e) =>
              setImgSize({
                w: e.currentTarget.naturalWidth,
                h: e.currentTarget.naturalHeight,
              })
            }
          />
          {imgSize &&
            photo.person_links.map((link, index) => {
              const box = parseBbox(link.bbox);
              if (!box) return null;
              const color = faceColor(index);
              const active = hoveredLink === link.id;
              return (
                <div
                  key={link.id}
                  className="pointer-events-none absolute transition-opacity"
                  style={{
                    left: `${(box.x / imgSize.w) * 100}%`,
                    top: `${(box.y / imgSize.h) * 100}%`,
                    width: `${(box.w / imgSize.w) * 100}%`,
                    height: `${(box.h / imgSize.h) * 100}%`,
                    border: `${active ? 3 : 2}px solid ${color}`,
                    borderRadius: 4,
                    boxShadow: active ? `0 0 0 2px ${color}55` : "none",
                    opacity: hoveredLink == null || active ? 1 : 0.35,
                  }}
                >
                  <span
                    className="absolute -left-px -top-5 rounded px-1 text-xs font-bold text-white"
                    style={{ backgroundColor: color }}
                  >
                    {index + 1}
                  </span>
                </div>
              );
            })}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>写真情報</CardTitle>
              {!editing && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                    <Pencil className="h-4 w-4" /> 編集
                  </Button>
                  <Button variant="destructive" size="sm" onClick={deletePhoto}>
                    <Trash2 className="h-4 w-4" /> 削除
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {editing ? (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="photo-taken-at">撮影日時</Label>
                    <Input
                      id="photo-taken-at"
                      type="datetime-local"
                      value={takenAt}
                      onChange={(e) => setTakenAt(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="photo-memo">メモ</Label>
                    <Textarea
                      id="photo-memo"
                      value={memo}
                      onChange={(e) => setMemo(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="photo-event">イベント</Label>
                    <select
                      id="photo-event"
                      className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                      value={eventId}
                      onChange={(e) => setEventId(e.target.value)}
                      disabled={eventsLoading}
                    >
                      <option value="">{eventsLoading ? "イベントを読み込み中..." : "未設定"}</option>
                      {events.map((event) => (
                        <option key={event.id} value={event.id}>
                          {event.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  {saveErr && <p className="text-sm text-destructive">{saveErr}</p>}
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={cancelEdit} disabled={busy}>
                      <X className="h-4 w-4" /> キャンセル
                    </Button>
                    <Button onClick={savePhoto} disabled={busy}>
                      <Check className="h-4 w-4" /> {busy ? "保存中..." : "保存"}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="space-y-1">
                  <p>撮影: {fmtDate(photo.taken_at)}</p>
                  <p>メモ: {photo.memo || "-"}</p>
                  <p>イベント: {eventName(photo.event_id)}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>検出された顔 ({photo.person_links.length})</CardTitle>
              <Button variant="outline" size="sm" onClick={reprocessPhoto} disabled={reprocessBusy}>
                <RefreshCw className="h-4 w-4" /> {reprocessBusy ? "再認識中..." : "再認識"}
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {reprocessErr && <p className="text-sm text-destructive">{reprocessErr}</p>}
              {photo.person_links.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  顔がない、または顔認識ランタイム未導入です。
                </p>
              )}
              {photo.person_links.map((link, index) => (
                <div
                  key={link.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border p-2 transition-colors"
                  style={hoveredLink === link.id ? { backgroundColor: `${faceColor(index)}1a` } : undefined}
                  onMouseEnter={() => setHoveredLink(link.id)}
                  onMouseLeave={() => setHoveredLink(null)}
                >
                  <span
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-xs font-bold text-white"
                    style={{ backgroundColor: faceColor(index) }}
                  >
                    {index + 1}
                  </span>
                  <div className="flex-1">
                    {link.person_id ? (
                      <Link href={`/persons/${link.person_id}`} className="font-medium underline">
                        {link.person_name ?? `#${link.person_id}`}
                      </Link>
                    ) : (
                      <Badge variant="outline">未照合</Badge>
                    )}
                    {link.confidence != null && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        類似 {link.confidence.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <PersonCombobox
                    onPick={(personId) => confirm(link.id, personId)}
                    onCreate={(name) => createAndConfirm(link.id, name)}
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
