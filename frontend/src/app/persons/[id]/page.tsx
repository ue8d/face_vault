"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Sparkles, Pencil, Trash2, ImagePlus, GitMerge } from "lucide-react";
import { api, photoRawUrl } from "@/lib/api";
import type { Person, Photo } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { PersonFormDialog } from "@/components/person-form";
import { PersonCombobox } from "@/components/person-combobox";
import { fmtDate } from "@/lib/utils";

export default function PersonDetail() {
  const { id } = useParams<{ id: string }>();
  const pid = Number(id);
  const router = useRouter();
  const [person, setPerson] = useState<Person | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [photosLoading, setPhotosLoading] = useState(true);
  const [answer, setAnswer] = useState<string | null>(null);
  const [loadingAns, setLoadingAns] = useState(false);
  const [edit, setEdit] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () => {
    setErr(null);
    api.getPerson(pid).then(setPerson).catch((e) => setErr(e.message));
    setPhotosLoading(true);
    api
      .listPhotos({ person_id: pid })
      .then(setPhotos)
      .catch(() => setPhotos([]))
      .finally(() => setPhotosLoading(false));
  };

  const doMergeWith = async (sourceId: number) => {
    if (
      !confirm(
        `選択した人物を「${person?.name}」に統合します。統合元は削除され、顔ベクトル等が移管されます。よろしいですか？`,
      )
    )
      return;
    try {
      await api.mergePerson(pid, sourceId);
      load();
    } catch (e) {
      alert(`統合失敗: ${(e as Error).message}`);
    }
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  const identify = async () => {
    setLoadingAns(true);
    setAnswer(null);
    try {
      const r = await api.identify(pid);
      setAnswer(r.answer);
    } catch (e) {
      setAnswer(`失敗: ${(e as Error).message}`);
    } finally {
      setLoadingAns(false);
    }
  };

  const del = async () => {
    if (!confirm("この人物を削除しますか？")) return;
    await api.deletePerson(pid);
    router.push("/persons");
  };

  const registerFace = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.registerPersonFace(pid, fd);
      await api.reindex();
      load();
      alert("参照顔を登録しました");
    } catch (e) {
      alert(`登録失敗: ${(e as Error).message}`);
    }
  };

  if (err) return <p className="text-destructive">{err}</p>;
  if (!person) return <LoadingState label="人物を読み込み中..." />;

  return (
    <div className="space-y-6">
      <Link href="/persons" className="inline-flex items-center gap-1 text-sm text-muted-foreground">
        <ArrowLeft className="h-4 w-4" /> 人物一覧
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">
            {person.name}
            {person.nicknames.length > 0 && (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                （{person.nicknames.join(" / ")}）
              </span>
            )}
          </h1>
          {person.relation && <p className="text-muted-foreground">{person.relation}</p>}
          <div className="mt-2 flex flex-wrap gap-1">
            {person.tags.map((t) => (
              <Badge key={t.id} variant="secondary">
                {t.name}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEdit(true)}>
            <Pencil className="h-4 w-4" /> 編集
          </Button>
          <Button variant="destructive" onClick={del}>
            <Trash2 className="h-4 w-4" /> 削除
          </Button>
        </div>
      </div>

      {person.memo && (
        <Card>
          <CardContent className="p-4 text-sm whitespace-pre-wrap">{person.memo}</CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> この人誰だっけ？
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={identify} disabled={loadingAns}>
            {loadingAns ? "生成中…" : "AIに聞く"}
          </Button>
          {answer && (
            <div className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm">{answer}</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImagePlus className="h-4 w-4" /> 参照顔を登録
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Input
            type="file"
            accept="image/*"
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) registerFace(f);
            }}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            顔認識ランタイム導入時のみ。1枚から代表ベクトルを登録。
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitMerge className="h-4 w-4" /> 別の人物をこの人に統合
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-muted-foreground">
            誤検出や自動登録（未確認人物）の重複を本人に吸収。顔ベクトルが移管され照合精度が上がる。
          </p>
          <PersonCombobox
            excludeId={pid}
            placeholder="統合する人物を入力..."
            className="w-full max-w-sm"
            onPick={(sourceId) => doMergeWith(sourceId)}
          />
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 text-lg font-semibold">
          写真 ({photosLoading && photos.length === 0 ? "..." : photos.length})
        </h2>
        {photosLoading && photos.length > 0 && <LoadingState compact label="写真を更新中..." />}
        {photosLoading && photos.length === 0 ? (
          <LoadingState label="この人物の写真を読み込み中..." />
        ) : photos.length === 0 ? (
          <p className="text-sm text-muted-foreground">この人物が写る写真はまだなし。</p>
        ) : (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {photos.map((p) => (
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
              </Link>
            ))}
          </div>
        )}
      </div>

      <PersonFormDialog
        open={edit}
        onClose={() => setEdit(false)}
        initial={person}
        onDone={() => {
          setEdit(false);
          load();
        }}
      />
    </div>
  );
}
