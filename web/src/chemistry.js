export const CPK = {
  H: "#FFFFFF",
  C: "#909090",
  N: "#3050F8",
  O: "#FF0D0D",
  F: "#90E050",
  Cl: "#1FF01F",
  Br: "#A62929",
  I: "#940094",
  S: "#FFFF30",
  P: "#FF8000",
};
export const dispR = {
  H: 0.31,
  C: 0.42,
  N: 0.4,
  O: 0.4,
  F: 0.37,
  Cl: 0.55,
  Br: 0.6,
  I: 0.68,
  S: 0.55,
  P: 0.55,
};
export const vdWR = {
  H: 1.2,
  C: 1.7,
  N: 1.55,
  O: 1.52,
  F: 1.47,
  Cl: 1.75,
  Br: 1.85,
  I: 1.98,
  S: 1.8,
  P: 1.8,
};
export const covR = {
  H: 0.31,
  C: 0.76,
  N: 0.71,
  O: 0.66,
  F: 0.57,
  Cl: 1.02,
  Br: 1.2,
  I: 1.39,
  S: 1.05,
  P: 1.07,
};
export const bond0 = {
  "C-C": 1.54,
  "C-H": 1.09,
  "C-O": 1.43,
  "C=O": 1.22,
  "C-N": 1.47,
  "O-H": 0.97,
  "N-H": 1.01,
  "C-Cl": 1.77,
  "C-S": 1.82,
};
export const maxValence = {
  H: 1,
  C: 4,
  N: 3,
  O: 2,
  F: 1,
  Cl: 1,
  Br: 1,
  I: 1,
  S: 2,
  P: 3,
};
export const elements =
  "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split(
    " ",
  );
