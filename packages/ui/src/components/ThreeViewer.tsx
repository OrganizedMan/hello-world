import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { FamilyRoomMeshResponse } from '../types'

// Wall mesh vertices/triangles arrive already in metres (the geometry
// package converts nm -> m at the manifold3d boundary; see
// packages/geometry/src/geometry/units_bridge.py), so no scaling happens
// here — a house-sized scene is a very ordinary scale for Three.js.
const WALL_COLOR = 0xcbd5e1

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
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    container.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2)
    dirLight.position.set(5, 8, 4)
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
    scene.add(grid)

    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3()).length()
    camera.position.set(center.x + size * 0.6, center.y + size * 0.5, center.z + size * 0.6)
    controls.target.copy(center)
    controls.update()

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

    return () => {
      cancelAnimationFrame(frameId)
      resizeObserver.disconnect()
      controls.dispose()
      renderer.dispose()
      container.removeChild(renderer.domElement)
    }
  }, [mesh])

  return <div ref={containerRef} className="three-viewer" data-testid="three-viewer" />
}
