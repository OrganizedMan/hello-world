import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { AdaptiveDpr, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import {
  AgXToneMapping,
  Box3,
  Camera,
  DirectionalLight,
  DoubleSide,
  Euler,
  Mesh,
  Object3D,
  PCFSoftShadowMap,
  PerspectiveCamera,
  SRGBColorSpace,
  Vector3,
} from "three";

import type { TourCameraPreset, TourManifest } from "./tourManifest";
import {
  boundsOfStoreys,
  ceilingsAreInTheWay,
  isEffectivelyVisible,
  framingForBounds,
  floorBeneath,
  isFloorHit,
  resolvePreset,
  setCeilingVisibility,
  setStoreyVisibility,
} from "./tourFraming";
import {
  cameraPositionForFloor,
  isWalkablePlacement,
  resolveMovement,
  type Barrier,
  type WalkableBounds,
} from "./tourNavigation";

export { isPartOfStorey, setStoreyVisibility } from "./tourFraming";


export type TourMode = "orbit" | "move" | "walk";
export type TourPresetName = "kitchen_overview" | "walk_start" | "overhead";


export function frameLoopForMode(mode: TourMode): "always" | "demand" {
  return mode === "walk" ? "always" : "demand";
}


export function applyCameraPreset(camera: Camera, preset: TourCameraPreset): void {
  const usable = resolvePreset(preset);
  camera.position.set(...usable.position);
  camera.up.set(...usable.up);
  camera.lookAt(new Vector3(...usable.target));
}

type TourViewerProps = {
  /** Public folder the manifest and its artifacts were served from. */
  basePath: string;
  /** Storey nodes to show. Empty means the whole building. */
  visibleStoreys: string[];
  manifest: TourManifest;
  mode: TourMode;
  preset: TourPresetName;
  viewRevision: number;
  onModeChange: (mode: TourMode) => void;
  onReady: () => void;
  onLoadError: () => void;
};

type TourLoadBoundaryProps = {
  children: ReactNode;
  onError: () => void;
};


class TourLoadBoundary extends Component<TourLoadBoundaryProps, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}


export function prepareTourSceneForBrowser(source: Object3D): Object3D {
  const scene = source.clone(true);
  scene.traverse((node) => {
    if (node instanceof Mesh) {
      node.castShadow = true;
      node.receiveShadow = true;
      // Shadows have to be told which side to cast from once the model culls
      // back faces. three.js derives shadowSide from side, and for a
      // front-side material it picks BackSide -- which, with the depth bias
      // these thin walls need, cancelled every shadow in the house and left it
      // looking like white cardboard. The geometry is closed boxes, so casting
      // from both sides is both correct and what the bias was tuned against.
      for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
        if (material) material.shadowSide = DoubleSide;
      }
    }
    if ("isLight" in node && node.isLight === true) {
      node.visible = false;
    }
  });
  return scene;
}


/**
 * A sun fitted to whatever is currently on screen.
 *
 * Two things it has to get right. A directional light's shadow camera is an
 * orthographic box, and three.js defaults it to 5 metres either side of the
 * origin; this house is 12 m by 16 m, so nearly all of it fell outside that
 * box and cast no shadow at all. And the sun has to be *low*. Height was
 * scaled by the model's own height, which for a four-storey stack put it 68
 * degrees up -- overhead noon, whose shadows fall underneath the walls that
 * cast them and are invisible from any useful angle. A fixed slant of about
 * 33 degrees is late afternoon, and its shadows read across a room.
 *
 * Its compass bearing matters as much as its height. The sun started out in
 * the same quarter of the sky as the framing camera, which throws every shadow
 * directly behind the thing casting it -- so the house looked unlit even
 * though the shadow map was working, and turning the light up only produced a
 * brighter unlit house. It now stands about a hundred degrees round from the
 * camera, which is a three-quarter light: the near faces stay lit and the
 * shadows fall across the floor towards the viewer.
 */
