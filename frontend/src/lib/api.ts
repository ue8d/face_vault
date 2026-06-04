import type {
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

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? detail;
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
};
