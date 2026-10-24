/**
 * Schematic map of Taiwan's main island. The outline is a hand-simplified
 * polygon (good enough to orient stations, not for measurement).
 */
export const TAIWAN_OUTLINE: [number, number][] = [
  [121.56, 25.3], [121.85, 25.13], [122.0, 25.01], [121.83, 24.85], [121.8, 24.6], [121.73, 24.36],
  [121.63, 24.05], [121.5, 23.65], [121.42, 23.4], [121.3, 23.05], [121.15, 22.75], [120.95, 22.4],
  [120.86, 22.0], [120.72, 21.93], [120.62, 22.25], [120.45, 22.47], [120.25, 22.62], [120.15, 22.95],
  [120.1, 23.1], [120.13, 23.45], [120.2, 23.75], [120.35, 24.05], [120.52, 24.3], [120.7, 24.6],
  [120.9, 24.85], [121.05, 25.05], [121.25, 25.12], [121.4, 25.2],
];

export const BOUNDS = { west: 119.95, east: 122.15, south: 21.85, north: 25.4 };

export interface Projection {
  width: number;
  height: number;
  project: (lon: number, lat: number) => [number, number];
}

/** Equirectangular projection with a cos(latitude) correction around 23.7°N. */
export function makeProjection(width: number): Projection {
  const k = Math.cos((23.7 * Math.PI) / 180);
  const spanX = (BOUNDS.east - BOUNDS.west) * k;
  const spanY = BOUNDS.north - BOUNDS.south;
  const height = Math.round((width * spanY) / spanX);
  return {
    width,
    height,
    project: (lon, lat) => [((lon - BOUNDS.west) * k * width) / spanX, ((BOUNDS.north - lat) * height) / spanY],
  };
}

export function outlinePath(projection: Projection): string {
  return (
    TAIWAN_OUTLINE.map(([lon, lat], i) => {
      const [x, y] = projection.project(lon, lat);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ") + " Z"
  );
}
