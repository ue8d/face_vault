"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, X } from "lucide-react";
import { api, photoRawUrl } from "@/lib/api";
import type { EventItem, Photo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import { PersonCombobox } from "@/components/person-combobox";
import { fmtDate } from "@/lib/utils";

export default function SearchPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [personId, setPersonId] = useState("");
  const [personName, setPersonName] = useState("");
  const [eventId, setEventId] = useState("");
  const [eventName, setEventName] = useState("");
  const [tag, setTag] = useState("");
  const [year, setYear] = useState("");
  const [month, setMonth] = useState("");
  const [results, setResults] = useState<Photo[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setEventsLoading(true);
    api
      .listEvents()
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setEventsLoading(false));
  }, []);

  const run = async () => {
    const params: Record<string, string | number | undefined> = {
      person_id: personId || undefined,
      event_id: eventId || undefined,
      event_name: eventName.trim() || undefined,
      tag: tag.trim() || undefined,
      year: year || undefined,
      month: month || undefined,
      limit: 500,
    };
    setBusy(true);
    setErr(null);
    try {
      setResults(await api.listPhotos(params));
      setSearched(true);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">検索</h1>

      <div className="grid grid-cols-1 gap-4 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1.5">
          <Label>人物</Label>
          {personId ? (
            <Badge variant="secondary" className="h-10 gap-1 px-3 text-sm">
              {personName || `#${personId}`}
              <button
                onClick={() => {
                  setPersonId("");
                  setPersonName("");
                }}
                className="ml-1 hover:text-foreground"
                aria-label="クリア"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ) : (
            <PersonCombobox
              className="w-full"
              placeholder="人物名を入力..."
              onPick={(pid, name) => {
                setPersonId(String(pid));
                setPersonName(name ?? "");
              }}
            />
          )}
        </div>
        <Sel
          label="イベント"
          value={eventId}
          onChange={setEventId}
          disabled={eventsLoading}
          options={events.map((e) => [String(e.id), e.name])}
        />
        <div className="space-y-1.5">
          <Label htmlFor="event-name">イベント名</Label>
          <Input
            id="event-name"
            value={eventName}
            onChange={(e) => setEventName(e.target.value)}
            placeholder="GW飲み会"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="tag">タグ</Label>
          <Input id="tag" value={tag} onChange={(e) => setTag(e.target.value)} placeholder="大学" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="year">年</Label>
          <Input id="year" type="number" placeholder="2025" value={year} onChange={(e) => setYear(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="month">月</Label>
          <Input
            id="month"
            type="number"
            placeholder="5"
            min={1}
            max={12}
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={run} disabled={busy}>
          <Search className="h-4 w-4" /> {busy ? "検索中..." : "検索"}
        </Button>
        {err && <p className="text-sm text-destructive">{err}</p>}
      </div>

      {busy && <LoadingState label="写真を検索中..." />}

      {!busy && searched && (
        <div>
          <p className="mb-3 text-sm text-muted-foreground">{results.length} 件</p>
          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground">条件に合う写真はありません。</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {results.map((p) => (
                <Link key={p.id} href={`/photos/${p.id}`}>
                  <div className="aspect-square overflow-hidden rounded-lg border bg-muted">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={photoRawUrl(p.id)}
                      alt=""
                      className="h-full w-full object-cover"
                      onError={(e) => (e.currentTarget.style.display = "none")}
                    />
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{fmtDate(p.taken_at)}</p>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Sel({
  label,
  value,
  onChange,
  disabled,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  options: [string, string][];
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <select
        className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        <option value="">{disabled ? "読み込み中..." : "指定なし"}</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}
