// src/components/Background3D.jsx
import { Canvas } from "@react-three/fiber";
import { Points, PointMaterial, OrbitControls } from "@react-three/drei";
import { useMemo } from "react";

export default function Background3D() {
  const stars = useMemo(() => {
    const count = 9000;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) {
      arr[i] = (Math.random() - 0.5) * 30;
    }
    return arr;
  }, []);

  return (
    <Canvas
      className="bg3d"
      camera={{ position: [0, 0, 12], fov: 60 }}
    >
      <Points positions={stars} stride={3} frustumCulled={false}>
        <PointMaterial
          transparent
          color="#8257e6"
          size={0.035}
          sizeAttenuation
          depthWrite={false}
        />
      </Points>

      <OrbitControls autoRotate autoRotateSpeed={0.4} enableZoom={false} />
    </Canvas>
  );
}
