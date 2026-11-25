import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { createLoader } from "./lib/data";
import { prefetchRoute } from "./lib/prefetch";
import "./styles/tokens.css";
import "./styles/global.css";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root element");

// Request the opened route's data now instead of after React's first render (see lib/prefetch.ts).
const loader = createLoader(import.meta.env.BASE_URL);
prefetchRoute(loader, window.location.hash);

createRoot(root).render(
  <StrictMode>
    <App loader={loader} />
  </StrictMode>,
);