function FittedSun({ box }: { box: Box3 | null }) {
  const light = useRef<DirectionalLight>(null);

  const fit = useMemo(() => {
    const bounds = box ?? new Box3(new Vector3(-6, 0, -8), new Vector3(6, 3, 8));
    const centre = bounds.getCenter(new Vector3());
    const size = bounds.getSize(new Vector3());
    // Half-diagonal of the ground plan, with headroom so a low sun still
    // covers the far corner rather than clipping the shadow at the edge.
    const reach = Math.max(1, Math.hypot(size.x, size.z) * 0.62);
    return { centre, reach, height: Math.max(size.y, 3) };
  }, [box]);

  useEffect(() => {
    const current = light.current;
    if (!current) return;
    current.target.position.copy(fit.centre);
    current.target.updateMatrixWorld();
  }, [fit]);

  return (
    <directionalLight
      ref={light}
      position={[
        fit.centre.x + fit.reach * 0.77,
        fit.centre.y + fit.height * 0.5 + fit.reach * 0.95,
        fit.centre.z - fit.reach * 1.24,
      ]}
      intensity={3.2}
      color="#fff1dc"
      castShadow
      shadow-mapSize={[2048, 2048]}
      shadow-camera-left={-fit.reach}
      shadow-camera-right={fit.reach}
      shadow-camera-top={fit.reach}
      shadow-camera-bottom={-fit.reach}
      shadow-camera-near={0.5}
      shadow-camera-far={fit.reach * 6 + fit.height * 4}
      // Walls here are thin boxes seen edge-on, which is the worst case for
      // shadow acne; normalBias moves the sample off the surface instead.
      shadow-bias={-0.00018}
      shadow-normalBias={0.02}
    />
  );
}


/**
 * Vertical field of view per mode.
 *
 * 52 degrees vertical is about 76 across on this canvas, which is a portrait
 * lens: standing in a room, a wall two metres away fills the frame and the
 * space reads as a corridor you cannot look around in. Interiors are shot wide
 * for the same reason -- the reference render is roughly a 20mm lens. Walking
 * gets the widest, orbit stays tighter because it is looking at the model
 * rather than standing in it.
 */
const FIELD_OF_VIEW: Record<TourMode, number> = {
  orbit: 58,
  move: 66,
  walk: 75,
};


export function setOverheadVisibility(scene: Object3D, overhead: boolean): void {
  setCeilingVisibility(scene, overhead);
}


