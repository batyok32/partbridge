"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Mouse-driven 3D tilt (perspective + rotateX/Y). Disabled when prefers-reduced-motion.
 */
export function HomeTiltCard({ children, className = "", maxTiltDeg = 11 }) {
  const ref = useRef(null);
  const [transform, setTransform] = useState(
    "perspective(1100px) rotateX(0deg) rotateY(0deg) translateZ(0)",
  );

  const onMove = useCallback(
    (e) => {
      if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        return;
      }
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      const rx = -y * 2 * maxTiltDeg;
      const ry = x * 2 * maxTiltDeg;
      setTransform(
        `perspective(1100px) rotateX(${rx}deg) rotateY(${ry}deg) translateZ(12px) scale3d(1.015,1.015,1.015)`,
      );
    },
    [maxTiltDeg],
  );

  const onLeave = useCallback(() => {
    setTransform("perspective(1100px) rotateX(0deg) rotateY(0deg) translateZ(0) scale3d(1,1,1)");
  }, []);

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{
        transform,
        transition: "transform 0.18s ease-out",
        transformStyle: "preserve-3d",
        willChange: "transform",
      }}
      className={`motion-reduce:transform-none motion-reduce:transition-none ${className}`}
    >
      {children}
    </div>
  );
}
