import { Vector3 } from "three";
import { idealLength } from "../chemistry.js";
export const point = (a) => new Vector3(a.x, a.y, a.z);
export function neighbors(model, index) {
  return model.bonds
    .filter((b) => b.a === index || b.b === index)
    .map((b) => (b.a === index ? b.b : b.a));
}
export function placement(
  model,
  index,
  el,
  cameraDirection = new Vector3(0, 0, 1),
) {
  const a = model.atoms[index],
    p = point(a),
    c = model.atoms
      .reduce((v, a) => v.add(point(a)), new Vector3())
      .divideScalar(model.atoms.length || 1),
    dirs = neighbors(model, index).map((i) =>
      p.clone().sub(point(model.atoms[i])).normalize(),
    );
  let dir = dirs.length
    ? dirs.reduce((v, d) => v.sub(d), new Vector3()).normalize()
    : p.clone().sub(c).normalize();
  if (dir.lengthSq() < 1e-8) dir.copy(cameraDirection).normalize();
  // The prescribed negative-sum direction can point directly at a neighbor. Break collisions deterministically.
  const occupied = dirs.map((d) => d.clone().negate());
  if (occupied.some((d) => dir.dot(d) > 0.8)) {
    let best = -Infinity;
    for (let i = 0; i < 72; i++) {
      const y = 1 - (2 * (i + 0.5)) / 72,
        r = Math.sqrt(1 - y * y),
        theta = i * 2.3999632297,
        v = new Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r),
        score = Math.min(...occupied.map((d) => -v.dot(d)));
      if (score > best) {
        best = score;
        dir = v;
      }
    }
  }
  return p.addScaledVector(dir, idealLength(a.el, el));
}
