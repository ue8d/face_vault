"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Camera, CalendarDays, Loader2, RefreshCw, Users } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  const [counts, setCounts] = useState({ photos: 0, persons: 0, events: 0 });
  const [countsLoading, setCountsLoading] = useState(true);
  const [reindex, setReindex] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.countPhotos(), api.countPersons(), api.countEvents()])
      .then(([p, pe, e]) =>
        setCounts({ photos: p.count, persons: pe.count, events: e.count }),
      )
      .catch(() => {})
      .finally(() => setCountsLoading(false));
  }, []);

  const doReindex = async () => {
    setBusy(true);
    try {
      const r = await api.reindex();
      setReindex(`${r.backend} / ${r.size}件`);
    } catch (e) {
      setReindex(`失敗: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const tiles = [
    { href: "/photos", label: "写真", icon: Camera, n: counts.photos },
    { href: "/persons", label: "人物", icon: Users, n: counts.persons },
    { href: "/events", label: "イベント", icon: CalendarDays, n: counts.events },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">ホーム</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {tiles.map(({ href, label, icon: Icon, n }) => (
          <Link key={href} href={href}>
            <Card className="transition-colors hover:bg-accent">
              <CardContent className="flex items-center justify-between p-6">
                <div>
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <p className="mt-1 flex h-9 items-center text-3xl font-bold">
                    {countsLoading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    ) : (
                      n
                    )}
                  </p>
                </div>
                <Icon className="h-8 w-8 text-muted-foreground" />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-4">
          <Button onClick={doReindex} disabled={busy} variant="outline">
            <RefreshCw className={busy ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            顔インデックス再構築
          </Button>
          {reindex && <span className="text-sm text-muted-foreground">{reindex}</span>}
        </CardContent>
      </Card>
    </div>
  );
}
