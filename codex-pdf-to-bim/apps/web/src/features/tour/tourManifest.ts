import { z } from "zod";


const vector2Schema = z.tuple([z.number().finite(), z.number().finite()]);
const vector3Schema = z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]);
const hashSchema = z.string().regex(/^[0-9a-f]{64}$/);

const rectangleSchema = z.object({
  name: z.string().min(1),
  min_x: z.number().finite(),
  min_y: z.number().finite(),
  max_x: z.number().finite(),
  max_y: z.number().finite(),
}).refine((value) => value.max_x > value.min_x && value.max_y > value.min_y, {
  message: "rectangle bounds must have positive area",
});

const openingSchema = z.object({
  name: z.string().min(1),
  wall: z.enum(["north", "east", "south", "west"]),
  footprint: rectangleSchema,
});

const cameraPresetSchema = z.object({
  name: z.enum(["kitchen_overview", "walk_start", "overhead"]),
  position: vector3Schema,
  target: vector3Schema,
  up: vector3Schema,
});

const provenanceSchema = z.object({
  verified_percent: z.number().min(0).max(100),
  measured: z.array(z.string().min(1)).min(1),
  assumed: z.array(z.string().min(1)),
  absent_from_drawing_set: z.string().min(1),
  approximated_wall_segments: z.number().int().nonnegative(),
});

const sharedSchema = z.object({
  orientation: z.object({
    bounds: rectangleSchema,
    north_vector: vector2Schema,
    north_up: z.literal(true),
    regions: z.array(rectangleSchema).min(2),
    openings: z.array(openingSchema).min(1),
  }).superRefine((orientation, context) => {
    // North must lie on the plan's vertical axis so the minimap can be drawn
    // north-up. Which sign points north is the authoring frame's business: the
    // traced pipeline is +y north, the older spike frame is -y north.
    if (orientation.north_vector[0] !== 0 || Math.abs(orientation.north_vector[1]) !== 1) {
      context.addIssue({ code: "custom", message: "tour orientation must use canonical north" });
    }
  }),
  provisional_categories: z.array(z.string()).superRefine((categories, context) => {
    for (const required of ["cabinetry_detail", "hardware", "finishes", "furniture", "decor", "undimensioned_offsets"]) {
      if (!categories.includes(required)) {
        context.addIssue({ code: "custom", message: `missing provisional category: ${required}` });
      }
    }
  }),
  artifact: z.object({
    glb: z.string().min(1).regex(/^[\w.-]+\.glb$/),
    poster: z.string().min(1),
    environment: z.string().min(1),
    total_browser_bytes: z.number().int().positive().max(45_000_000),
  }),
  runtime: z.object({
    eye_height_meters: z.number().positive().max(2.2),
    walkable: z.object({
      min_x: z.number().finite(),
      max_x: z.number().finite(),
      min_z: z.number().finite(),
      max_z: z.number().finite(),
    }),
    barriers: z.array(z.object({
      name: z.string().min(1),
      min_x: z.number().finite(),
      max_x: z.number().finite(),
      min_z: z.number().finite(),
      max_z: z.number().finite(),
    })),
    camera_presets: z.array(cameraPresetSchema).superRefine((presets, context) => {
      for (const required of ["kitchen_overview", "walk_start", "overhead"] as const) {
        if (!presets.some((preset) => preset.name === required)) {
          context.addIssue({ code: "custom", message: `missing camera preset: ${required}` });
        }
      }
    }),
  }),
}).passthrough();

/** The original hand-built kitchen spike: staging, explicitly not measured. */
const spikeManifestSchema = sharedSchema.extend({
  schema: z.literal("hearthview-tour-spike/v1"),
  label: z.literal("Quality spike · visual staging"),
  canonical_geometry: z.literal(false),
  canonical_model_hash: hashSchema,
  canonical_geometry_hash: hashSchema,
  island_footprint: rectangleSchema,
});

/** The A-1 trace tour: geometry lifted from the drawing, provenance declared. */
const tracedManifestSchema = sharedSchema.extend({
  schema: z.literal("hearthview-tour/v2"),
  label: z.string().min(1),
  canonical_geometry: z.literal(true),
  source: z.object({
    sheet: z.string().min(1),
    page: z.number().int().positive(),
    view: z.string().min(1),
    points_per_foot: z.number().positive(),
  }),
  provenance: provenanceSchema,
  island_footprint: rectangleSchema.optional(),
});

export const manifestSchema = z.discriminatedUnion("schema", [
  spikeManifestSchema,
  tracedManifestSchema,
]);


export type TourManifest = z.infer<typeof manifestSchema>;
export type TourOrientation = TourManifest["orientation"];
export type TourRectangle = TourManifest["island_footprint"];
export type TourCameraPreset = TourManifest["runtime"]["camera_presets"][number];


export function parseTourManifest(value: unknown): TourManifest {
  return manifestSchema.parse(value);
}
