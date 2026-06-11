export interface Environment {
  id: number;
  name: string;
  created_at: string;
  person_count: number;
  photo_count: number;
}

export type CrawlMode = "page" | "shallow" | "domain";

export interface CollectSource {
  id: number;
  name: string;
  start_url: string;
  crawl_mode: CrawlMode;
  max_pages: number;
  max_images: number;
  same_domain_only: boolean;
  respect_robots: boolean;
  enabled: boolean;
  interval_minutes: number;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  created_at: string;
}

export interface CollectSourceInput {
  name: string;
  start_url: string;
  crawl_mode: CrawlMode;
  max_pages: number;
  max_images: number;
  same_domain_only: boolean;
  respect_robots: boolean;
  enabled: boolean;
  interval_minutes: number;
}

export interface CollectRunResult {
  found_urls: number;
  new_urls: number;
  saved: number;
  skipped_duplicate: number;
  failed: number;
  pages_scanned: number;
  error: string | null;
}

export interface Tag {
  id: number;
  name: string;
}

export interface Person {
  id: number;
  name: string;
  nicknames: string[];
  relation: string | null;
  memo: string | null;
  created_at: string;
  tags: Tag[];
}

export interface PhotoPersonLink {
  id: number;
  person_id: number | null;
  person_name: string | null;
  confidence: number | null;
  bbox: string | null;
}

export interface Photo {
  id: number;
  path: string;
  taken_at: string | null;
  memo: string | null;
  event_id: number | null;
  created_at: string;
  person_links: PhotoPersonLink[];
}

export interface PhotoUpdate {
  taken_at?: string | null;
  memo?: string | null;
  event_id?: number | null;
}

export interface PhotoUrlImport {
  url: string;
  taken_at?: string | null;
  memo?: string | null;
  event_id?: number | null;
}

export interface PhotoUrlsImport {
  urls: string[];
  taken_at?: string | null;
  memo?: string | null;
  event_id?: number | null;
}

export interface PhotoImportError {
  source: string;
  detail: string;
}

export interface PhotoBulkImportResult {
  created: Photo[];
  errors: PhotoImportError[];
}

export interface EventItem {
  id: number;
  name: string;
  memo: string | null;
  created_at: string;
}

export interface IdentifyResponse {
  person_id: number;
  answer: string;
}

export interface ApiCandidate {
  person_id: number;
  name: string;
  score: number;
  margin: number;
  model_key: string;
  matched: boolean;
}

export interface ApiFaceResult {
  bbox: number[];
  det_score: number;
  candidates: ApiCandidate[];
}

export interface ApiQuery {
  id: number;
  path: string;
  faces_detected: number;
  result: ApiFaceResult[];
  note: string | null;
  learned_person_id: number | null;
  learned_person_name: string | null;
  created_at: string;
}

export interface SettingItem {
  key: string;
  label: string;
  type: "str" | "int" | "float" | "secret" | "bool";
  group: string;
  value: string;
  is_set: boolean;
  source: string;
}

export interface PersonCreate {
  name: string;
  nicknames?: string[];
  relation?: string | null;
  memo?: string | null;
  tags?: string[];
}

export interface PersonImportResult {
  created: number;
  updated: number;
  skipped: number;
  face_queued: number;
  errors: string[];
}

export interface FaceImportStatus {
  pending: number;
  done: number;
  failed: number;
}

export interface ReviewCandidate {
  person_id: number;
  name: string;
  score: number;
}

export interface ReviewItem {
  link_id: number;
  photo_id: number;
  bbox: string | null;
  confidence: number | null;
  person_id: number | null;
  person_name: string | null;
  candidates: ReviewCandidate[];
}

export interface MergeSuggestion {
  person_a_id: number;
  person_a_name: string;
  person_a_photo_id: number | null;
  person_a_link_id: number | null;
  person_b_id: number;
  person_b_name: string;
  person_b_photo_id: number | null;
  person_b_link_id: number | null;
  score: number;
}