function TourExperience({
  basePath,
  visibleStoreys,
  manifest,
  mode,
  preset,
  viewRevision,
  onModeChange,
  onReady,
}: Pick<TourViewerProps, "basePath" | "visibleStoreys" | "manifest" | "mode" | "preset" | "viewRevision" | "onModeChange" | "onReady">) {
  const { camera, gl } = useThree();
  const loaded = useGLTF(`${basePath}/${manifest.artifact.glb}`);
  const [orbitTarget, setOrbitTarget] = useState<[number, number, number]>([4.3434, 0.9, -3.0226]);
  const [maxDistance, setMaxDistance] = useState(18);
  const pressedKeys = useRef(new Set<string>());
  const dragging = useRef(false);
  const lastPointer = useRef({ x: 0, y: 0 });
  const heldPointerLock = useRef(false);

  const scene = useMemo(() => prepareTourSceneForBrowser(loaded.scene), [loaded.scene]);

  // Held by value, not by identity. The page rebuilds this array on every
  // render, so an effect keyed on the array alone re-ran whenever anything
  // changed -- and the one below reframes the camera, which quietly undid the
  // spot you had just chosen with Move here.
  const storeyKey = visibleStoreys.join("|");
  const storeys = useMemo(() => (storeyKey ? storeyKey.split("|") : []), [storeyKey]);

  // Storeys and ceilings are decided together, in that order. Two effects
  // writing the same `visible` flags would let whichever ran last win, and the
  // ceiling nodes sit inside the storey names the first pass rewrites.
  useEffect(() => {
    setStoreyVisibility(scene, storeys);
    setCeilingVisibility(scene, ceilingsAreInTheWay(mode, preset, storeys), storeys);
  }, [mode, preset, scene, storeys]);

  useEffect(() => {
    if (!(camera instanceof PerspectiveCamera)) return;
    camera.fov = FIELD_OF_VIEW[mode];
    camera.updateProjectionMatrix();
  }, [camera, mode]);

  const bounds = useMemo<WalkableBounds>(() => ({
    minX: manifest.runtime.walkable.min_x,
    maxX: manifest.runtime.walkable.max_x,
    minZ: manifest.runtime.walkable.min_z,
    maxZ: manifest.runtime.walkable.max_z,
  }), [manifest.runtime.walkable]);

  const barriers = useMemo<Barrier[]>(() => manifest.runtime.barriers.map((barrier) => ({
    name: barrier.name,
    minX: barrier.min_x,
    maxX: barrier.max_x,
    minZ: barrier.min_z,
    maxZ: barrier.max_z,
  })), [manifest.runtime.barriers]);

  const presets = useMemo(() => new Map(
    manifest.runtime.camera_presets.map((cameraPreset) => [cameraPreset.name, cameraPreset]),
  ), [manifest.runtime.camera_presets]);

  // Every floor a person could be standing on. The single-storey tour has no
  // storeys listed and only ever stands on zero.
  const storeyBases = useMemo<number[]>(() => {
    const storeys = manifest.schema === "hearthview-tour/v2" ? manifest.storeys ?? [] : [];
    return storeys.length > 0 ? storeys.map((storey) => storey.base_meters) : [0];
  }, [manifest]);

  useEffect(() => {
    onReady();
  }, [onReady]);

  // A handle on the live scene while developing. Every recent defect here --
  // storeys hiding their own geometry, ceilings that could not be switched off,
  // walls wound inside out -- was invisible to the tests and obvious the moment
  // someone opened the graph. Vite drops this from a production build.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (window as unknown as { __hvScene?: Object3D }).__hvScene = scene;
  }, [scene]);

  // Mode is read through a ref, not a dependency. "Move here" finishes by
  // placing the camera and switching back to orbit; if the mode change also
  // re-ran the framing below, it would throw that placement away immediately.
  const modeRef = useRef(mode);
  modeRef.current = mode;

  // One measurement of what is on screen, shared by the camera and the sun.
  const visibleBox = useMemo(() => boundsOfStoreys(scene, storeys), [scene, storeys]);

  useEffect(() => {
    const box = visibleBox;
    if (modeRef.current === "walk") {
      // Switching floors while walking should move you to that floor, not
      // leave you standing at the old one's height inside its ceiling.
      if (box) camera.position.setY(box.min.y + manifest.runtime.eye_height_meters);
      return;
    }

    if (!box) {
      const cameraPreset = presets.get(preset);
      if (!cameraPreset) return;
      applyCameraPreset(camera, cameraPreset);
      setOrbitTarget([...cameraPreset.target]);
      return;
    }

    const framing = framingForBounds(box, {
      fovDegrees: FIELD_OF_VIEW.orbit,
      aspect: camera instanceof PerspectiveCamera ? camera.aspect : 1.6,
      overhead: preset === "overhead",
    });
    camera.up.set(0, 1, 0);
    camera.position.set(...framing.position);
    camera.lookAt(new Vector3(...framing.target));
    setOrbitTarget(framing.target);
    // The default 18m ceiling on orbit distance is shorter than the whole
    // house needs, so the controls pulled the camera back in on the frame
    // after it was placed.
    setMaxDistance(Math.max(18, framing.distance * 1.6));
  }, [camera, manifest.runtime.eye_height_meters, preset, presets, viewRevision, visibleBox]);

  useEffect(() => {
    if (mode !== "walk") {
      pressedKeys.current.clear();
      if (document.pointerLockElement === gl.domElement) document.exitPointerLock?.();
      return;
    }

    const walkStart = presets.get("walk_start");
    if (!walkStart) return;
    applyCameraPreset(camera, walkStart);
    // walk_start is a spot on the first floor. Walking a storey you picked
    // upstairs has to start on that storey's slab, or you spend the walk
    // buried in the floor below.
    if (visibleBox) camera.position.setY(visibleBox.min.y + manifest.runtime.eye_height_meters);
  }, [camera, gl.domElement, manifest.runtime.eye_height_meters, mode, presets, visibleBox]);

  useEffect(() => {
    const canvas = gl.domElement;
    const rotation = new Euler(0, 0, 0, "YXZ");

    function rotateView(deltaX: number, deltaY: number) {
      rotation.setFromQuaternion(camera.quaternion, "YXZ");
      rotation.y -= deltaX * 0.0022;
      rotation.x = Math.max(-Math.PI / 2 + 0.08, Math.min(Math.PI / 2 - 0.08, rotation.x - deltaY * 0.0022));
      camera.quaternion.setFromEuler(rotation);
    }

    function keyDown(event: KeyboardEvent) {
      if (mode !== "walk") return;
      if (event.key === "Escape") {
        onModeChange("orbit");
        return;
      }
      const key = event.key.toLowerCase();
      if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"].includes(key)) {
        event.preventDefault();
        pressedKeys.current.add(key);
      }
    }

    function keyUp(event: KeyboardEvent) {
      pressedKeys.current.delete(event.key.toLowerCase());
    }

    function pointerDown(event: PointerEvent) {
      if (mode !== "walk") return;
      dragging.current = true;
      lastPointer.current = { x: event.clientX, y: event.clientY };
      if (document.pointerLockElement !== canvas) {
        const lockResult = canvas.requestPointerLock?.();
        if (lockResult && "catch" in lockResult) void lockResult.catch(() => undefined);
      }
    }

    function pointerMove(event: PointerEvent) {
      if (mode !== "walk") return;
      if (document.pointerLockElement === canvas) {
        rotateView(event.movementX, event.movementY);
      } else if (dragging.current) {
        rotateView(event.clientX - lastPointer.current.x, event.clientY - lastPointer.current.y);
        lastPointer.current = { x: event.clientX, y: event.clientY };
      }
    }

    function pointerUp() {
      dragging.current = false;
    }

    function pointerLockChanged() {
      if (document.pointerLockElement === canvas) {
        heldPointerLock.current = true;
      } else if (heldPointerLock.current && mode === "walk") {
        heldPointerLock.current = false;
        onModeChange("orbit");
      }
    }

    function clearMovement() {
      pressedKeys.current.clear();
      dragging.current = false;
    }

    window.addEventListener("keydown", keyDown);
    window.addEventListener("keyup", keyUp);
    window.addEventListener("blur", clearMovement);
    canvas.addEventListener("pointerdown", pointerDown);
    window.addEventListener("pointermove", pointerMove);
    window.addEventListener("pointerup", pointerUp);
    document.addEventListener("pointerlockchange", pointerLockChanged);
    return () => {
      window.removeEventListener("keydown", keyDown);
      window.removeEventListener("keyup", keyUp);
      window.removeEventListener("blur", clearMovement);
      canvas.removeEventListener("pointerdown", pointerDown);
      window.removeEventListener("pointermove", pointerMove);
      window.removeEventListener("pointerup", pointerUp);
      document.removeEventListener("pointerlockchange", pointerLockChanged);
    };
  }, [camera, gl.domElement, mode, onModeChange]);

  useFrame((_, frameDelta) => {
    if (mode !== "walk") return;
    const keys = pressedKeys.current;
    const forwardInput = Number(keys.has("w") || keys.has("arrowup")) - Number(keys.has("s") || keys.has("arrowdown"));
    const rightInput = Number(keys.has("d") || keys.has("arrowright")) - Number(keys.has("a") || keys.has("arrowleft"));
    if (forwardInput === 0 && rightInput === 0) return;

    const forward = camera.getWorldDirection(new Vector3());
    forward.y = 0;
    if (forward.lengthSq() < 0.0001) forward.set(0, 0, -1);
    forward.normalize();
    const right = new Vector3().crossVectors(forward, camera.up).normalize();
    const movement = forward.multiplyScalar(forwardInput).add(right.multiplyScalar(rightInput));
    if (movement.lengthSq() > 1) movement.normalize();
    movement.multiplyScalar(1.8 * Math.min(frameDelta, 0.05));

    const next = resolveMovement(
      { x: camera.position.x, z: camera.position.z },
      { x: movement.x, z: movement.z },
      barriers,
      bounds,
      0.3,
    );
    camera.position.set(next.x, camera.position.y, next.z);
  });

  function moveHere(event: ThreeEvent<MouseEvent>) {
    if (mode !== "move") return;
    if (!isEffectivelyVisible(event.object)) return;
    if (!isFloorHit(event.point, event.face?.normal, storeyBases)) return;
    const floor = floorBeneath(event.point.y, storeyBases);
    const floorPoint = { x: event.point.x, y: floor, z: event.point.z };
    if (!isWalkablePlacement(floorPoint, bounds, barriers, floor)) return;
    event.stopPropagation();

    const nextPosition = cameraPositionForFloor(floorPoint, manifest.runtime.eye_height_meters);
    const forward = camera.getWorldDirection(new Vector3());
    forward.y = 0;
    if (forward.lengthSq() < 0.0001) forward.set(1, 0, 0);
    forward.normalize();
    const nextTarget: [number, number, number] = [
      nextPosition.x + forward.x * 2.4,
      nextPosition.y - 0.3,
      nextPosition.z + forward.z * 2.4,
    ];
    camera.position.set(nextPosition.x, nextPosition.y, nextPosition.z);
    camera.lookAt(new Vector3(...nextTarget));
    setOrbitTarget(nextTarget);
    onModeChange("orbit");
  }

  return (
    <>
      <FittedSun box={visibleBox} />
      <primitive object={scene} onClick={moveHere} />
      <OrbitControls
        makeDefault
        enabled={mode !== "walk"}
        enableDamping
        dampingFactor={0.08}
        target={orbitTarget}
        minDistance={0.9}
        maxDistance={maxDistance}
        maxPolarAngle={Math.PI / 2.02}
      />
    </>
  );
}


