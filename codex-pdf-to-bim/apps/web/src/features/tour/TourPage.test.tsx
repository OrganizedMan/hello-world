import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TourPage } from "./TourPage";


vi.mock("./TourViewer", () => ({
  TourViewer: ({ mode, onReady }: { mode: string; onReady: () => void }) => {
    queueMicrotask(onReady);
    return <div data-testid="tour-viewer" data-mode={mode}>Room canvas</div>;
  },
}));


const manifest = {
  schema: "hearthview-tour-spike/v1",
  label: "Quality spike · visual staging",
  canonical_geometry: false,
  provisional_categories: [
    "cabinetry_detail",
    "hardware",
    "finishes",
    "furniture",
    "decor",
    "undimensioned_offsets",
  ],
  artifact: {
    glb: "hearthview-kitchen-family.glb",
    poster: "poster.webp",
    environment: "environment.hdr",
    total_browser_bytes: 24_604_690,
  },
  runtime: {
    eye_height_meters: 1.65,
    walkable: { min_x: 0.18, max_x: 8.9894, min_z: -4.6714, max_z: -0.18 },
    barriers: [
      { name: "island", min_x: 1.7272, max_x: 4.3434, min_z: -3.0226, max_z: -1.7272 },
    ],
    camera_presets: [
      { name: "kitchen_overview", position: [0.7, 1.65, -4.3014], target: [4.3434, 0.9, -3.0226] },
      { name: "walk_start", position: [4.15, 1.65, -4.2014], target: [5.2, 1.65, -2.1] },
      { name: "overhead", position: [4.5847, 8, -2.4257], target: [4.5847, 0, -2.4257] },
    ],
  },
};


function successfulResponse() {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(manifest),
  } as Response);
}


describe("TourPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(successfulResponse));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("gives homeowners labeled controls, recovery, and plain-language guidance", async () => {
    const user = userEvent.setup();
    render(<TourPage />);

    expect(await screen.findByRole("heading", { name: "Explore the proposed kitchen and family room" })).toBeVisible();
    for (const control of ["Orbit", "Move here", "Walk", "Overhead", "Reset"]) {
      expect(screen.getByRole("button", { name: control })).toBeVisible();
    }
    const walkingGuide = screen.getByText("While walking").parentElement;
    expect(walkingGuide).toHaveTextContent(/WASD or arrow keys/i);
    expect(walkingGuide).toHaveTextContent(/mouse or drag to look/i);
    expect(screen.getByText("Quality spike · visual staging")).toBeVisible();
    expect(screen.getByText(/furniture, décor, and finishes are provisional/i)).toBeVisible();
    expect(screen.getByText(/stays on this Mac/i)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Walk" }));
    expect(screen.getByRole("button", { name: "Exit walk" })).toBeVisible();
    expect(screen.getByRole("status", { name: "Tour mode" })).toHaveTextContent("Walk mode");

    await user.click(screen.getByRole("button", { name: "Exit walk" }));
    expect(screen.queryByRole("button", { name: "Exit walk" })).not.toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Tour mode" })).toHaveTextContent("Orbit mode");
  });

  it("shows loading progress while the local manifest is opening", () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}));

    render(<TourPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Preparing your room");
    expect(screen.getByRole("progressbar", { name: "Room loading progress" })).toBeVisible();
  });

  it("offers a retry when the local artifact cannot be opened", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch)
      .mockRejectedValueOnce(new Error("disk read failed"))
      .mockImplementation(successfulResponse);

    render(<TourPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("The room could not be opened");
    await user.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(screen.getByTestId("tour-viewer")).toBeVisible());
  });
});
