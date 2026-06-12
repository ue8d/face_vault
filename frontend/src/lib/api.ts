import type {
  ApiQuery,
  CollectRunResult,
  CollectSource,
  CollectSourceInput,
  Environment,
  EventItem,
  IdentifyResponse,
  Person,
  PersonCreate,
  PersonImportResult,
  Photo,
  PhotoUpdate,
  SettingItem,
  FaceImportStatus,
  MergeSuggestion,
  ReviewItem,
  PhotoBulkImportResult,
  PhotoUrlImport,
  PhotoUrlsImport,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8017";

// 選択中の環境（テナント）。全リクエストに X-Environment-Id を付与して分離。
export const ENV_STORAGE_KEY = "fv_env_id";

export function getCurrentEnvId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ENV_STORAGE_KEY);
  if (!raw) return null;
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
}

export function setCurrentEnvId(id: number | null) {
  if (typeof window === "undefined") return;
  if (id == null) window.localStorage.removeItem(ENV_STORAGE_KEY);
  else window.localStorage.setItem(ENV_STORAGE_KEY, String(id));
}

/** FastAPI のエラー detail を読める文字列にする。
 * 422 は detail が [{loc, msg, type}, ...] の配列で来るため、msg を結合する。 */
function formatDetail(detail: unknown): string | undefined {
  if (detail == null) return undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => {
      if (d && typeof d === "object") {
        const o = d as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(o.loc) ? o.loc[o.loc.length - 1] : undefined;
        return field ? `${field}: ${o.msg ?? ""}` : o.msg ?? JSON.stringify(d);
      }
      return String(d);
    });
    return msgs.join(" / ");
  }
  if (typeof detail === "object") {
    const o = detail as { msg?: string };
    return o.msg ?? JSON.stringify(detail);
  }
  return String(detail);
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const envId = getCurrentEnvId();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(envId != null ? { "X-Environment-Id": String(envId) } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: string = res.statusText;
    try {
      const j = await res.json();
      detail = formatDetail(j.detail) ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const photoRawUrl = (id: number) => `${API_BASE}/photos/${id}/raw`;
export const faceCropUrl = (photoId: number, linkId: number) =>
  `${API_BASE}/photos/${photoId}/faces/${linkId}/crop`;
export const apiQueryRawUrl = (id: number) => `${API_BASE}/api-queries/${id}/raw`;
export const apiQueryCropUrl = (id: number) => `${API_BASE}/api-queries/${id}/crop`;

type PersonListParams = {
  q?: string;
  limit?: number;
  offset?: number;
};

const qs = (params: Record<string, string | number | undefined>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");

export const api = {
  // persons
  listPersons: (params?: string | PersonListParams) => {
    const query =
      typeof params === "string"
        ? qs({ q: params })
        : qs({
            q: params?.q,
            limit: params?.limit,
            offset: params?.offset,
          });
    return http<Person[]>(`/persons${query ? `?${query}` : ""}`);
  },
  countPersons: (q?: string) =>
    http<{ count: number }>(`/persons/count${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getPerson: (id: number) => http<Person>(`/persons/${id}`),
  createPerson: (data: PersonCreate) =>
    http<Person>(`/persons`, { method: "POST", body: JSON.stringify(data) }),
  importPersons: (form: FormData) =>
    http<PersonImportResult>(`/persons/import`, { method: "POST", body: form }),
  faceImportStatus: () =>
    http<FaceImportStatus>(`/persons/import/face-status`),
  processFaces: () =>
    http<FaceImportStatus>(`/persons/import/process-faces`, { method: "POST" }),
  retryFaces: () =>
    http<FaceImportStatus>(`/persons/import/retry-faces`, { method: "POST" }),
  updatePerson: (id: number, data: Partial<PersonCreate>) =>
    http<Person>(`/persons/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deletePerson: (id: number) => http<void>(`/persons/${id}`, { method: "DELETE" }),
  listPersonEvents: (personId: number) => http<EventItem[]>(`/persons/${personId}/events`),
  addPersonEvent: (personId: number, eventId: number) =>
    http<EventItem>(`/persons/${personId}/events/${eventId}`, { method: "POST" }),
  removePersonEvent: (personId: number, eventId: number) =>
    http<void>(`/persons/${personId}/events/${eventId}`, { method: "DELETE" }),
  mergePerson: (targetId: number, sourceId: number) =>
    http<Person>(`/persons/${targetId}/merge`, {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId }),
    }),
  mergeSuggestions: (limit?: number) =>
    http<MergeSuggestion[]>(
      `/persons/merge-suggestions${limit != null ? `?limit=${limit}` : ""}`,
    ),
  dismissMerge: (a: number, b: number) =>
    http<void>(`/persons/merge-suggestions/dismiss`, {
      method: "POST",
      body: JSON.stringify({ person_a_id: a, person_b_id: b }),
    }),

  // review
  reviewFaces: (limit = 30) => http<ReviewItem[]>(`/review/faces?limit=${limit}`),
  reviewCount: () => http<{ count: number }>(`/review/count`),

  // events
  listEvents: (q?: string) =>
    http<EventItem[]>(`/events${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  countEvents: () => http<{ count: number }>(`/events/count`),
  createEvent: (data: { name: string; memo?: string | null }) =>
    http<EventItem>(`/events`, { method: "POST", body: JSON.stringify(data) }),
  listEventPersons: (eventId: number) => http<Person[]>(`/events/${eventId}/persons`),
  addEventPerson: (eventId: number, personId: number) =>
    http<Person>(`/events/${eventId}/persons/${personId}`, { method: "POST" }),
  removeEventPerson: (eventId: number, personId: number) =>
    http<void>(`/events/${eventId}/persons/${personId}`, { method: "DELETE" }),

  // photos
  listPhotos: (params: Record<string, string | number | undefined> = {}) => {
    const query = qs(params);
    return http<Photo[]>(`/photos${query ? `?${query}` : ""}`);
  },
  countPhotos: () => http<{ count: number }>(`/photos/count`),
  getPhoto: (id: number) => http<Photo>(`/photos/${id}`),
  deletePhoto: (id: number) => http<void>(`/photos/${id}`, { method: "DELETE" }),
  updatePhoto: (id: number, data: PhotoUpdate) =>
    http<Photo>(`/photos/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  reprocessPhoto: (id: number) =>
    http<Photo>(`/photos/${id}/reprocess`, { method: "POST" }),
  uploadPhoto: (form: FormData) =>
    http<Photo>(`/photos/upload`, { method: "POST", body: form }),
  uploadPhotosBulk: (form: FormData) =>
    http<PhotoBulkImportResult>(`/photos/upload-bulk`, { method: "POST", body: form }),
  importPhotoUrl: (data: PhotoUrlImport) =>
    http<Photo>(`/photos/import-url`, { method: "POST", body: JSON.stringify(data) }),
  importPhotoUrls: (data: PhotoUrlsImport) =>
    http<PhotoBulkImportResult>(`/photos/import-urls`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // external API queries (受信画像ログ)
  listApiQueries: (params: Record<string, string | number | undefined> = {}) => {
    const query = qs(params);
    return http<ApiQuery[]>(`/api-queries${query ? `?${query}` : ""}`);
  },
  learnApiQuery: (id: number, personId: number, faceIndex = 0) =>
    http<ApiQuery>(`/api-queries/${id}/learn`, {
      method: "POST",
      body: JSON.stringify({ person_id: personId, face_index: faceIndex }),
    }),
  deleteApiQuery: (id: number) =>
    http<void>(`/api-queries/${id}`, { method: "DELETE" }),

  // faces
  confirmFace: (linkId: number, personId: number) =>
    http(`/faces/links/${linkId}`, {
      method: "PATCH",
      body: JSON.stringify({ person_id: personId }),
    }),
  deleteFaceLink: (linkId: number) =>
    http<void>(`/faces/links/${linkId}`, { method: "DELETE" }),
  registerPersonFace: (personId: number, form: FormData) =>
    http(`/persons/${personId}/faces`, { method: "POST", body: form }),
  reindex: () => http<{ backend: string; size: number }>(`/faces/reindex`, { method: "POST" }),

  // environments
  listEnvironments: () => http<Environment[]>(`/environments`),
  createEnvironment: (name: string) =>
    http<Environment>(`/environments`, { method: "POST", body: JSON.stringify({ name }) }),
  renameEnvironment: (id: number, name: string) =>
    http<Environment>(`/environments/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteEnvironment: (id: number) =>
    http<void>(`/environments/${id}`, { method: "DELETE" }),

  // settings
  listSettings: () => http<SettingItem[]>(`/settings`),
  updateSettings: (values: Record<string, string | null>) =>
    http<SettingItem[]>(`/settings`, { method: "PUT", body: JSON.stringify({ values }) }),

  // identify
  identify: (personId: number) =>
    http<IdentifyResponse>(`/identify-person`, {
      method: "POST",
      body: JSON.stringify({ person_id: personId }),
    }),

  // collect (自動画像収集)
  listCollectSources: () => http<CollectSource[]>(`/collect/sources`),
  createCollectSource: (data: CollectSourceInput) =>
    http<CollectSource>(`/collect/sources`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateCollectSource: (id: number, data: Partial<CollectSourceInput>) =>
    http<CollectSource>(`/collect/sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteCollectSource: (id: number) =>
    http<void>(`/collect/sources/${id}`, { method: "DELETE" }),
  runCollectSource: (id: number) =>
    http<CollectRunResult>(`/collect/sources/${id}/run`, { method: "POST" }),
};
