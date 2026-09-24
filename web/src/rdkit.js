import { parseMOL, idealLength } from "./chemistry.js";
import { relax } from "./editor/relax.js";
import { placement, neighbors, point } from "./editor/placement.js";
import { Vector3 } from "three";
let rdkitP = null;
export const getRDKit = () =>
  (rdkitP ??= new Promise((res, rej) => {
    const s = document.createElement("script");
    const packed = document.getElementById("alder-rdkit");
    const embedded = packed ? JSON.parse(packed.textContent) : null;
    const runtime = new URL("vendor/rdkit/", document.baseURI);
    s.src = embedded
      ? "data:text/javascript;base64," + embedded.js
      : new URL("RDKit_minimal.js", runtime).href;
    const fail = (e) => {
      rdkitP = null;
      s.remove();
      rej(e);
    };
    const timer = setTimeout(
      () =>
        fail(
          new Error(
            "The local chemistry engine timed out. Reload Alder and try again.",
          ),
        ),
      45000,
    );
    s.onload = () => {
      if (typeof window.initRDKitModule !== "function") {
        clearTimeout(timer);
        fail(new Error("RDKit failed to initialize"));
        return;
      }
      const options = { locateFile: (name) => new URL(name, runtime).href };
      if (embedded) {
        const binary = atob(embedded.wasm);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        // This pinned MinimalLib exposes instantiateWasm, but omits wasmBinary
        // from its accepted options. Instantiate the embedded bytes directly.
        options.instantiateWasm = (imports, receive) => {
          WebAssembly.instantiate(bytes, imports).then(
            ({ instance }) => receive(instance),
            (error) => {
              clearTimeout(timer);
              fail(error);
            },
          );
          return {};
        };
      }
      window.initRDKitModule(options).then(
        (m) => {
          clearTimeout(timer);
          packed?.remove();
          res(m);
        },
        (e) => {
          clearTimeout(timer);
          fail(e);
        },
      );
    };
    s.onerror = () => {
      clearTimeout(timer);
      fail(
        new Error(
          "The bundled chemistry engine could not load. Re-extract the complete download. File import and editing remain available.",
        ),
      );
    };
    document.head.appendChild(s);
  }));