export function TourViewer(props: TourViewerProps) {
  const initialPreset = props.manifest.runtime.camera_presets.find((preset) => preset.name === "kitchen_overview");
  const initialPosition = initialPreset?.position ?? [0.7, 1.65, -4.3014];

  return (
    <div className="tour-viewer" data-tour-mode={props.mode}>
      <TourLoadBoundary onError={props.onLoadError}>
        <Canvas
          aria-label="Interactive tour of the proposed kitchen and family room"
          camera={{ fov: FIELD_OF_VIEW.orbit, near: 0.05, far: 160, position: initialPosition }}
          dpr={[1, 1.75]}
          frameloop={frameLoopForMode(props.mode)}
          // AgX is the transform the Cycles stills were graded through. ACES
          // pushed the warm plaster towards orange and clipped the daylight,
          // which is a large part of why the browser and the renders did not
          // look like the same building.
          gl={{ antialias: true, outputColorSpace: SRGBColorSpace, toneMapping: AgXToneMapping }}
          onCreated={({ gl }) => {
            gl.toneMappingExposure = 0.95;
          }}
          shadows={{ type: PCFSoftShadowMap }}
        >
          <color attach="background" args={["#d9d1c3"]} />
          <Suspense fallback={null}>
            {/* The sky is the outdoor view: it is what shows through every
                window and door, and it is the light in the room. It was being
                used at 0.3 strength and hidden behind a flat beige page
                colour, so the house stood in a void lit by nothing. */}
            <Environment
              files={`${props.basePath}/${props.manifest.artifact.environment}`}
              background
              backgroundIntensity={0.7}
              environmentIntensity={0.7}
            />
            <TourExperience {...props} />
          </Suspense>
          <AdaptiveDpr pixelated />
        </Canvas>
      </TourLoadBoundary>
      <div className="tour-viewer__gesture" aria-hidden="true">
        {props.mode === "move" ? "Choose a clear spot on the floor" : props.mode === "walk" ? "Click the room, then look and walk" : "Drag to orbit · scroll to zoom"}
      </div>
    </div>
  );
}
