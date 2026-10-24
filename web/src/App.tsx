import { lazy, Suspense, useEffect, useMemo, useRef } from "react";
import { LoaderContext, useRoute } from "./app/hooks";
import { Shell } from "./components/Shell";
import { EmptyState, Loading } from "./components/States";
import { createLoader, type Loader } from "./lib/data";
import { routeToHash } from "./lib/router";
import Home from "./routes/Home";

const Station = lazy(() => import("./routes/Station"));
const PropagationPage = lazy(() => import("./routes/Propagation"));
const AnomaliesPage = lazy(() => import("./routes/Anomalies"));
const WhatIfPage = lazy(() => import("./routes/WhatIf"));
const ModelPage = lazy(() => import("./routes/Model"));
const DataTrust = lazy(() => import("./routes/DataTrust"));

function Routes() {
  const [route] = useRoute();
  const first = useRef(true);
  const key = route.name === "station" ? `station-${route.station}` : route.name;

  // Move focus to the new page for keyboard and screen-reader users.
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo({ top: 0 });
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [key]);

  switch (route.name) {
    case "home":
      return <Home />;
    case "station":
      return <Station key={key} station={route.station} sensitivity={route.sensitivity ?? "sensitive"} hours={route.hours ?? 2} />;
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
      return (
        <div className="page">
          <EmptyState title="找不到這個頁面">
            <p>
              網址 <code>{route.path}</code> 不存在。<a href={routeToHash({ name: "home" })}>回到即時總覽</a>
            </p>
          </EmptyState>
        </div>
      );
  }
}

export default function App({ loader }: { loader?: Loader }) {
  const value = useMemo(() => loader ?? createLoader(import.meta.env.BASE_URL), [loader]);
  return (
    <LoaderContext.Provider value={value}>
      <Shell>
        <Suspense
          fallback={
            <div className="page">
              <Loading label="頁面載入中" />
            </div>
          }
        >
          <Routes />
        </Suspense>
      </Shell>
    </LoaderContext.Provider>
  );
}
