import { Component, lazy, Suspense, useEffect, useMemo, useRef, type ReactNode } from "react";
import { LoaderContext, useDocumentTitle, useRoute } from "./app/hooks";
import { Shell } from "./components/Shell";
import { EmptyState, ErrorState, Loading } from "./components/States";
import { createLoader, type Loader } from "./lib/data";
import { routeDatasets, routeToHash, type Route } from "./lib/router";
import Home from "./routes/Home";

const Planner = lazy(() => import("./routes/Planner"));
const Station = lazy(() => import("./routes/Station"));
const PropagationPage = lazy(() => import("./routes/Propagation"));
const AnomaliesPage = lazy(() => import("./routes/Anomalies"));
const WhatIfPage = lazy(() => import("./routes/WhatIf"));
const ModelPage = lazy(() => import("./routes/Model"));
const DataTrust = lazy(() => import("./routes/DataTrust"));

function NotFound({ path }: { path: string }) {
  useDocumentTitle("找不到這個頁面");
  return (
    <div className="page">
      <EmptyState title="找不到這個頁面" asPageTitle>
        <p>
          網址 <code>{path}</code> 不存在。<a href={routeToHash({ name: "home" })}>回到空品總覽</a>
        </p>
      </EmptyState>
    </div>
  );
}

const routeKey = (route: Route) => (route.name === "station" ? `station-${route.station}` : route.name);

/** Show the page error state instead of unmounting the whole site; navigating away clears it. */
class ErrorBoundary extends Component<{ resetKey: string; children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error : new Error(String(error)) };
  }

  componentDidUpdate(previous: { resetKey: string }) {
    if (previous.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render() {
    return this.state.error ? (
      <div className="page">
        <ErrorState error={this.state.error} />
      </div>
    ) : (
      this.props.children
    );
  }
}

function Routes({ route }: { route: Route }) {
  const key = routeKey(route);

  switch (route.name) {
    case "home":
      return <Home />;
    case "station":
      return <Station key={key} station={route.station} sensitivity={route.sensitivity ?? "sensitive"} hours={route.hours ?? 2} />;
    case "planner":
      return <Planner route={route} />;
    case "propagation":
      return <PropagationPage frame={route.frame} />;
    case "anomalies":
      return <AnomaliesPage id={route.id} station={route.station} kind={route.kind} />;
    case "whatif":
      return <WhatIfPage />;
    case "model":
      return <ModelPage />;
    case "data":
      return <DataTrust />;
    case "not-found":
      return <NotFound path={route.path} />;
  }
}

export default function App({ loader }: { loader?: Loader }) {
  const value = useMemo(() => loader ?? createLoader(import.meta.env.BASE_URL), [loader]);
  const [route] = useRoute();
  const key = routeKey(route);
  const previousKey = useRef(key);
  const datasets = routeDatasets(route).join(",");

  // Start the route's data requests alongside its lazy code chunk; useDataset later reuses the cached promise.
  // Errors surface through useDataset, which retries after a failed load.
  useEffect(() => {
    for (const name of datasets ? (datasets.split(",") as ReturnType<typeof routeDatasets>) : []) value.load(name).catch(() => undefined);
  }, [value, datasets]);

  // The shell is available even when the next route's module is still loading.
  useEffect(() => {
    if (previousKey.current === key) return;
    previousKey.current = key;
    window.scrollTo({ top: 0 });
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [key]);

  return (
    <LoaderContext.Provider value={value}>
      <Shell>
        <ErrorBoundary resetKey={routeKey(route)}>
          <Suspense
            fallback={
              <div className="page">
                <Loading label="頁面載入中" />
              </div>
            }
          >
            <Routes route={route} />
          </Suspense>
        </ErrorBoundary>
      </Shell>
    </LoaderContext.Provider>
  );
}
