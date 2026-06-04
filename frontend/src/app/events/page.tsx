"use client";
import { useEffect, useState } from "react";
import { CalendarPlus } from "lucide-react";
import { api } from "@/lib/api";
import type { EventItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog } from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";
import { fmtDate } from "@/lib/utils";

export default function EventsPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [open, setOpen] = useState(false);

  const load = () => api.listEvents().then(setEvents).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">イベント</h1>
        <Button onClick={() => setOpen(true)}>
          <CalendarPlus className="h-4 w-4" /> 作成
        </Button>
      </div>

      {events.length === 0 ? (
        <p className="text-muted-foreground">イベントなし。</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {events.map((ev) => (
            <Card key={ev.id}>
              <CardContent className="space-y-1 p-4">
                <p className="font-semibold">{ev.name}</p>
                {ev.memo && <p className="text-sm text-muted-foreground">{ev.memo}</p>}
                <p className="text-xs text-muted-foreground">{fmtDate(ev.created_at)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateEventDialog
        open={open}
        onClose={() => setOpen(false)}
        onDone={() => {
          setOpen(false);
          load();
        }}
      />
    </div>
  );
}

function CreateEventDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [name, setName] = useState("");
  const [memo, setMemo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.createEvent({ name: name.trim(), memo: memo || null });
      setName("");
      setMemo("");
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="イベント作成">
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label>名前 *</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="GW飲み会" />
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
          <Button onClick={submit} disabled={!name.trim() || busy}>
            {busy ? "作成中…" : "作成"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
