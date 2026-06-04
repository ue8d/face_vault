"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Check, GitMerge, X, UserCheck } from "lucide-react";
import { api, faceCropUrl } from "@/lib/api";
import type { MergeSuggestion, ReviewItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PersonCombobox } from "@/components/person-combobox";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [suggestions, setSuggestions] = useState<MergeSuggestion[]>([]);

  const load = () => {
    api.reviewFaces(40).then(setItems).catch(() => {});
    api.mergeSuggestions(40).then(setSuggestions).catch(() => {});
  };
  useEffect(load, []);

  const assign = async (item: ReviewItem, personId: number) => {
    try {
      await api.confirmFace(item.link_id, personId);
      await api.reindex();
      setItems((xs) => xs.filter((x) => x.link_id !== item.link_id));
    } catch (e) {
      alert(`確定失敗: ${(e as Error).message}\nこの写真に既にいる人物の場合は「対象外」で削除してください。`);
    }
  };

  const assignNew = async (item: ReviewItem, name: string) => {
    try {
      const p = await api.createPerson({ name });
      await assign(item, p.id);
    } catch (e) {
      alert(`作成失敗: ${(e as Error).message}`);
    }
  };

  const removeFace = async (item: ReviewItem) => {
    if (!window.confirm("この顔を対象外にして削除しますか？（誤検出・重複時）")) return;
    await api.deleteFaceLink(item.link_id);
    setItems((xs) => xs.filter((x) => x.link_id !== item.link_id));
  };

  const doMerge = async (s: MergeSuggestion) => {
    await api.mergePerson(s.person_a_id, s.person_b_id); // b を a に統合
    setSuggestions((xs) =>
      xs.filter((x) => !(x.person_a_id === s.person_a_id && x.person_b_id === s.person_b_id)),
    );
    api.reviewFaces(40).then(setItems).catch(() => {});
  };

  const dismiss = async (s: MergeSuggestion) => {
    await api.dismissMerge(s.person_a_id, s.person_b_id);
    setSuggestions((xs) =>
      xs.filter((x) => !(x.person_a_id === s.person_a_id && x.person_b_id === s.person_b_id)),
    );
  };

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">確認</h1>

      {/* 顔の確認キュー */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <UserCheck className="h-5 w-5" /> 顔の確認 ({items.length})
        </h2>
        <p className="text-sm text-muted-foreground">
          未照合・低信頼の顔。確定するほど本人のベクトルが増え精度が上がる。
        </p>
        {items.length === 0 ? (
          <p className="text-muted-foreground">確認待ちなし。</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {items.map((it) => (
              <Card key={it.link_id}>
                <CardContent className="flex gap-3 p-3">
                  <Link href={`/photos/${it.photo_id}`} className="shrink-0">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={faceCropUrl(it.photo_id, it.link_id)}
                      alt="face"
                      className="h-24 w-24 rounded-md border object-cover"
                    />
                  </Link>
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="text-sm">
                      {it.person_id ? (
                        <span>
                          現在: <b>{it.person_name}</b>
                          {it.confidence != null && (
                            <span className="text-muted-foreground">
                              {" "}
                              (類似 {it.confidence.toFixed(2)})
                            </span>
                          )}
                        </span>
                      ) : (
                        <Badge variant="outline">未照合</Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {it.candidates.map((c) => (
                        <Button
                          key={c.person_id}
                          size="sm"
                          variant="secondary"
                          onClick={() => assign(it, c.person_id)}
                        >
                          <Check className="h-3 w-3" /> {c.name} {c.score.toFixed(2)}
                        </Button>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <PersonCombobox
                        className="flex-1"
                        placeholder="別の人物を入力..."
                        onPick={(pid) => assign(it, pid)}
                        onCreate={(name) => assignNew(it, name)}
                      />
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        onClick={() => removeFace(it)}
                        title="対象外（削除）"
                      >
                        <X className="h-4 w-4" /> 対象外
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* 統合候補 */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <GitMerge className="h-5 w-5" /> 統合候補 ({suggestions.length})
        </h2>
        <p className="text-sm text-muted-foreground">
          顔ベクトルが近い別人物。同一人物なら統合（後者を前者に吸収）。
        </p>
        {suggestions.length === 0 ? (
          <p className="text-muted-foreground">候補なし。</p>
        ) : (
          <div className="space-y-2">
            {suggestions.map((s) => (
              <Card key={`${s.person_a_id}-${s.person_b_id}`}>
                <CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
                  <div className="text-sm">
                    <Link href={`/persons/${s.person_a_id}`} className="font-medium underline">
                      {s.person_a_name}
                    </Link>
                    <span className="mx-2 text-muted-foreground">↔</span>
                    <Link href={`/persons/${s.person_b_id}`} className="font-medium underline">
                      {s.person_b_name}
                    </Link>
                    <Badge variant="secondary" className="ml-2">
                      類似 {s.score.toFixed(2)}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => doMerge(s)}>
                      <GitMerge className="h-4 w-4" /> 統合
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => dismiss(s)}>
                      <X className="h-4 w-4" /> 別人
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