export const atomPosition = (a) => [a.x, a.y, a.z];
export function idealLength(a, b, order = 1) {
  const sep = order === 2 ? "=" : order === 3 ? "#" : "-";
  return (
    bond0[a + sep + b] ??
    bond0[b + sep + a] ??
    ((covR[a] ?? 0.7) + (covR[b] ?? 0.7)) *
      (order === 2 ? 0.87 : order === 3 ? 0.78 : 1)
  );
}
export function validateModel(model) {
  if (
    !model ||
    !Array.isArray(model.atoms) ||
    !Array.isArray(model.bonds) ||
    model.atoms.length > 10000 ||
    model.bonds.length > 40000
  )
    throw Error("Invalid structure or size limit exceeded (10,000 atoms).");
  const atoms = model.atoms.map((a) => {
    if (
      !a ||
      !elements.includes(a.el) ||
      ![a.x, a.y, a.z].every((n) => Number.isFinite(n) && Math.abs(n) < 1e5)
    )
      throw Error("Invalid atom symbol or coordinates.");
    return {
      el: a.el,
      x: a.x,
      y: a.y,
      z: a.z,
      ...(Number.isInteger(a.charge) && Math.abs(a.charge) <= 15
        ? { charge: a.charge }
        : {}),
      ...(Number.isInteger(a.isotope) && a.isotope > 0 && a.isotope <= 300 ? {isotope:a.isotope} : {}),
      ...(Number.isInteger(a.radical) && a.radical > 0 && a.radical <= 8 ? {radical:a.radical} : {}),
    };
  });
  const pairs = new Set();
  const bonds = model.bonds.map((b) => {
    if (
      !b ||
      ![b.a, b.b].every(
        (n) => Number.isInteger(n) && n >= 0 && n < atoms.length,
      ) ||
      b.a === b.b ||
      ![1, 2, 3, 4].includes(b.order)
    )
      throw Error("Invalid bond indices or order.");
    const key = [b.a, b.b].sort((a, b) => a - b).join(":");
    if (pairs.has(key)) throw Error("Duplicate bond.");
    pairs.add(key);
    return { a: b.a, b: b.b, order: b.order };
  });
  return {
    name: String(model.name || "Untitled molecule").slice(0, 150),
    smiles:
      typeof model.smiles === "string" ? model.smiles.slice(0, 10000) : "",
    atoms,
    bonds,
    ...(["ETKDG", "ETKDG + MMFF94", "ETKDG + UFF"].includes(model.embedding) ? {embedding:model.embedding} : {}),
  };
}
export function parseMOL(text, name) {
  const lines = text.replace(/\r/g, "").split("\n");
  if (!lines[3]?.includes("V2000"))
    throw Error("Expected a MOL V2000 structure. V3000 is not supported.");
  const n = Number(lines[3].slice(0, 3)),
    m = Number(lines[3].slice(3, 6));
  if (
    !Number.isInteger(n) ||
    !Number.isInteger(m) ||
    n < 0 ||
    m < 0 ||
    lines.length < 4 + n + m
  )
    throw Error("Incomplete MOL atom or bond block.");
  const atoms = lines.slice(4, 4 + n).map((l) => ({
    el: l.slice(31, 34).trim(),
    x: parseFloat(l.slice(0, 10)),
    y: parseFloat(l.slice(10, 20)),
    z: parseFloat(l.slice(20, 30)),
    charge:
      { 1: 3, 2: 2, 3: 1, 5: -1, 6: -2, 7: -3 }[Number(l.slice(36, 39))] || 0,
  }));
  const bonds = lines.slice(4 + n, 4 + n + m).map((l) => ({
    a: Number(l.slice(0, 3)) - 1,
    b: Number(l.slice(3, 6)) - 1,
    order: Number(l.slice(6, 9)),
  }));
  for (const l of lines.slice(4 + n + m)) {
    if (/^M  (CHG|ISO|RAD)/.test(l)) {
      const field=l.slice(3,6);
      const parts = l.trim().split(/\s+/).slice(3).map(Number);
      for (let i = 0; i < parts.length; i += 2) {
        if (atoms[parts[i] - 1]) atoms[parts[i] - 1][{CHG:'charge',ISO:'isotope',RAD:'radical'}[field]] = field==='RAD' ? (parts[i+1]===2?1:2) : parts[i + 1];
      }
    }
  }
  return validateModel({ name: name || lines[0]?.trim(), atoms, bonds });
}
export function formula(model) {
  const c = {};
  for (const a of model.atoms) c[a.el] = (c[a.el] || 0) + 1;
  const order = Object.keys(c).sort(
    (a, b) =>
      (a === "C" ? -2 : a === "H" ? -1 : 0) -
        (b === "C" ? -2 : b === "H" ? -1 : 0) || a.localeCompare(b),
  );
  return order
    .map(
      (el) =>
        el +
        (c[el] === 1
          ? ""
          : String(c[el]).replace(/\d/g, (n) => "₀₁₂₃₄₅₆₇₈₉"[n])),
    )
    .join("");
}
// Spatial bins keep bond inference linear for ordinary molecular densities.
export function inferBonds(atoms) {
  const bonds = [],
    grid = new Map(),
    cell = 3.2,
    key = (x, y, z) => `${x},${y},${z}`;
  atoms.forEach((a, i) => {
    const x = Math.floor(a.x / cell),
      y = Math.floor(a.y / cell),
      z = Math.floor(a.z / cell);
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (let dz = -1; dz <= 1; dz++)
          for (const j of grid.get(key(x + dx, y + dy, z + dz)) || []) {
            const b = atoms[j],
              d = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
            if (d > 0.1 && d < (covR[a.el] ?? 0.7) + (covR[b.el] ?? 0.7) + 0.4)
              bonds.push({ a: j, b: i, order: 1 });
          }
    const k = key(x, y, z);
    if (!grid.has(k)) grid.set(k, []);
    grid.get(k).push(i);
  });
  return bonds;
}
export function parseXYZ(text, name) {
  const lines = text.trimEnd().replace(/\r/g, "").split("\n"),
    n = Number(lines[0]?.trim());
  if (!Number.isInteger(n) || n < 1 || n > 10000 || lines.length < 2 + n)
    throw Error("Invalid XYZ atom count or incomplete coordinates.");
  const atoms = lines.slice(2, 2 + n).map((l) => {
    const [el, x, y, z] = l.trim().split(/\s+/);
    return { el, x: Number(x), y: Number(y), z: Number(z) };
  });
  const m = validateModel({ name: name || lines[1], atoms, bonds: [] });
  m.bonds = inferBonds(m.atoms);
  return m;
}
export function parsePDB(text, name) {
  const lines = text.replace(/\r/g, "").split("\n"),
    atoms = [],
    serials = new Map(),
    counts = new Map();
  let explicit = false,
    ended = false;
  for (const l of lines) {
    if (l.startsWith("ENDMDL")) ended = true;
    if (/^(ATOM  |HETATM)/.test(l) && !ended) {
      if (l[16] && l[16] !== " " && l[16] !== "A") continue;
      let el = l.slice(76, 78).trim();
      if (!el) {
        const raw = l.slice(12, 16);
        el =
          raw[0] === " "
            ? raw.trim().replace(/^\d/, "")[0]
            : raw.trim().replace(/^\d/, "").slice(0, 2);
        if (!el) throw Error("PDB atom is missing its element and atom name.");
        if (!elements.includes(el[0] + el.slice(1).toLowerCase())) el = el[0];
      }
      el = el[0]?.toUpperCase() + el.slice(1).toLowerCase();
      const serial = Number(l.slice(6, 11));
      if (serials.has(serial)) continue;
      serials.set(serial, atoms.length);
      atoms.push({
        el,
        x: parseFloat(l.slice(30, 38)),
        y: parseFloat(l.slice(38, 46)),
        z: parseFloat(l.slice(46, 54)),
      });
    }
  }
  for (const l of lines) {
    if (!l.startsWith("CONECT")) continue;
    explicit = true;
    const from = serials.get(Number(l.slice(6, 11)));
    if (from === undefined) continue;
    const repeated = new Map();
    for (let k = 11; k + 5 <= l.length; k += 5) {
      const to = serials.get(Number(l.slice(k, k + 5)));
      if (to !== undefined && to !== from)
        repeated.set(to, (repeated.get(to) || 0) + 1);
    }
    for (const [to, order] of repeated) {
      const directed = from + ":" + to;
      counts.set(directed, (counts.get(directed) || 0) + order);
    }
  }
  if (!atoms.length) throw Error("No atoms found in PDB.");
  const pairs = new Map();
  for (const [k, order] of counts) {
    const [a, b] = k.split(":").map(Number),
      key = [Math.min(a, b), Math.max(a, b)].join(":");
    pairs.set(key, Math.min(3, Math.max(pairs.get(key) || 0, order)));
  }
  const bonds = explicit
    ? [...pairs].map(([k, order]) => {
        const [a, b] = k.split(":").map(Number);
        return { a, b, order };
      })
    : inferBonds(atoms);
  return validateModel({ name: name || "PDB structure", atoms, bonds });
}
export function parseFile(text, filename, onNotice = () => {}) {
  const ext = filename.split(".").pop().toLowerCase(),
    name = filename.replace(/\.[^.]+$/, "");
  if (ext === "mol") return parseMOL(text, name);
  if (ext === "sdf") {
    const records = text.split("$$$$").filter((r) => r.trim());
    if (records.length > 1)
      onNotice(`SDF contains ${records.length} records; showing the first.`);
    return parseMOL(records[0] || "", name);
  }
  if (ext === "xyz") return parseXYZ(text, name);
  if (ext === "pdb") return parsePDB(text, name);
  throw Error("Choose a MOL, SDF, XYZ, or PDB file.");
}
