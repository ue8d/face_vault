import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "face_vault — 写真記憶アシスタント",
  description: "この人誰だっけ？に答える個人用写真管理",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <div className="flex min-h-screen">
          <Nav />
          <main className="flex-1 pb-20 pt-12 md:pb-0 md:pt-0">
            <div className="container py-6">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
