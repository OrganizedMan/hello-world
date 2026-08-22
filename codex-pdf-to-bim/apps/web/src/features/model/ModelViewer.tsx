import { Component, Suspense, useEffect, useMemo, type ReactNode } from "react";
import { Canvas, type ThreeEvent, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { Mesh, Object3D, Vector3 } from "three";


export type CameraPreset = "plan" | "axonometric" | "kitchen" | "living";

type ModelViewerProps = {
  url: string;
  cameraPreset: CameraPreset;
  onSelect: (elementId: string) => void;
};


export class ModelLoadBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="model-viewer__error" role="alert">
          <strong>The 3D model could not be displayed.</strong>
          <span>Build the model again. Your PDF and review answers are still safe.</span>
        </div>
      );
    }
    return this.props.children;
  }
}


const cameraPositions: Record<CameraPreset, { position: [number, number, number]; target: [number, number, number] }> = {
  plan: { position: [6.4, 12, -2.7], target: [6.4, 0, -2.7] },
  axonometric: { position: [13, 9, 8], target: [6.4, 1.1, -2.7] },
  kitchen: { position: [1.2, 1.7, 1.5], target: [4.2, 1.1, -2.2] },
  living: { position: [8.6, 1.7, -7.2], target: [8.3, 1.25, -2.7] },
};


export function canonicalElementIdFromObject(object: Object3D | null): string | null {
  let current: Object3D | null = object;
  while (current) {
    const candidate = current.userData.canonicalElementId;
    if (typeof candidate === "string" && candidate.length > 0) return candidate;
    current = current.parent;
  }
  return null;
}


function CameraRig({ preset }: { preset: CameraPreset }) {
  const { camera } = useThree();

  useEffect(() => {
    const next = cameraPositions[preset];
    camera.position.set(...next.position);
    camera.lookAt(new Vector3(...next.target));
    camera.updateProjectionMatrix();
  }, [camera, preset]);

  return <OrbitControls makeDefault target={cameraPositions[preset].target} minDistance={1.5} maxDistance={30} />;
}


function CanonicalModel({ url, onSelect }: Pick<ModelViewerProps, "url" | "onSelect">) {
  const loaded = useGLTF(url);
  const scene = useMemo(() => {
    const displayScene = loaded.scene.clone(true);
    displayScene.traverse((node) => {
      if (node instanceof Mesh) {
        node.geometry = node.geometry.clone();
        node.geometry.computeVertexNormals();
        node.castShadow = true;
        node.receiveShadow = true;
      }
    });
    return displayScene;
  }, [loaded.scene]);

  function select(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    const elementId = canonicalElementIdFromObject(event.object);
    if (elementId) onSelect(elementId);
  }

  return <primitive object={scene} onClick={select} />;
}


export function ModelViewer({ url, cameraPreset, onSelect }: ModelViewerProps) {
  return (
    <div className="model-viewer" data-camera-preset={cameraPreset}>
      <ModelLoadBoundary>
        <Canvas
          aria-label="Interactive 3D model"
          camera={{ fov: 45, near: 0.05, far: 100, position: cameraPositions.axonometric.position }}
          dpr={[1, 2]}
          shadows
        >
          <color attach="background" args={["#e9e4d9"]} />
          <hemisphereLight args={["#fff4df", "#807567", 2.2]} />
          <directionalLight position={[4, 10, 5]} intensity={2.7} castShadow />
          <Suspense fallback={null}>
            <CanonicalModel url={url} onSelect={onSelect} />
          </Suspense>
          <CameraRig preset={cameraPreset} />
        </Canvas>
      </ModelLoadBoundary>
      <div className="model-viewer__hint">Drag to orbit · scroll to zoom · click a wall or island for its source</div>
    </div>
  );
}
