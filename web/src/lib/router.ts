/** Hash routes keep every view shareable on a static host. */
export type Sensitivity = "sensitive" | "general";

export type Route =
  | { name: "home" }
  | { name: "station"; station: string; sensitivity?: Sensitivity; hours?: number }
  | { name: "propagation"; frame?: number }
  | { name: "anomalies"; id?: string; station?: string; kind?: "local" | "regional" }
  | { name: "whatif" }
  | { name: "model" }
  | { name: "data" }
  | { name: "not-found"; path: string };

const MAX_HOURS = 12;

/** Integer query parameter, or undefined when it is absent or malformed. */
function intParam(params: URLSearchParams, key: string): number | undefined {
  const raw = params.get(key);
  if (raw === null || !/^\d+$/.test(raw)) return undefined;
  return Number(raw);
}

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, "") || "/";
  const [path = "/", query = ""] = raw.split("?");
  const params = new URLSearchParams(query);
  let parts: string[];
  try {
    parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  } catch {
    return { name: "not-found", path };
  }
  const [head, second] = parts;
  switch (head) {
    case undefined:
      return { name: "home" };
    case "station": {
      if (!second) return { name: "not-found", path };
      const sensitivity = params.get("for");
      const hours = intParam(params, "hours");
      return {
        name: "station",
        station: second,
        sensitivity: sensitivity === "general" ? "general" : sensitivity === "sensitive" ? "sensitive" : undefined,
        hours: hours !== undefined && hours >= 1 && hours <= MAX_HOURS ? hours : undefined,
      };
    }
    case "propagation": {
      return { name: "propagation", frame: intParam(params, "frame") };
    }
    case "anomalies": {
      const kind = params.get("kind");
      return {
        name: "anomalies",
        id: params.get("id") ?? undefined,
        station: params.get("station") ?? undefined,
        kind: kind === "local" || kind === "regional" ? kind : undefined,
      };
    }
    case "whatif":
      return { name: "whatif" };
    case "model":
      return { name: "model" };
    case "data":
      return { name: "data" };
    default:
      return { name: "not-found", path };
  }
}

export function routeToHash(route: Route): string {
  const query = (entries: Record<string, string | number | undefined>) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(entries)) if (value !== undefined && value !== "") params.set(key, String(value));
    const text = params.toString();
    return text ? `?${text}` : "";
  };
  switch (route.name) {
    case "home":
      return "#/";
    case "station":
      return `#/station/${encodeURIComponent(route.station)}${query({ for: route.sensitivity, hours: route.hours })}`;
    case "propagation":
      return `#/propagation${query({ frame: route.frame })}`;
    case "anomalies":
      return `#/anomalies${query({ id: route.id, station: route.station, kind: route.kind })}`;
    case "whatif":
      return "#/whatif";
    case "model":
      return "#/model";
    case "data":
      return "#/data";
    case "not-found":
      return `#${route.path}`;
  }
}
