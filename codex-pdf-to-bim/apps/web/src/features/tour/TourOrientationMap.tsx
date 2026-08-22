import type { TourOrientation, TourRectangle } from "./tourManifest";


const regionLabels: Record<string, string> = {
  kitchen: "Kitchen",
  family_room: "Family room",
  mudroom_context: "Mudroom",
  existing_living_context: "Existing living",
};


type TourOrientationMapProps = {
  orientation: TourOrientation;
  island?: TourRectangle;
};


export function TourOrientationMap({ orientation, island }: TourOrientationMapProps) {
  const rectangles = island ? [...orientation.regions, island] : orientation.regions;
  const minX = Math.min(...rectangles.map((item) => item.min_x));
  const minY = Math.min(...rectangles.map((item) => item.min_y));
  const maxX = Math.max(...rectangles.map((item) => item.max_x));
  const maxY = Math.max(...rectangles.map((item) => item.max_y));
  const width = maxX - minX;
  const height = maxY - minY;
  // Which way the plan is drawn follows the manifest's own north vector, so a
  // frame change in the authoring pipeline cannot silently mirror this map.
  // The traced frame is +y north (a true north-up, east-right plan); the older
  // spike frame is -y north and reads east on screen left, matching the mirror
  // that frame carried in its overhead camera.
  const northIsPlusY = orientation.north_vector[1] > 0;
  const x = northIsPlusY
    ? (value: number) => ((value - minX) / width) * 100
    : (value: number) => ((maxX - value) / width) * 100;
  const y = northIsPlusY
    ? (value: number) => ((maxY - value) / height) * 64
    : (value: number) => ((value - minY) / height) * 64;
  // The projections above run in opposite directions, so rectangles are built
  // from the extremes rather than assuming which edge maps to the smaller
  // screen coordinate.
  const box = (minA: number, maxA: number, project: (value: number) => number) => {
    const a = project(minA);
    const b = project(maxA);
    return { start: Math.min(a, b), length: Math.abs(b - a) };
  };
  const rect = (item: NonNullable<TourRectangle>) => {
    const horizontal = box(item.min_x, item.max_x, x);
    const vertical = box(item.min_y, item.max_y, y);
    return { x: horizontal.start, y: vertical.start, width: horizontal.length, height: vertical.length };
  };

  return (
    <svg className="tour-map" viewBox="0 0 100 64" role="img" aria-label="North-up plan of the kitchen, family room, and adjacent openings">
      {orientation.regions.map((region) => {
        const label = regionLabels[region.name] ?? region.name.replaceAll("_", " ");
        return (
          <g key={region.name} data-tour-region={region.name}>
            <rect
              className={`tour-map__region tour-map__region--${region.name}`}
              {...rect(region)}
            />
            <text x={(x(region.min_x) + x(region.max_x)) / 2} y={(y(region.min_y) + y(region.max_y)) / 2}>{label}</text>
          </g>
        );
      })}
      {island ? (
        <g data-tour-region="island">
          <rect className="tour-map__island" {...rect(island)} />
          <text x={(x(island.min_x) + x(island.max_x)) / 2} y={(y(island.min_y) + y(island.max_y)) / 2}>Island</text>
        </g>
      ) : null}
      {orientation.openings.map((opening) => {
        const footprint = opening.footprint;
        const vertical = opening.wall === "east" || opening.wall === "west";
        return (
          <line
            key={opening.name}
            data-tour-opening={opening.name}
            className={`tour-map__opening tour-map__opening--${opening.name}`}
            x1={x(vertical ? (footprint.min_x + footprint.max_x) / 2 : footprint.min_x)}
            y1={y(vertical ? footprint.min_y : (footprint.min_y + footprint.max_y) / 2)}
            x2={x(vertical ? (footprint.min_x + footprint.max_x) / 2 : footprint.max_x)}
            y2={y(vertical ? footprint.max_y : (footprint.min_y + footprint.max_y) / 2)}
          />
        );
      })}
      <g className="tour-map__north" aria-label="North is up">
        <text x="94" y="8">N</text>
        <path d="M94 18 L94 9 M90.5 12.5 L94 9 L97.5 12.5" />
      </g>
    </svg>
  );
}
