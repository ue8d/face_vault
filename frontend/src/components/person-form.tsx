"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Person } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog } from "@/components/ui/dialog";

export function PersonFormDialog({
  open,
  onClose,
  onDone,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  onDone: (p: Person) => void;
  initial?: Person;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [nicknames, setNicknames] = useState((initial?.nicknames ?? []).join(", "));
  const [relation, setRelation] = useState(initial?.relation ?? "");
  const [memo, setMemo] = useState(initial?.memo ?? "");
  const [tags, setTags] = useState((initial?.tags ?? []).map((t) => t.name).join(", "));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    const splitCsv = (s: string) =>
      s
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
    const payload = {
      name: name.trim(),
      nicknames: splitCsv(nicknames),
      relation: relation || null,
      memo: memo || null,
      tags: splitCsv(tags),
    };
    try {
      const p = initial
        ? await api.updatePerson(initial.id, payload)
        : await api.createPerson(payload);
      onDone(p);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title={initial ? "人物を編集" : "人物を登録"}>
      <div className="space-y-4">
        <Field label="名前 *">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="山田太郎" />
        </Field>
        <Field label="ニックネーム（カンマ区切り・複数可）">
          <Input
            value={nicknames}
            onChange={(e) => setNicknames(e.target.value)}
            placeholder="タロ, やまちゃん"
          />
        </Field>
        <Field label="関係性">
          <Input
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
            placeholder="大学の友人 / 家族 / 前職"
          />
        </Field>
        <Field label="タグ（カンマ区切り）">
          <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="大学, 趣味仲間" />
        </Field>
        <Field label="メモ">
          <Textarea value={memo} onChange={(e) => setMemo(e.target.value)} />
        </Field>
        {err && <p className="text-sm text-destructive">{err}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            キャンセル
          </Button>
          <Button onClick={submit} disabled={!name.trim() || busy}>
            {busy ? "保存中…" : "保存"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
