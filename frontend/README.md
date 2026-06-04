# frontend — face_vault

Next.js 14 (App Router) / TypeScript / TailwindCSS / shadcn風UI。モバイル対応（PC=サイドナビ、モバイル=下部タブ）。

## 画面

- `/` ホーム（件数・顔インデックス再構築）
- `/photos` 写真一覧 + アップロード（メモ/イベント/撮影日時）
- `/photos/[id]` 写真詳細・検出顔→人物確定
- `/persons` 人物一覧・名前検索・登録
- `/persons/[id]` 人物詳細・「この人誰だっけ？」・編集/削除・参照顔登録・写真一覧
- `/events` イベント一覧・作成
- `/search` 写真検索（人物/イベント/年/月）

## 開発

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE を backend に合わせる
npm run dev                  # http://localhost:3017
```

backend(FastAPI) を `http://localhost:8017` で起動しておくこと。

## 構成

```
src/
  app/            App Router ページ
  components/
    ui/           shadcn風プリミティブ（button/input/card/dialog 等）
    nav.tsx       レスポンシブナビ
    person-form.tsx 人物 登録/編集ダイアログ
  lib/
    api.ts        backend RESTクライアント
    types.ts      APIスキーマ型
    utils.ts      cn / 日付整形
```

## 備考

- shadcn/ui は CLI生成でなく同等の最小実装を `components/ui` に同梱（radix非依存・オフラインビルド可）
- 画像は backend `GET /photos/{id}/raw` から取得
