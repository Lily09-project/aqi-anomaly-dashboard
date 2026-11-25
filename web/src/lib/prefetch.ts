import type { Loader } from "./data";
import { parseRoute, routeDatasets } from "./router";

/**
 * Start the opened route's data requests before React renders anything.
 *
 * App also requests these in an effect, but that effect only runs after the first render, which on a slow
 * phone starts the requests several hundred milliseconds after the script arrived. The loader caches the
 * promise, so App's later call reuses this one and nothing is fetched twice. A failed load is dropped from
 * the cache by the loader, and useDataset retries it, so errors are intentionally not reported here.
 */
export function prefetchRoute(loader: Pick<Loader, "load">, hash: string): void {
  for (const name of routeDatasets(parseRoute(hash))) loader.load(name).catch(() => undefined);
}
