import LZString from "lz-string";
import { Color } from "three";
import { validateModel } from "./chemistry.js";
const pad = (v, n) => String(v).padStart(n, " "),
  fixed = (v, n = 10) => pad(v.toFixed(4), n);
export const safeName = (name) =>
  name.replace(/[^a-zA-Z0-9_-]+/g, "_").slice(0, 80) || "molecule";
export function writeXYZ(model) {
  return (
    `${model.atoms.length}\n${model.name.replace(/[\r\n]/g, " ")}\n` +
    model.atoms
      .map((a) => `${a.el.padEnd(2)} ${fixed(a.x)} ${fixed(a.y)} ${fixed(a.z)}`)
      .join("\n") +
    "\n"
  );
}
export function writeMOL(model) {
  if (model.atoms.length > 999 || model.bonds.length > 999)
    throw Error(
      "V2000 supports at most 999 atoms and 999 bonds. Export XYZ or PDB instead.",
    );
  if (
    model.atoms.some((a) =>
      [a.x, a.y, a.z].some((x) => x.toFixed(4).length > 10),
    )
  )
    throw Error("Coordinates exceed the V2000 field width.");
  let s = `${model.name.replace(/[\r\n]/g, " ")}\n  MolStudio         3D\n\n${pad(model.atoms.length, 3)}${pad(model.bonds.length, 3)}  0  0  0  0            999 V2000\n`;
  s +=
    model.atoms
      .map(
        (a) =>
          `${fixed(a.x)}${fixed(a.y)}${fixed(a.z)} ${a.el.padEnd(3)} 0  0  0  0  0  0  0  0  0  0  0  0`,
      )
      .join("\n") + "\n";
  s +=
    model.bonds
      .map(
        (b) =>
          `${pad(b.a + 1, 3)}${pad(b.b + 1, 3)}${pad(b.order, 3)}  0  0  0  0`,
      )
      .join("\n") + (model.bonds.length ? "\n" : "");
  const charges = model.atoms
    .map((a, i) => [i + 1, a.charge || 0])
    .filter(([, c]) => c);
  for (let i = 0; i < charges.length; i += 8) {
    const chunk = charges.slice(i, i + 8);
    s +=
      `M  CHG${pad(chunk.length, 3)}` +
      chunk.map(([n, c]) => pad(n, 4) + pad(c, 4)).join("") +
      "\n";
  }
  for(const [field,tag] of [['isotope','ISO'],['radical','RAD']]) {
    const entries=model.atoms.map((a,i)=>[i+1,a[field]||0]).filter(([,v])=>v);
    for(let i=0;i<entries.length;i+=8) {
      const chunk=entries.slice(i,i+8);
      s+=`M  ${tag}${pad(chunk.length,3)}`+chunk.map(([n,v])=>pad(n,4)+pad(tag==='RAD'?(v===1?2:3):v,4)).join('')+'\n';
    }
  }
  return s + "M  END\n";
}
export function writePDB(model) {
  if (
    model.atoms.some((a) =>
      [a.x, a.y, a.z].some((n) => n.toFixed(3).length > 8),
    )
  )
    throw Error("Coordinates exceed the PDB field width.");
  let s = `TITLE     ${model.name.replace(/[\r\n]/g, " ").slice(0, 69)}\n`;
  s +=
    model.atoms
      .map(
        (a, i) =>
          `HETATM${pad(i + 1, 5)} ${(" " + a.el).padEnd(4)} MOL A   1    ${pad(a.x.toFixed(3), 8)}${pad(a.y.toFixed(3), 8)}${pad(a.z.toFixed(3), 8)}  1.00  0.00          ${pad(a.el, 2)}  `,
      )
      .join("\n") + "\n";
  for (let i = 0; i < model.atoms.length; i++) {
    const ns = model.bonds.flatMap((b) =>
      b.a === i
        ? Array(b.order === 4 ? 1 : b.order).fill(b.b + 1)
        : b.b === i
          ? Array(b.order === 4 ? 1 : b.order).fill(b.a + 1)
          : [],
    );
    for (let k = 0; k < ns.length; k += 4)
      s +=
        "CONECT" +
        pad(i + 1, 5) +
        ns
          .slice(k, k + 4)
          .map((n) => pad(n, 5))
          .join("") +
        "\n";
  }
  return s + "END\n";
}
export function downloadText(text, name) {
  const blob = new Blob([text], {
      type: "chemical/x-mdl-molfile;charset=utf-8",
    }),
    a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export function shareHash(model, style) {
  return (
    "#m=" +
    LZString.compressToEncodedURIComponent(
      JSON.stringify({
        v: 1,
        name: model.name,
        smiles: model.smiles,
        style,
        atoms: model.atoms,
        bonds: model.bonds,
      }),
    )
  );
}
export function readHash(hash) {
  if (!hash.startsWith("#m=")) return null;
  if (hash.length > 300000)
    throw Error(
      "Share link exceeds the supported size. Import a structure file instead.",
    );
  const decoded = LZString.decompressFromEncodedURIComponent(hash.slice(3));
  if (!decoded || decoded.length > 5e6)
    throw Error("Invalid or oversized share link.");
  let data;
  try {
    data = JSON.parse(decoded);
  } catch {
    throw Error("Invalid share link.");
  }
  if (data.v !== 1) throw Error("Unsupported share-link version.");
  if (data.atoms) data = { ...data, ...validateModel(data) };
  const s = data.style || {};
  data.style = {
    representation: ["ball", "sticks", "space"].includes(s.representation)
      ? s.representation
      : "ball",
    palette: s.palette === "paton" ? "paton" : "cpk",
    hydrogens: s.hydrogens !== false,
    labels: s.labels === true,
    spin: s.spin === true,
    size:
      typeof s.size === "number" && Number.isFinite(s.size)
        ? Math.max(0.5, Math.min(1.8, s.size))
        : 1,
    background: ["light", "dark", "transparent"].includes(s.background)
      ? s.background
      : "light",
  };
  return data;
}
export function capturePNG(view, scale = 2) {
  const { renderer, scene, camera } = view,
    w = renderer.domElement.clientWidth,
    h = renderer.domElement.clientHeight,
    gl = renderer.getContext(),
    limit = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
  if (w * scale > limit || h * scale > limit || w * h * scale * scale > 67e6)
    throw Error(
      "This resolution exceeds your graphics limit. Choose a lower export scale.",
    );
  const old = scene.background;
  scene.background =
    view.style.background === "transparent"
      ? null
      : new Color(view.style.background === "dark" ? "#1d2534" : "#edf0f6");
  // Capture synchronously; alpha survives without preserveDrawingBuffer. Keep the specified exporter.
  function exportPNG(scale = 2) {
    const { clientWidth: w, clientHeight: h } = renderer.domElement;
    renderer.setSize(w * scale, h * scale, false);
    renderer.render(scene, camera);
    renderer.domElement.toBlob((b) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = "molecule.png";
      a.click();
      URL.revokeObjectURL(a.href);
    }, "image/png");
    renderer.setSize(w, h, false);
  }
  try {
    exportPNG(scale);
  } finally {
    scene.background = old;
    renderer.setSize(w, h, false);
  }
}
