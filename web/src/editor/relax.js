import { idealLength, vdWR } from "../chemistry.js";
// ponytail: the requested pairwise relaxer is O(n²). Yield within pair scans, not just between iterations.
export function createRelaxer(model, iterations = 300) {
  const original = model.atoms.map((a) => [a.x, a.y, a.z]),
    n = model.atoms.length,
    bonded = new Set(
      model.bonds.map((b) => Math.min(b.a, b.b) * n + Math.max(b.a, b.b)),
    );
  let iteration = 0;
  const movePair = (d, i, j, target, factor) => {
    const a = model.atoms[i],
      b = model.atoms[j];
    let x = b.x - a.x,
      y = b.y - a.y,
      z = b.z - a.z,
      dist = Math.hypot(x, y, z);
    const axis = dist < 1e-8 ? [1, 0, 0] : [x / dist, y / dist, z / dist],
      error = (dist - target) * factor * 0.5;
    for (let k = 0; k < 3; k++) {
      d[i][k] += axis[k] * error;
      d[j][k] -= axis[k] * error;
    }
  };
  function* steps() {
    while (iteration < iterations) {
      const d = model.atoms.map(() => [0, 0, 0]);
      for (const b of model.bonds.filter(b=>!b.kind))
        movePair(
          d,
          b.a,
          b.b,
          idealLength(model.atoms[b.a].el, model.atoms[b.b].el, b.order),
          0.5,
        );
      let pairs = 0;
      for (let i = 0; i < n; i++)
        for (let j = i + 1; j < n; j++) {
          if (++pairs % 2048 === 0) yield;
          if (bonded.has(i * n + j)) continue;
          const a = model.atoms[i],
            b = model.atoms[j],
            min = 0.8 * ((vdWR[a.el] ?? 1.6) + (vdWR[b.el] ?? 1.6));
          if (Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) < min)
            movePair(d, i, j, min, 1);
        }
      let max = 0;
      model.atoms.forEach((a, i) => {
        for (let k = 0; k < 3; k++)
          d[i][k] += 0.02 * (original[i][k] - a[["x", "y", "z"][k]]);
        const length = Math.hypot(...d[i]);
        if (length > 0.5) for (let k = 0; k < 3; k++) d[i][k] *= 0.5 / length;
        max = Math.max(max, Math.min(length, 0.5));
        a.x += d[i][0];
        a.y += d[i][1];
        a.z += d[i][2];
      });
      iteration++;
      if (max < 1e-4) return;
      yield;
    }
  }
  const iterator = steps();
  return {
    step: () => iterator.next().done,
    get iteration() {
      return iteration;
    },
  };
}
export async function relax(model, iterations = 300, onProgress = () => {}) {
  const r = createRelaxer(model, iterations);
  if (model.atoms.length <= 300) {
    while (!r.step()) {}
    return model;
  }
  let done = false;
  while (!done) {
    const start = performance.now();
    do {
      done = r.step();
    } while (!done && performance.now() - start < 8);
    onProgress(r.iteration / iterations);
    if (!done) await new Promise(requestAnimationFrame);
  }
  return model;
}
