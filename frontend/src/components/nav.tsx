"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Camera,
  Users,
  CalendarDays,
  Search,
  LayoutDashboard,
  Settings,
  ClipboardCheck,
  Webhook,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "ホーム", icon: LayoutDashboard },
  { href: "/photos", label: "写真", icon: Camera },
  { href: "/persons", label: "人物", icon: Users },
  { href: "/events", label: "イベント", icon: CalendarDays },
  { href: "/review", label: "確認", icon: ClipboardCheck },
  { href: "/search", label: "検索", icon: Search },
  { href: "/api-logs", label: "API", icon: Webhook },
  { href: "/settings", label: "設定", icon: Settings },
];

export function Nav() {
  const pathname = usePathname();
  const [reviewCount, setReviewCount] = useState(0);
  const active = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  useEffect(() => {
    const fetchCount = () =>
      api.reviewCount().then((r) => setReviewCount(r.count)).catch(() => {});
    fetchCount();
    const t = setInterval(fetchCount, 30000);
    return () => clearInterval(t);
  }, [pathname]);

  const badge = (href: string) =>
    href === "/review" && reviewCount > 0 ? (
      <span className="ml-auto rounded-full bg-destructive px-1.5 text-[10px] font-bold text-destructive-foreground">
        {reviewCount > 99 ? "99+" : reviewCount}
      </span>
    ) : null;

  return (
    <>
      {/* PC: サイド */}
      <aside className="hidden md:flex md:w-56 md:flex-col md:border-r md:bg-card md:p-4">
        <Link href="/" className="mb-6 px-2 text-xl font-bold">
          face_vault
        </Link>
        <nav className="flex flex-col gap-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active(href)
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
              {badge(href)}
            </Link>
          ))}
        </nav>
      </aside>

      {/* モバイル: 下部バー */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t bg-card md:hidden">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]",
              active(href) ? "text-primary" : "text-muted-foreground",
            )}
          >
            <span className="relative">
              <Icon className="h-5 w-5" />
              {href === "/review" && reviewCount > 0 && (
                <span className="absolute -right-2 -top-1 rounded-full bg-destructive px-1 text-[8px] font-bold text-destructive-foreground">
                  {reviewCount > 99 ? "99+" : reviewCount}
                </span>
              )}
            </span>
            {label}
          </Link>
        ))}
      </nav>
    </>
  );
}