export function embed3D(mol) {
  const methods = new Set();
  for (let p = mol; p && p !== Object.prototype; p = Object.getPrototypeOf(p))
    for (const n of Object.getOwnPropertyNames(p))
      if (typeof mol[n] === "function") methods.add(n);
  const method = [...methods].find((n) =>
    /^(generate_?3d_?coords|embed_?molecule|embed_?3d)$/i.test(n),
  );
  if (method) {
    try {
      mol[method]();
      const block = mol.get_molblock(),
        m = parseMOL(block);
      if (m.atoms.some((a) => Math.abs(a.z) > 1e-5)) {
        console.info(`[Alder] RDKit 3D path: ${method}`);
        return m;
      }
    } catch (e) {
      console.info("[Alder] Native embedding unavailable:", String(e));
    }
  }
  console.info(
    "[Alder] RDKit has no usable 3D embedding method; using local topology embedding + 400-step relaxation.",
  );
  return null;
}
function ringAtoms(model) {
  const adjacency = model.atoms.map(() => []);
  model.bonds.forEach((b, k) => {
    adjacency[b.a].push([b.b, k]);
    adjacency[b.b].push([b.a, k]);
  });
  const seen = new Int32Array(model.atoms.length),
    low = new Int32Array(model.atoms.length),
    bridges = new Set();
  let time = 0;
  const visit = (i, parentEdge = -1) => {
    seen[i] = low[i] = ++time;
    for (const [j, k] of adjacency[i]) {
      if (k === parentEdge) continue;
      if (!seen[j]) {
        visit(j, k);
        low[i] = Math.min(low[i], low[j]);
        if (low[j] > seen[i]) bridges.add(k);
      } else low[i] = Math.min(low[i], seen[j]);
    }
  };
  for (let i = 0; i < model.atoms.length; i++) if (!seen[i]) visit(i);
  const rings = new Set();
  model.bonds.forEach((b, k) => {
    if (!bridges.has(k)) {
      rings.add(b.a);
      rings.add(b.b);
    }
  });
  return rings;
}
function set(a, p) {
  a.x = p.x;
  a.y = p.y;
  a.z = p.z;
}
function frame(axis) {
  const u = axis
    .clone()
    .cross(Math.abs(axis.y) < 0.9 ? new Vector3(0, 1, 0) : new Vector3(1, 0, 0))
    .normalize();
  return [u, axis.clone().cross(u).normalize()];
}
export async function fallbackEmbed(model) {
  const original = structuredClone(model),
    seen = new Set();
  let component = 0;
  // BFS handles salts/disconnected structures too; no atom is left at the origin by accident.
  for (let root = 0; root < model.atoms.length; root++) {
    if (seen.has(root)) continue;
    set(model.atoms[root], new Vector3(component++ * 6, 0, 0));
    seen.add(root);
    const q = [root];
    while (q.length) {
      const i = q.shift();
      for (const j of neighbors(model, i)) {
        if (seen.has(j)) continue;
        const sub = {
          atoms: model.atoms,
          bonds: model.bonds.filter((b) => seen.has(b.a) && seen.has(b.b)),
        };
        set(model.atoms[j], placement(sub, i, model.atoms[j].el));
        seen.add(j);
        q.push(j);
      }
    }
  }
  await relax(model, 400);
  // The stipulated Tidy energy has no angle/planarity terms. Restore ring topology from RDKit's
  // validated 2D depiction, then use valence geometry for branches; this keeps aromatic rings flat.
  const rings = ringAtoms(original),
    placed = new Set();
  const planar = new Set(
    [...rings].filter((i) =>
      original.bonds.some((b) => (b.a === i || b.b === i) && b.order > 1),
    ),
  );
  if (rings.size) {
    const lengths = original.bonds
        .filter((b) => rings.has(b.a) && rings.has(b.b))
        .map((b) =>
          point(original.atoms[b.a]).distanceTo(point(original.atoms[b.b])),
        )
        .filter((d) => d > 0),
      scale =
        1.39 / (lengths.reduce((s, v) => s + v, 0) / lengths.length || 1.5);
    for (const i of rings) {
      const a = original.atoms[i];
      set(model.atoms[i], point(a).multiplyScalar(scale));
      placed.add(i);
    }
  }
  const heavy = model.atoms
    .map((a, i) => (a.el !== "H" ? i : -1))
    .filter((i) => i >= 0);
  const assignBranch = (i, j, dir) => {
    const b = model.bonds.find(
      (b) => (b.a === i && b.b === j) || (b.b === i && b.a === j),
    );
    set(
      model.atoms[j],
      point(model.atoms[i]).addScaledVector(
        dir,
        idealLength(model.atoms[i].el, model.atoms[j].el, b.order),
      ),
    );
    placed.add(j);
  };
  if (!placed.size && heavy.length) {
    set(model.atoms[heavy[0]], new Vector3());
    placed.add(heavy[0]);
  }
  let pending = true;
  while (pending) {
    pending = false;
    for (const i of [...placed]) {
      const ns = neighbors(model, i),
        missing = ns.filter((j) => !placed.has(j) && model.atoms[j].el !== "H");
      if (!missing.length) continue;
      const existing = ns.filter((j) => placed.has(j)),
        p = point(model.atoms[i]);
      let dir;
      if (rings.has(i)) {
        dir = existing
          .reduce(
            (v, j) => v.sub(point(model.atoms[j]).sub(p).normalize()),
            new Vector3(),
          )
          .normalize();
        if (!dir.lengthSq()) dir.set(1, 0, 0);
      } else if (existing.length) {
        const axis = point(model.atoms[existing[0]]).sub(p).normalize(),
          [u] = frame(axis);
        dir = axis
          .multiplyScalar(-1 / 3)
          .addScaledVector(u, Math.sqrt(8 / 9))
          .normalize();
      } else dir = new Vector3(1, 0, 0);
      missing.forEach((j, k) =>
        assignBranch(
          i,
          j,
          k ? dir.clone().applyAxisAngle(new Vector3(0, 0, 1), k * 2.094) : dir,
        ),
      );
      pending = true;
    }
    if (!pending) {
      const next = heavy.find((i) => !placed.has(i));
      if (next !== undefined) {
        set(model.atoms[next], new Vector3(placed.size * 2, 0, 0));
        placed.add(next);
        pending = true;
      }
    }
  }
  for (const i of heavy) {
    const a = model.atoms[i],
      p = point(a),
      ns = neighbors(model, i),
      hs = ns.filter((j) => model.atoms[j].el === "H"),
      others = ns.filter((j) => model.atoms[j].el !== "H");
    if (!hs.length) continue;
    let dirs = [];
    if (a.el === "O" && hs.length === 2 && others.length === 0) {
      const half = (104.5 * Math.PI) / 360;
      dirs = [
        new Vector3(Math.cos(half), Math.sin(half), 0),
        new Vector3(Math.cos(half), -Math.sin(half), 0),
      ];
    } else if (
      planar.has(i) ||
      model.bonds.some((b) => (b.a === i || b.b === i) && b.order > 1)
    ) {
      const outward = others
        .reduce(
          (v, j) => v.sub(point(model.atoms[j]).sub(p).normalize()),
          new Vector3(),
        )
        .normalize();
      dirs = hs.map((_, k) =>
        outward
          .clone()
          .applyAxisAngle(
            new Vector3(0, 0, 1),
            ((k - (hs.length - 1) / 2) * Math.PI) / 3,
          ),
      );
    } else if (others.length === 1) {
      const axis = point(model.atoms[others[0]]).sub(p).normalize(),
        [u, v] = frame(axis);
      const cos = a.el === "O" ? Math.cos((104.5 * Math.PI) / 180) : -1 / 3;
      dirs = hs.map((_, k) => {
        const angle = (2 * Math.PI * k) / 3 + (i % 2 ? (2 * Math.PI) / 3 : 0);
        return axis
          .clone()
          .multiplyScalar(cos)
          .addScaledVector(u, Math.sqrt(1 - cos * cos) * Math.cos(angle))
          .addScaledVector(v, Math.sqrt(1 - cos * cos) * Math.sin(angle));
      });
    } else if (others.length === 0) {
      dirs = [
        new Vector3(1, 1, 1),
        new Vector3(1, -1, -1),
        new Vector3(-1, 1, -1),
        new Vector3(-1, -1, 1),
      ].map((v) => v.normalize());
    } else {
      const axes = others.map((j) => point(model.atoms[j]).sub(p).normalize()),
        bisector = axes.reduce((v, d) => v.sub(d), new Vector3()).normalize(),
        normal = axes[0].clone().cross(axes[1]).normalize();
      dirs =
        hs.length === 1
          ? [bisector]
          : [
              bisector
                .clone()
                .multiplyScalar(1 / Math.sqrt(3))
                .addScaledVector(normal, Math.sqrt(2 / 3)),
              bisector
                .clone()
                .multiplyScalar(1 / Math.sqrt(3))
                .addScaledVector(normal, -Math.sqrt(2 / 3)),
            ];
    }
    hs.forEach((j, k) => assignBranch(i, j, dirs[k % dirs.length]));
  }
  model.embedding = "approximate";
  return model;
}
export async function smilesToModel(smiles, name = "Molecule") {
  if (!smiles.trim()) throw Error("Enter a SMILES string first.");
  if (smiles.length > 10000)
    throw Error("SMILES exceeds the 10,000-character limit.");
  const rdkit = await getRDKit();
  let mol, hydrogenated;
  try {
    mol = rdkit.get_mol(smiles);
    if (!mol || !mol.is_valid()) throw Error("Invalid SMILES");
    const expanded = mol.add_hs();
    hydrogenated = rdkit.get_mol(expanded);
    if (!hydrogenated || !hydrogenated.is_valid())
      throw Error("Could not add explicit hydrogens.");
    let model = embed3D(hydrogenated);
    if (!model)
      model = await fallbackEmbed(parseMOL(hydrogenated.get_molblock()));
    model.name = name;
    model.smiles = smiles;
    return model;
  } catch (e) {
    throw Error(e instanceof Error ? e.message : "Invalid SMILES");
  } finally {
    hydrogenated?.delete();
    mol?.delete();
  }
}
