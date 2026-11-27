import { afterEach, describe, expect, it, vi } from "vitest";
import { createLoader, FETCH_TIMEOUT_MS, sha256Hex } from "./data";

const body = '{"items":[]}';
const respond = (value: string) => new Response(new TextEncoder().encode(value));

describe("deployment data boundaries", () => {
  it("rejects a foreign schema even when the content hash matches", async () => {
    const digest = await sha256Hex(new TextEncoder().encode(body).buffer as ArrayBuffer);
    const loader = createLoader("./", async (url) => respond(
      url.endsWith("manifest.json")
        ? JSON.stringify({ schema_version: "incompatible", files: { "overview.json": digest } })
        : body,
    ));
    await expect(loader.load("overview.json")).rejects.toThrow("資料格式版本不符");
    expect(loader.verifiedFiles()).toEqual([]);
  });

  it("does not mark a hash-matched but invalid JSON file as verified", async () => {
    const invalid = "{";
    const digest = await sha256Hex(new TextEncoder().encode(invalid).buffer as ArrayBuffer);
    let payload = invalid;
    const loader = createLoader("./", async (url) => respond(
      url.endsWith("manifest.json")
        ? JSON.stringify({ schema_version: "2.0", files: { "overview.json": digest } })
        : payload,
    ));
    await expect(loader.load("overview.json")).rejects.toThrow();
    expect(loader.verifiedFiles()).toEqual([]);
    payload = body;
    await expect(loader.load("overview.json")).rejects.toThrow();
  });

  it.each(["null", "[]", "{}", '{"files":null}'])("rejects a malformed manifest and allows a later retry: %s", async (invalid) => {
    const digest = await sha256Hex(new TextEncoder().encode(body).buffer as ArrayBuffer);
    let broken = true;
    const loader = createLoader("./", async (url) => respond(
      url.endsWith("manifest.json")
        ? broken ? invalid : JSON.stringify({ schema_version: "2.0", files: { "overview.json": digest } })
        : body,
    ));
    await expect(loader.load("overview.json")).rejects.toThrow("manifest.json");
    expect(loader.verifiedFiles()).toEqual([]);
    broken = false;
    await expect(loader.load("overview.json")).resolves.toEqual({ items: [] });
  });
});

it("does not return a new file alongside cached files from an older deployment", async () => {
  const old = '{"version":"old"}';
  const next = '{"version":"new"}';
  const digest = async (value: string) => sha256Hex(new TextEncoder().encode(value).buffer as ArrayBuffer);
  const oldHash = await digest(old);
  const nextHash = await digest(next);
  let deployed = false;
  let finishOld!: (response: Response) => void;
  const delayed = new Promise<Response>((resolve) => { finishOld = resolve; });
  const loader = createLoader("./", async (url) => {
    if (url.endsWith("manifest.json")) {
      const hash = deployed ? nextHash : oldHash;
      return respond(JSON.stringify({ schema_version: "2.0", files: {
        "overview.json": hash, "provenance.json": hash, "propagation.json": hash,
      } }));
    }
    if (url.endsWith("propagation.json")) return delayed;
    return respond(deployed ? next : old);
  });
  await expect(loader.load("overview.json")).resolves.toEqual({ version: "old" });
  const late = expect(loader.load("propagation.json")).rejects.toThrow("網站資料已更新");
  deployed = true;
  await expect(loader.load("provenance.json")).rejects.toThrow("網站資料已更新");
  finishOld(respond(old));
  await late;
  await expect(loader.load("overview.json")).rejects.toThrow("網站資料已更新");
  await expect(loader.manifest()).rejects.toThrow("網站資料已更新");
  expect(loader.verifiedFiles()).toEqual([]);
});

describe("web crypto availability", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains the secure-context requirement instead of a raw TypeError", async () => {
    vi.stubGlobal("crypto", {});
    await expect(sha256Hex(new TextEncoder().encode(body).buffer as ArrayBuffer)).rejects.toThrow("https 或 localhost");
  });
});

describe("stalled connections", () => {
  afterEach(() => vi.useRealTimers());

  const abortable = (signal: AbortSignal | null | undefined) =>
    new Promise<never>((_, reject) => signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));

  it("gives up with a readable message when the server never answers", async () => {
    vi.useFakeTimers();
    const loader = createLoader("./", (_url, init) => abortable(init?.signal));
    const result = loader.load("overview.json").then(() => "loaded", (e: Error) => e.message);
    await vi.advanceTimersByTimeAsync(FETCH_TIMEOUT_MS + 1);
    expect(await result).toMatch(/逾時.*20 秒/);
  });

  it("also times out when the body stalls after the headers arrived", async () => {
    vi.useFakeTimers();
    const loader = createLoader("./", (_url, init) =>
      Promise.resolve({ ok: true, status: 200, arrayBuffer: () => abortable(init?.signal) } as unknown as Response),
    );
    const result = loader.load("overview.json").then(() => "loaded", (e: Error) => e.message);
    await vi.advanceTimersByTimeAsync(FETCH_TIMEOUT_MS + 1);
    expect(await result).toMatch(/逾時/);
  });

  it("does not report a timeout for an ordinary network failure", async () => {
    const loader = createLoader("./", () => Promise.reject(new TypeError("Failed to fetch")));
    await expect(loader.load("overview.json")).rejects.toThrow("網路連線失敗");
  });
});
