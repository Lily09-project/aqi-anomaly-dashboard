/**
 * Data loading with integrity verification.
 *
 * Every JSON file is checked against the SHA-256 recorded in manifest.json
 * before it is parsed, so a truncated or tampered deployment fails loudly
 * instead of rendering wrong numbers.
 */
import type { DataFiles, Manifest } from "./types";

export const DATA_SCHEMA_VERSION = "2.0";

export class IntegrityError extends Error {
  constructor(public readonly file: string) {
    super(`資料完整性檢查失敗：${file}`);
    this.name = "IntegrityError";
  }
}

export class SchemaMismatchError extends Error {
  constructor(public readonly found: string | undefined) {
    super(`資料格式版本不符：網站需要 ${DATA_SCHEMA_VERSION}，部署的資料是 ${found ?? "未知"}`);
    this.name = "SchemaMismatchError";
  }
}

function parseJson<T>(name: string, bytes: ArrayBuffer): T {
  try {
    return JSON.parse(new TextDecoder().decode(bytes)) as T;
  } catch {
    throw new Error(`${name} 不是有效的 JSON`);
  }
}

function parseManifest(bytes: ArrayBuffer): Manifest {
  const value = parseJson<unknown>("manifest.json", bytes);
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new IntegrityError("manifest.json");
  }
  const manifest = value as Partial<Manifest>;
  if (typeof manifest.schema_version !== "string" || manifest.files === null ||
      typeof manifest.files !== "object" || Array.isArray(manifest.files)) {
    throw new IntegrityError("manifest.json");
  }
  return manifest as Manifest;
}

export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export function createLoader(baseUrl: string, fetcher: Fetcher = (url, init) => fetch(url, init)) {
  let manifestPromise: Promise<Manifest> | null = null;
  const cache = new Map<string, Promise<unknown>>();
  const verified = new Set<string>();

  const getBytes = async (name: string, init?: RequestInit): Promise<ArrayBuffer> => {
    const response = await fetcher(`${baseUrl}data/${name}`, init);
    if (!response.ok) throw new Error(`無法載入 ${name}（HTTP ${response.status}）`);
    return response.arrayBuffer();
  };

  const fetchManifest = (init?: RequestInit) => {
    const promise = getBytes("manifest.json", init).then((bytes) => parseManifest(bytes));
    manifestPromise = promise;
    // Forget a failed manifest so one transient error does not break every later load.
    promise.catch(() => {
      if (manifestPromise === promise) manifestPromise = null;
    });
    return promise;
  };

  const manifest = () => manifestPromise ?? fetchManifest();

  const matches = async (m: Manifest, name: string, bytes: ArrayBuffer) => {
    const expected = m.files[name];
    return m.schema_version === DATA_SCHEMA_VERSION && Boolean(expected) && (await sha256Hex(bytes)) === expected;
  };

  async function load<K extends keyof DataFiles>(name: K): Promise<DataFiles[K]> {
    if (!cache.has(name)) {
      const promise = (async () => {
        let [m, bytes] = await Promise.all([manifest(), getBytes(name)]);
        if (!(await matches(m, name, bytes))) {
          // A redeploy since this tab read the manifest also looks like a mismatch: retry once, bypassing caches.
          [m, bytes] = await Promise.all([fetchManifest({ cache: "reload" }), getBytes(name, { cache: "reload" })]);
          if (m.schema_version !== DATA_SCHEMA_VERSION) throw new SchemaMismatchError(m.schema_version);
          if (!(await matches(m, name, bytes))) throw new IntegrityError(name);
        }
        const data = parseJson<DataFiles[K]>(name, bytes);
        verified.add(name);
        return data;
      })();
      promise.catch(() => cache.delete(name));
      cache.set(name, promise);
    }
    return cache.get(name) as Promise<DataFiles[K]>;
  }

  return { load, manifest, verifiedFiles: () => [...verified].sort() };
}

export type Loader = ReturnType<typeof createLoader>;
