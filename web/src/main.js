import "./style.css";
import { shell, toast, copyText } from "./ui.js";
import { MolecularView } from "./viewer.js";
import { parseMOL, parseFile, formula } from "./chemistry.js";
import { smilesToModel } from "./rdkit.js";
import aspirin from "./fixtures/aspirin.mol?raw";
import { Editor } from "./editor/editor.js";
import { elements } from "./chemistry.js";
shell();
const $ = (s) => document.querySelector(s),
  view = new MolecularView($("#viewport"));
let model = { ...parseMOL(aspirin), smiles: "CC(=O)Oc1ccccc1C(=O)O" },
  busy = false,
  loadVersion = 0,
  editor;
const samples = {
  Aspirin: "CC(=O)Oc1ccccc1C(=O)O",
  Caffeine: "CN1C=NC2=C1C(=O)N(C)C(=O)N2C",
  Benzene: "c1ccccc1",
  Ibuprofen: "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
};
function info() {
  $("#molecule-name").textContent = model.name;
  $("#formula").textContent = formula(model);
  $("#atom-count").textContent = `${model.atoms.length} atoms`;
  $("#bond-count").textContent = `${model.bonds.length} bonds`;
  $("#empty").hidden = !!model.atoms.length;
}
function load(next) {
  if (editor?.locked) {
    toast("Wait for geometry relaxation to finish.");
    return;
  }
  editor?.reset();
  model = next;
  view.syncModel(model);
  view.fit();
  editor?.update();
  info();
  $("#smiles").value = model.smiles || "";
}
async function renderSmiles(smiles, name = "Molecule") {
  if (busy) return;
  const version = ++loadVersion;
  busy = true;
  $("#busy").hidden = false;
  $("#render").disabled = true;
  try {
    const next = await smilesToModel(smiles, name);
    if (version === loadVersion) {
      load(next);
      if (next.embedding === "approximate")
        toast(
          "Approximate 3D geometry. Inspect before scientific use.",
          "info",
        );
    }
  } catch (e) {
    toast(e.message, "error");
  } finally {
    busy = false;
    $("#busy").hidden = true;
    $("#render").disabled = false;
  }
}
$("#smiles-form").onsubmit = (e) => {
  e.preventDefault();
  const smiles = $("#smiles").value.trim();
  renderSmiles(
    smiles,
    Object.keys(samples).find((n) => samples[n] === smiles) || "Molecule",
  );
};
for (const b of document.querySelectorAll("[data-sample]"))
  b.onclick = () => {
    $("#smiles").value = samples[b.dataset.sample];
    renderSmiles(samples[b.dataset.sample], b.dataset.sample);
  };
async function importFile(file) {
  if (!file) return;
  const version = ++loadVersion;
  if (file.size > 20 * 1024 * 1024) {
    toast("File exceeds the 20 MB limit.", "error");
    return;
  }
  try {
    const next = parseFile(await file.text(), file.name, toast);
    if (version === loadVersion) load(next);
  } catch (e) {
    toast(e.message, "error");
  }
}
$("#open-file").onclick = () => $("#file").click();
$("#file").onchange = (e) => {
  importFile(e.target.files[0]);
  e.target.value = "";
};
let dragDepth = 0;
window.addEventListener("dragenter", (e) => {
  if (e.dataTransfer.types.includes("Files")) {
    e.preventDefault();
    dragDepth++;
    document.body.classList.add("dropping");
  }
});
window.addEventListener("dragover", (e) => {
  e.preventDefault();
});
window.addEventListener("dragleave", () => {
  if (--dragDepth <= 0) document.body.classList.remove("dropping");
});
window.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  document.body.classList.remove("dropping");
  if (e.dataTransfer.files.length > 1)
    toast("Opening the first file. Drop additional files individually.");
  importFile(e.dataTransfer.files[0]);
});
for (const key of [
  "representation",
  "palette",
  "hydrogens",
  "labels",
  "spin",
  "size",
  "background",
])
  $("#" + key).addEventListener("input", (e) => {
    const v =
      e.target.type === "checkbox"
        ? e.target.checked
        : key === "size"
          ? Number(e.target.value)
          : e.target.value;
    view.style[key] = v;
    applyStyle();
  });
