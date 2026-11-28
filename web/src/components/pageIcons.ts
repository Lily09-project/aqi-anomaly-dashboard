import type { Route } from "../lib/router";
import type { IconName } from "./Icon";

/** One icon per page, shared by the navigation and the overview's chapter cards. */
export const PAGE_ICON: Record<Route["name"], IconName> = {
  home: "gauge",
  station: "gauge",
  propagation: "wind",
  anomalies: "activity",
  whatif: "sliders",
  model: "shield",
  planner: "route",
  data: "database",
  "not-found": "inbox",
};
