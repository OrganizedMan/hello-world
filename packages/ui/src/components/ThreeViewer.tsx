import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { FamilyRoomMeshResponse } from '../types'

// Wall mesh vertices/triangles arrive already in metres (the geometry
// package converts nm -> m at the manifold3d boundary; see
// packages/geometry/src/geometry/units_bridge.py), so no scaling happens
// here — a house-sized scene is a very ordinary scale for Three.js.
//
// The geometry package's coordinate convention is Z-up (wall base_z_nm /
// top_z_nm run along local Z — see wall_solid.py's cube dimensions
// [length, thickness, height] and its rotate-about-Z placement). Three.js
// defaults every camera to Y-up. Left uncorrected, OrbitControls' "spin
// around vertical" (horizontal drag) actually spins around a *horizontal*
// building axis instead, which tumbles the model rather than orbiting it
// like a turntable — camera.up is set to Z below specifically to fix that.
const WALL_COLOR = 0xcbd5e1
const UP = new THREE.Vector3(0, 0, 1)

// A horizontal two-finger trackpad swipe (no click held) fires `wheel`
// events with deltaX set — OrbitControls' built-in wheel handler only
// reads deltaY (zoom), so that gesture does nothing by default. This is
// the other half of "azimuth doesn't respond to trackpad input": added
// as a supplementary listener rather than reworked into OrbitControls
// itself, since OrbitControls already exposes rotateLeft() for exactly
// this purpose.
const TRACKPAD_SWIPE_ROTATE_SPEED = 0.0025

type PresetName = 'iso' | 'top' | 'front' | 'side'

interface Props {
  mesh: FamilyRoomMeshResponse | null
}

export function ThreeViewer({ mesh }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container || !mesh) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0f172a)

    const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000)
    camera.up.copy(UP)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    container.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2)
    dirLight.position.set(5, 4, 8) // offset in the (x, y, z-up) sense
    scene.add(dirLight)

    const group = new THREE.Group()
    const box = new THREE.Box3()

    for (const [wallId, data] of Object.entries(mesh)) {
      const geometry = new THREE.BufferGeometry()
      const positions = new Float32Array(data.vertices.flat())
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      geometry.setIndex(data.triangles.flat())
      geometry.computeVertexNormals()

      const material = new THREE.MeshStandardMaterial({
        color: WALL_COLOR,
        roughness: 0.9,
        metalness: 0.0,
        side: THREE.DoubleSide,
      })
      const wallMesh = new THREE.Mesh(geometry, material)
      wallMesh.name = wallId
      group.add(wallMesh)

      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry, 30),
        new THREE.LineBasicMaterial({ color: 0x1e293b }),
      )
      group.add(edges)

      box.expandByObject(wallMesh)
    }
    scene.add(group)

    const gridSize = Math.max(10, box.getSize(new THREE.Vector3()).length())
    const grid = new THREE.GridHelper(gridSize * 2, 20, 0x334155, 0x1e293b)
    grid.rotation.x = Math.PI / 2 // GridHelper defaults to the XZ plane (Y-up); lie flat in XY instead
    scene.add(grid)

    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3()).length() || 10
    controls.target.copy(center)

    const presets: Record<PresetName, THREE.Vector3> = {
      iso: new THREE.Vector3(center.x + size * 0.6, center.y - size * 0.6, center.z + size * 0.5),
      // A camera placed exactly on the up-axis through the target is a
      // singularity for OrbitControls' spherical coordinates (azimuth is
      // undefined) -- nudged fractionally off-axis so "straight down"
      // still resolves to a stable, genuinely top-down view rather than
      // whatever angle the degenerate case happens to fall back to.
      top: new THREE.Vector3(center.x + size * 0.0001, center.y, center.z + size * 1.1),
      front: new THREE.Vector3(center.x, center.y - size, center.z),
      side: new THREE.Vector3(center.x + size, center.y, center.z),
    }
    function goToPreset(name: PresetName) {
      camera.position.copy(presets[name])
      controls.target.copy(center)
      controls.update()
    }
    goToPreset('iso')

    // Trackpad horizontal-swipe -> azimuth rotation (see TRACKPAD_SWIPE_ROTATE_SPEED above).
    function onWheel(event: WheelEvent) {
      if (event.ctrlKey || event.metaKey) return // pinch-zoom gesture: leave to default dolly
      if (Math.abs(event.deltaX) < 2) return // not a meaningfully horizontal swipe
      event.preventDefault()
      controls.rotateLeft(event.deltaX * TRACKPAD_SWIPE_ROTATE_SPEED)
    }
    renderer.domElement.addEventListener('wheel', onWheel, { passive: false })

    function resize() {
      if (!container) return
      const { clientWidth, clientHeight } = container
      camera.aspect = clientWidth / Math.max(clientHeight, 1)
      camera.updateProjectionMatrix()
      renderer.setSize(clientWidth, clientHeight)
    }
    resize()
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(container)

    let frameId: number
    function animate() {
      controls.update()
      renderer.render(scene, camera)
      frameId = requestAnimationFrame(animate)
    }
    animate()

    // Preset buttons: a deterministic way to position the camera that
    // doesn't depend on drag/gesture behavior at all.
    const presetBar = document.createElement('div')
    presetBar.className = 'viewer-preset-bar'
    ;(['iso', 'top', 'front', 'side'] as PresetName[]).forEach((name) => {
      const btn = document.createElement('button')
      btn.textContent = name
      btn.setAttribute('data-testid', `camera-preset-${name}`)
      btn.onclick = () => goToPreset(name)
      presetBar.appendChild(btn)
    })
    container.appendChild(presetBar)

    return () => {
      cancelAnimationFrame(frameId)
      resizeObserver.disconnect()
      renderer.domElement.removeEventListener('wheel', onWheel)
      controls.dispose()
      renderer.dispose()
      container.removeChild(presetBar)
      container.removeChild(renderer.domElement)
    }
  }, [mesh])

  return <div ref={containerRef} className="three-viewer" data-testid="three-viewer" />
}
