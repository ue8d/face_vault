"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Person } from "@/lib/types";
import { Input } from "@/components/ui/input";

/**
 * 人物フリー入力＋サジェスト。
 * - onPick: 既存人物を選択
 * - onCreate: 一致なしの新規作成（省略時は新規作成行を出さない＝統合等の用途）
 * - excludeId: 候補から除外（自分自身など）
 */
export function PersonCombobox({
  onPick,
  onCreate,
  excludeId,
  placeholder = "人物名を入力...",
  className = "w-56",
}: {
  onPick: (personId: number, name?: string) => void | Promise<void>;
  onCreate?: (name: string) => void | Promise<void>;
  excludeId?: number;
  placeholder?: string;
  className?: string;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<Person[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const term = q.trim();
    if (!term) {
      setList([]);
      return;
    }
    let alive = true;
    const t = setTimeout(() => {
      api
        .listPersons({ q: term, limit: 8 })
        .then((rows) => alive && setList(rows.filter((p) => p.id !== excludeId)))
        .catch(() => alive && setList([]));
    }, 200);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, excludeId]);

  const exactExists = list.some((p) => p.name === q.trim());

  const run = async (fn: () => void | Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      setQ("");
      setOpen(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`relative ${className}`}>
      <Input
        className="h-8"
        placeholder={placeholder}
        value={q}
        disabled={busy}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && q.trim()) {
            e.preventDefault();
            if (list.length > 0) run(() => onPick(list[0].id, list[0].name));
            else if (onCreate) run(() => onCreate(q.trim()));
          }
        }}
      />
      {open && q.trim() && (
        <div className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-md border bg-card shadow-md">
          {list.map((p) => (
            <button
              key={p.id}
              type="button"
              className="flex w-full flex-col items-start px-3 py-1.5 text-left text-sm hover:bg-accent"
              onMouseDown={(e) => {
                e.preventDefault();
                run(() => onPick(p.id, p.name));
              }}
            >
              <span className="font-medium">{p.name}</span>
              {p.nicknames.length > 0 && (
                <span className="text-xs text-muted-foreground">{p.nicknames.join(" / ")}</span>
              )}
            </button>
          ))}
          {list.length === 0 && !onCreate && (
            <p className="px-3 py-1.5 text-sm text-muted-foreground">該当なし</p>
          )}
          {onCreate && !exactExists && (
            <button
              type="button"
              className="flex w-full items-center gap-1 border-t px-3 py-1.5 text-left text-sm text-primary hover:bg-accent"
              onMouseDown={(e) => {
                e.preventDefault();
                run(() => onCreate(q.trim()));
              }}
            >
              ＋ 「{q.trim()}」を新規作成
            </button>
          )}
        </div>
      )}
    </div>
  );
}
