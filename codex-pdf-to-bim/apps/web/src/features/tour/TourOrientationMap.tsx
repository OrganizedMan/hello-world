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
  const x = (value: number) => ((value - minX) / width) * 100;
  const y = (value: number) => ((value - minY) / height) * 64;

  return (
    <svg className="tour-map" viewBox="0 0 100 64" role="img" aria-label="North-up plan of the kitchen, family room, and adjacent openings">
      {orientation.regions.map((region) => {
        const label = regionLabels[region.name] ?? region.name.replaceAll("_", " ");
        return (
          <g key={region.name} data-tour-region={region.name}>
            <rect
              className={`tour-map__region tour-map__region--${region.name}`}
              x={x(region.min_x)}
              y={y(region.min_y)}
              width={x(region.max_x) - x(region.min_x)}
              height={y(region.max_y) - y(region.min_y)}
            />
            <text x={(x(region.min_x) + x(region.max_x)) / 2} y={(y(region.min_y) + y(region.max_y)) / 2}>{label}</text>
          </g>
        );
      })}
      {island ? (
        <g data-tour-region="island">
          <rect className="tour-map__island" x={x(island.min_x)} y={y(island.min_y)} width={x(island.max_x) - x(island.min_x)} height={y(island.max_y) - y(island.min_y)} />
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