function applyStyle() {
  document.body.classList.toggle("dark", view.style.background === "dark");
  document.body.classList.toggle(
    "transparent",
    view.style.background === "transparent",
  );
  $("#size-value").textContent = Math.round(view.style.size * 100) + "%";
  if (editor?.tool !== "select" && editor) view.style.spin = false;
  view.controls.autoRotate = view.style.spin;
  view.syncModel(model);
  editor?.update();
}
$("#fit").onclick = () => view.fit();
$("#mobile-toggle").onclick = () => {
  const open = document.body.classList.toggle("sheet-open");
  $("#mobile-toggle").setAttribute("aria-expanded", open);
};
view.onMeasurement = (m, text) => {
  $("#measurement").hidden = !m;
  $("#measurement").textContent = m ? `${m.kind} · ${text}` : "";
};
const hints = {
  select: "Click up to 4 atoms to measure. Drag to orbit.",
  add: "Click space for an atom, or an atom to extend it.",
  move: "Drag an atom to move the selection in the view plane.",
  delete: "Click an atom to remove it and its bonds.",
  bond: "Click two atoms. Repeat to cycle bond order.",
};
editor = new Editor(view, {
  getModel: () => model,
  toast,
  onChange: (next, full) => {
    loadVersion++; // A later edit supersedes an in-flight SMILES request.
    model = next;
    if (full) view.syncModel(model);
    info();
    $("#smiles").value = model.smiles || "";
  },
  onState: (e) => {
    $("#undo").disabled = !e.undoStack.length || e.locked;
    $("#redo").disabled = !e.redoStack.length || e.locked;
    $("#tidy").disabled = !model.atoms.length || e.locked;
    $("#apply-element").disabled = !e.selection.length || e.locked;
    $("#apply-element").textContent = `Apply ${e.element} to selection`;
    for (const b of document.querySelectorAll("[data-tool]")) {
      b.setAttribute("aria-pressed", b.dataset.tool === e.tool);
      b.disabled = e.locked;
    }
    $("#spin").disabled = e.tool !== "select";
    $("#spin").checked = view.style.spin;
    $("#tool-hint").textContent = hints[e.tool];
    for (const id of ["new", "render", "open-file"])
      $("#" + id).disabled = e.locked || (id === "render" && busy);
  },
});
for (const b of document.querySelectorAll("[data-tool]"))
  b.onclick = () => editor.setTool(b.dataset.tool);
function setElement(el) {
  editor.element = el;
  for (const b of document.querySelectorAll("[data-element]"))
    b.setAttribute("aria-pressed", b.dataset.element === el);
  editor.update();
}
const common = ["H", "C", "N", "O", "F", "S", "P", "Cl", "Br", "I"];
for (const [target, list] of [
  ["#elements", common],
  ["#periodic", elements],
])
  for (const el of list) {
    const b = document.createElement("button");
    b.textContent = el;
    b.dataset.element = el;
    b.title = `${el} — atomic number ${elements.indexOf(el) + 1}`;
    b.setAttribute("aria-label", `Choose ${el}`);
    b.onclick = () => setElement(el);
    $(target).append(b);
  }
$("#more").onclick = () => {
  const open = $("#periodic").hidden;
  $("#periodic").hidden = !open;
  $("#more").setAttribute("aria-expanded", open);
};
$("#apply-element").onclick = () => editor.applyElement();
$("#undo").onclick = () => editor.undo();
$("#redo").onclick = () => editor.redo();
$("#tidy").onclick = () => editor.tidy();
editor.onProgress = (p) =>
  ($("#tool-hint").textContent = `Relaxing geometry… ${Math.round(p * 100)}%`);
$("#new").onclick = () => {
  loadVersion++;
  editor.new();
};
window.addEventListener("keydown", (e) => {
  if (e.target.closest("textarea,input,select,[contenteditable=true]")) return;
  const k = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && k === "z") {
    e.preventDefault();
    e.shiftKey ? editor.redo() : editor.undo();
    return;
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (k === "escape") {
    editor.selection = [];
    editor.setTool("select");
  } else if (k === "delete" || k === "backspace") {
    e.preventDefault();
    editor.delete(editor.selection);
  } else {
    const tool = {
      1: "select",
      v: "select",
      2: "add",
      a: "add",
      3: "move",
      m: "move",
      4: "delete",
      d: "delete",
      5: "bond",
      b: "bond",
    }[k];
    if (tool) {
      e.preventDefault();
      editor.setTool(tool);
    }
  }
});
setElement("C");
load(model);
window.alder = {
  view,
  editor,
  get model() {
    return model;
  },
  load,
  renderSmiles,
  importFile,
};
import {
  capturePNG,
  downloadText,
  writeXYZ,
  writeMOL,
  writePDB,
  safeName,
  shareHash,
  readHash,
} from "./io.js";
$("#png").onclick = () => {
  try {
    capturePNG(view, Number($("#png-scale").value));
    toast("PNG exported.");
  } catch (e) {
    toast(e.message, "error");
  }
};
for (const [id, writer] of [
  ["xyz", writeXYZ],
  ["mol", writeMOL],
  ["pdb", writePDB],
])
  $("#" + id).onclick = () => {
    try {
      downloadText(writer(model), safeName(model.name) + "." + id);
    } catch (e) {
      toast(e.message, "error");
    }
  };
$("#share").onclick = async () => {
  try {
    const url = location.href.split("#")[0] + shareHash(model, view.style);
    const copied = await copyText(url);
    if (!copied) return;
    toast(
      url.length > 8000
        ? "Link copied. Over 8,000 characters: some apps may truncate it."
        : "Share link copied.",
      url.length > 8000 ? "warning" : "info",
    );
  } catch {
    toast(
      "Could not prepare the link. Export MOL to save the structure.",
      "error",
    );
  }
};
async function restoreLink() {
  try {
    const data = readHash(location.hash);
    if (!data) return;
    if (data.atoms) load(data);
    else if (data.smiles) await renderSmiles(data.smiles, data.name);
    Object.assign(view.style, data.style);
    for (const [key, value] of Object.entries(view.style)) {
      const input = $("#" + key);
      if (input?.type === "checkbox") input.checked = value;
      else if (input) input.value = value;
    }
    applyStyle();
  } catch (e) {
    toast(e.message, "error");
  }
}
window.addEventListener("hashchange", restoreLink);
restoreLink();
