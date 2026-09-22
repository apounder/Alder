import { Vector3, MathUtils } from "three";
const V = (a) => new Vector3(a.x, a.y, a.z);
export function measure(atoms, indices) {
  if (indices.length < 2 || indices.length > 4) return null;
  const p = indices.map((i) => V(atoms[i]));
  if (p.length === 2)
    return { kind: "Distance", value: p[0].distanceTo(p[1]), unit: "Å" };
  if (p.length === 3) {
    const a = p[0].clone().sub(p[1]),
      b = p[2].clone().sub(p[1]);
    if (a.lengthSq() < 1e-12 || b.lengthSq() < 1e-12)
      return { kind: "Angle", value: NaN, unit: "°" };
    return {
      kind: "Angle",
      value: MathUtils.radToDeg(
        Math.acos(MathUtils.clamp(a.normalize().dot(b.normalize()), -1, 1)),
      ),
      unit: "°",
    };
  }
  const b1 = p[1].clone().sub(p[0]),
    b2 = p[2].clone().sub(p[1]),
    b3 = p[3].clone().sub(p[2]),
    n1 = b1.clone().cross(b2),
    n2 = b2.clone().cross(b3);
  if (n1.lengthSq() < 1e-12 || n2.lengthSq() < 1e-12)
    return { kind: "Dihedral", value: NaN, unit: "°" };
  const m = n1.clone().cross(b2.clone().normalize());
  return {
    kind: "Dihedral",
    value: (MathUtils.radToDeg(Math.atan2(-m.dot(n2), n1.dot(n2))) + 180) % 360 - 180,
    unit: "°",
  };
}
export const measurementText = (m) =>
  m
    ? Number.isFinite(m.value)
      ? `${m.value.toFixed(m.unit === "Å" ? 2 : 1)} ${m.unit}`
      : "Undefined (collinear atoms)"
    : "";
