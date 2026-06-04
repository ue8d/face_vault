# face_vault

> 「この人、誰だっけ？」に答える、セルフホスト型の写真記憶アシスタント。

大量の写真から顔認識で人物を特定し、名前・関係性・記録・共起（よく一緒に写る人）まで含めて答えるWebアプリ。手元のサーバーで自分専用に動かす前提（self-hosted）。

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)

---

## 特徴

- 🧠 **顔認識で自動整理** — アップロードした写真の顔を検出し、既存人物に自動照合。知らない顔は「未確認人物」として自動登録
- 🔍 **「この人誰だっけ？」** — 人物の関係性・メモ・初回/最終撮影・写真枚数・よく一緒に写る人・関連イベントをAIが要約
- 📈 **使うほど賢くなる（半自動）** — 確認キューでサクサク確定、近い人物の統合提案で重複を掃除 → 参照ベクトルが増えて精度向上
- 🏷️ **人物・イベント・タグ管理** — 複数ニックネーム対応、共起分析、撮影日時はEXIFから自動抽出
- 🔌 **AIプロバイダ切替** — OpenAI / Anthropic / Gemini を抽象化レイヤーで切替（Web設定から、鍵未設定時はテンプレ回答）
- 🐳 **Docker一発起動** — `docker compose up` だけ。FAISS未導入環境はnumpyフォールバックで同一動作
- 🔒 **完全セルフホスト** — データは自分のサーバー内のみ。外部公開する場合も Cloudflare Tunnel + Access を想定

## 技術スタック

| レイヤー | 採用技術 |
|---|---|
| フロント | Next.js 14 (App Router) / TypeScript / TailwindCSS / shadcn風UI |
| バック | FastAPI / Python 3.12 / SQLAlchemy 2.0 |
| DB | PostgreSQL（本番） / SQLite（ローカル開発） |
| 顔認識 | InsightFace (antelopev2 / ArcFace R100) + ONNX Runtime |
| ベクトル検索 | FAISS（PG=正本、FAISS=検索インデックス。未導入時 numpy） |
| AI | OpenAI / Anthropic / Gemini（抽象化レイヤー） |

## クイックスタート

必要なもの: Docker / Docker Compose。

```bash
git clone <this-repo> face_vault && cd face_vault
cp .env.example .env          # 値を編集（最低限 POSTGRES_PASSWORD）
docker compose up -d --build  # db + backend + frontend
```

- フロント: http://localhost:3017
- API ドキュメント: http://localhost:8017/docs

> 顔認識ランタイム（InsightFace/FAISS）は既定で有効。イメージが大きく初回はモデルを自動DL（約350MB）。
> 軽量に試すだけなら `INSTALL_FACE=false docker compose up -d --build`（顔処理はスキップ、手動割当のみ）。

停止: `docker compose down`（`-v` でDB・写真ボリュームも削除）。

## 設定

`.env`（`.env.example` 参照）。AI鍵・しきい値などは**起動後にWeb設定画面からも変更可**（DB管理、再起動不要）。

| 変数 | 説明 | 既定 |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | DB認証 | `face_vault` |
| `AI_PROVIDER` | `openai` / `anthropic` / `gemini` | `anthropic` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | AIキー（任意） | 空 |
| `MATCH_THRESHOLD` | 顔照合のコサイン類似度しきい値 | `0.35` |
| `INSTALL_FACE` | 顔認識ランタイムを入れる（Dockerビルド時） | `true` |
| `NEXT_PUBLIC_API_BASE` | ブラウザから見たbackend URL | `http://localhost:8017` |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel（任意公開） | 空 |

> ポートは標準+17（backend 8017 / frontend 3017 / postgres 5449）。`docker-compose.yml` で変更可。
> DB接続情報とポートだけは起動前に必要なため env 管理（その他の設定はDB管理）。

## 使い方

1. **人物** タブで人物を登録（名前・複数ニックネーム・関係性・タグ）
2. **写真** タブからアップロード（顔を自動検出・照合・未一致は自動登録）
3. **確認** タブで未照合・低信頼の顔を候補から確定 → 精度が育つ。重複人物は統合候補から掃除
4. **人物詳細** で「この人誰だっけ？」→ AIが要約回答
5. **検索** で人物名・イベント名・タグ・年月から写真を探す

CSV一括取り込みにも対応（`id,name,name_type,img_url`、`img_url` から参照顔を自動取得）。

## 開発

```bash
# backend（SQLiteで起動・Docker不要）
cd backend && pip install -r requirements.txt
export DATABASE_URL="sqlite:///./face_vault.db"   # PowerShell: $env:DATABASE_URL=...
uvicorn app.main:app --reload --port 8017          # http://127.0.0.1:8017/docs
pytest                                             # テスト（顔ランタイム無しでも緑）

# frontend
cd frontend && npm install && npm run dev          # http://localhost:3017
```

設計方針: Repository Pattern / Service Layer / 型安全 / OpenAPI自動生成 / テスト。
詳細は `backend/app/models/`（DB設計の正本）と各 service を参照。

## バックアップ・公開

```bash
bash scripts/backup.sh    # DB(pg_dump.gz) + 写真ボリューム(tar.gz) → backups/
bash scripts/restore.sh backups/db_YYYYMMDD_HHMMSS.sql.gz

# 外部公開（任意）: Cloudflare Tunnel
#   .env に CLOUDFLARE_TUNNEL_TOKEN を設定し
docker compose --profile tunnel up -d
```

公開時は **Cloudflare Access 等で認証必須**にすること（顔データを含むため）。

## ロードマップ

- [ ] オンライン学習（高信頼マッチの自動ベクトル追加 / ドリフト対策込み）
- [ ] AdaFace 等 マスク・低画質特化モデルへの差し替え

## プライバシーと責任

本ソフトウェアは顔認識を扱う。**自分が正当な権利を持つ写真にのみ使用**し、各地域の法令（個人情報・肖像権・GDPR等）を遵守すること。生成された顔ベクトル・人物データはすべて自分のサーバー内に保存される。作者は本ソフトの利用に起因する一切の責任を負わない。

## ライセンス

[GNU General Public License v3.0](LICENSE)

```
Copyright (C) 2026 face_vault contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
```
