import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { AdaptiveDpr, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import {
  ACESFilmicToneMapping,
  Euler,
  Mesh,
  Object3D,
  PCFShadowMap,
  SRGBColorSpace,
  Vector3,
} from "three";

import type { TourManifest } from "./TourPage";
import {
  cameraPositionForFloor,
  isWalkablePlacement,
  resolveMovement,
  type Barrier,
  type WalkableBounds,
} from "./tourNavigation";


export type TourMode = "orbit" | "move" | "walk";
export type TourPresetName = "kitchen_overview" | "walk_start" | "overhead";


export function frameLoopForMode(mode: TourMode): "always" | "demand" {
  return mode === "walk" ? "always" : "demand";
}

type TourViewerProps = {
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


function isWalkableObject(object: Object3D | null): boolean {
  let current = object;
  while (current) {
    if (current.name === "HV_WALKABLE") return true;
    current = current.parent;
  }
  return false;
}


export function prepareTourSceneForBrowser(source: Object3D): Object3D {
  const scene = source.clone(true);
  scene.traverse((node) => {
    if (node instanceof Mesh) {
      node.castShadow = true;
      node.receiveShadow = true;
    }
    if ("isLight" in node && node.isLight === true) {
      node.visible = false;
    }
  });
  return scene;
}


export function setOverheadVisibility(scene: Object3D, overhead: boolean): void {
  const ceiling = scene.getObjectByName("HV_CEILING");
  if (ceiling) ceiling.visible = !overhead;
}


function TourExperience({
  manifest,
  mode,
  preset,
  viewRevision,
  onModeChange,
  onReady,
}: Pick<TourViewerProps, "manifest" | "mode" | "preset" | "viewRevision" | "onModeChange" | "onReady">) {
  const { camera, gl } = useThree();
  const loaded = useGLTF(`/tour-spike/${manifest.artifact.glb}`);
  const [orbitTarget, setOrbitTarget] = useState<[number, number, number]>([4.3434, 0.9, -3.0226]);
  const pressedKeys = useRef(new Set<string>());
  const dragging = useRef(false);
  const lastPointer = useRef({ x: 0, y: 0 });
  const heldPointerLock = useRef(false);

  const scene = useMemo(() => prepareTourSceneForBrowser(loaded.scene), [loaded.scene]);

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

  useEffect(() => {
    onReady();
  }, [onReady]);

  useEffect(() => {
    setOverheadVisibility(scene, preset === "overhead" && mode === "orbit");
  }, [mode, preset, scene]);

  useEffect(() => {
    const cameraPreset = presets.get(preset);
    if (!cameraPreset) return;
    camera.position.set(...cameraPreset.position);
    camera.lookAt(new Vector3(...cameraPreset.target));
    camera.updateProjectionMatrix();
    setOrbitTarget([...cameraPreset.target]);
  }, [camera, preset, presets, viewRevision]);

  useEffect(() => {
    if (mode !== "walk") {
      pressedKeys.current.clear();
      if (document.pointerLockElement === gl.domElement) document.exitPointerLock?.();
      return;
    }

    const walkStart = presets.get("walk_start");
    if (!walkStart) return;
    camera.position.set(...walkStart.position);
    camera.lookAt(new Vector3(...walkStart.target));
    camera.updateProjectionMatrix();
  }, [camera, gl.domElement, mode, presets]);

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
    camera.position.set(next.x, manifest.runtime.eye_height_meters, next.z);
  });

  function moveHere(event: ThreeEvent<MouseEvent>) {
    if (mode !== "move" || !isWalkableObject(event.object)) return;
    const floorPoint = { x: event.point.x, y: event.point.y, z: event.point.z };
    if (!isWalkablePlacement(floorPoint, bounds, barriers)) return;
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
      <primitive object={scene} onClick={moveHere} />
      <OrbitControls
        makeDefault
        enabled={mode !== "walk"}
        enableDamping
        dampingFactor={0.08}
        target={orbitTarget}
        minDistance={0.9}
        maxDistance={18}
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
          camera={{ fov: 52, near: 0.05, far: 120, position: initialPosition }}
          dpr={[1, 1.75]}
          frameloop={frameLoopForMode(props.mode)}
          gl={{ antialias: true, outputColorSpace: SRGBColorSpace, toneMapping: ACESFilmicToneMapping }}
          onCreated={({ gl }) => {
            gl.toneMappingExposure = 0.7;
          }}
          shadows={{ type: PCFShadowMap }}
        >
          <color attach="background" args={["#d9d1c3"]} />
          <hemisphereLight args={["#fff4df", "#7b746b", 0.65]} />
          <directionalLight position={[3.8, 8.5, -1.5]} intensity={1.3} castShadow shadow-mapSize={[2048, 2048]} />
          <Suspense fallback={null}>
            <Environment files={`/tour-spike/${props.manifest.artifact.environment}`} environmentIntensity={0.28} />
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
