import brandLogo from "../public/favicon.svg?raw";
const logoURL =
  "data:image/svg+xml;charset=utf-8," + encodeURIComponent(brandLogo);
export const icon = (name) => {
  const paths = {
    select: "m5 3 14 9-7 1-3 7Z",
    add: "M12 5v14M5 12h14",
    move: "M12 3v18M3 12h18m-4-4 4 4-4 4M8 7l4-4 4 4M8 17l4 4 4-4M7 8l-4 4 4 4",
    delete: "M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6m4-6v6",
    bond: "m7 17 10-10M5 14l5 5M14 5l5 5",
    undo: "M9 5 4 10l5 5M4 10h10a6 6 0 0 1 6 6",
    redo: "m15 5 5 5-5 5M20 10H10a6 6 0 0 0-6 6",
    fit: "M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5M8 12h8m-4-4v8",
    spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z",
    download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
    link: "m10 14 4-4M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 10a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-1 1",
    folder: "M3 7h7l2 3h9l-3 10H3ZM3 7V4h7l2 3h7v3",
    settings: "M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6",
    chevron: "m6 9 6 6 6-6",
    close: "m6 6 12 12M6 18 18 6",
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.select}"/></svg>`;
};
export function shell() {
  document.querySelector("#app").innerHTML = `
 <div id="viewport" aria-label="Interactive molecule. Drag to orbit, scroll to zoom, right-drag to pan." tabindex="0"></div>
 <div id="drop-mask">${icon("folder")}<strong>Drop your structure here</strong><span>MOL · SDF · XYZ · PDB</span></div>
 <header><a class="brand" href="./" aria-label="MolStudio home"><img src="${logoURL}" alt=""><span>Mol<span class="brand-light">Studio</span></span><span class="beta">WORKSPACE</span></a><span class="privacy"><i></i> Local & private</span><button id="mobile-toggle" aria-expanded="false" aria-controls="panels">${icon("settings")} Workspace</button></header>
 <div id="panels"><div class="left-panels">
 <section class="glass source-panel" aria-label="Molecule input"><div class="eyebrow">START EXPLORING</div><div class="section-title">A little structure.<br>A lot of possibility.</div><form id="smiles-form"><label for="smiles">SMILES string</label><textarea id="smiles" spellcheck="false" rows="2" placeholder="e.g. CC(=O)Oc1ccccc1C(=O)O">CC(=O)Oc1ccccc1C(=O)O</textarea><button id="render" class="primary" type="submit">${icon("spark")} Render molecule <span>↵</span></button></form><div class="samples" aria-label="Sample molecules">${["Aspirin", "Caffeine", "Benzene", "Ibuprofen"].map((n) => `<button data-sample="${n}">${n}</button>`).join("")}</div><button id="open-file" class="file-button">${icon("folder")} Open a structure file</button><p class="hint center">or drop MOL, SDF, XYZ, PDB anywhere</p><input id="file" type="file" accept=".mol,.sdf,.xyz,.pdb" hidden></section>
 <section class="glass editor-panel" aria-label="Molecular editor"><div class="panel-heading"><span class="eyebrow">BUILD & EDIT</span><button id="new" class="text-button">New ${icon("add")}</button></div><div class="tools" role="toolbar" aria-label="Editor tools">${[
   ["select", "Select", "1 / V"],
   ["add", "Add", "2 / A"],
   ["move", "Move", "3 / M"],
   ["delete", "Delete", "4 / D"],
   ["bond", "Bond", "5 / B"],
 ]
   .map(
     ([t, n, k]) =>
       `<button data-tool="${t}" title="${n} (${k})" aria-pressed="${t === "select"}">${icon(t)}<span>${n}</span></button>`,
   )
   .join(
     "",
   )}</div><div class="palette-heading"><label>Element</label><button id="more" class="text-button" aria-expanded="false">Periodic table ${icon("chevron")}</button></div><div id="elements" class="elements"></div><div id="periodic" class="elements" hidden></div><button id="apply-element" class="secondary wide" disabled>Apply carbon to selection</button><div class="edit-actions"><button id="undo" title="Undo (Ctrl / ⌘ Z)" aria-label="Undo" disabled>${icon("undo")}</button><button id="redo" title="Redo (Ctrl / ⌘ Shift Z)" aria-label="Redo" disabled>${icon("redo")}</button><button id="tidy" class="secondary">${icon("spark")} Tidy geometry</button></div><p id="tool-hint" class="hint">Click atoms to measure. Drag to orbit.</p></section>
 </div><details class="glass style-panel" open><summary><span>${icon("settings")} Appearance</span>${icon("chevron")}</summary><div class="style-body"><label for="representation">Representation</label><select id="representation"><option value="ball">Ball & stick</option><option value="sticks">Sticks</option><option value="space">Space-filling</option></select><label for="palette">Color palette</label><select id="palette"><option value="cpk">Classic CPK</option><option value="paton">Paton-inspired</option></select><div class="divider"></div>${[
   ["hydrogens", "Hydrogens", true],
   ["labels", "Element labels", false],
   ["spin", "Auto-rotate", false],
 ]
   .map(
     ([id, n, on]) =>
       `<label class="switch-row" for="${id}">${n}<input id="${id}" type="checkbox" role="switch" ${on ? "checked" : ""}></label>`,
   )
   .join(
     "",
   )}<label class="size-label" for="size">Atom size <output id="size-value">100%</output></label><input id="size" type="range" min="0.5" max="1.8" step="0.05" value="1"><label for="background">Background</label><select id="background"><option value="light">Pearl light</option><option value="dark">Midnight</option><option value="transparent">Transparent</option></select><div class="lighting"><i></i> Studio lighting <span>PHYSICAL</span></div></div></details>
 <section class="glass export-panel" aria-label="Export and share"><div class="panel-heading"><span class="eyebrow">TAKE IT WITH YOU</span></div><div class="png-row"><button id="png" class="primary">${icon("download")} Export PNG</button><select id="png-scale" aria-label="PNG resolution"><option value="1">1×</option><option value="2" selected>2×</option><option value="4">4×</option></select></div><div class="export-formats"><button id="xyz">XYZ</button><button id="mol">MOL</button><button id="pdb">PDB</button><button id="share" title="Copy share link">${icon("link")} Link</button></div><p class="hint">XYZ carries no bond information; orders are lost (export MOL too)</p></section></div>
 <div class="canvas-top"><span>3D MOLECULAR WORKSPACE</span><span class="units">Å · ANGSTROMS</span></div>
 <div id="empty" hidden><h1>Build something from nothing.</h1><p>Choose an element, then use Add to place your first atom.</p></div>
 <div class="canvas-bottom"><div id="model-info"><h1 id="molecule-name">Aspirin</h1><p><span id="formula"></span><span class="dot">·</span><span id="atom-count"></span><span class="dot">·</span><span id="bond-count"></span></p></div><button id="fit" class="glass icon-button" title="Fit molecule to view" aria-label="Fit molecule to view">${icon("fit")}</button></div>
 <div id="measurement" class="glass" hidden aria-live="polite"></div><div id="busy" hidden role="status"><span class="spinner"></span><span id="busy-label">Loading chemistry engine…</span></div><div id="toasts" aria-live="polite" aria-atomic="false"></div>
 <div class="bottom-hint"><span>DRAG <b>orbit</b></span><span>SCROLL <b>zoom</b></span><span>RIGHT DRAG <b>pan</b></span></div>`;
  document.querySelector(".brand").href = location.href.split("#")[0];
}
export function toast(message, kind = "info", duration = 5000) {
  const host = document.querySelector("#toasts");
  for (const old of host.children)
    if (old.textContent === message) old.remove();
  while (host.children.length >= 3) host.firstElementChild.remove();
  const item = document.createElement("div");
  item.className = `toast ${kind}`;
  item.textContent = message;
  document.querySelector("#toasts").append(item);
  const timer = setTimeout(() => item.remove(), duration);
  const dismiss = () => {
    clearTimeout(timer);
    item.remove();
  };
  dismiss.update = (text) => {
    item.textContent = text;
  };
  return dismiss;
}

// Local-file clipboard permissions vary by browser. Keep a native manual-copy fallback.
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    let dialog = document.querySelector("#copy-dialog");
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.id = "copy-dialog";
      dialog.setAttribute("aria-labelledby", "copy-title");
      dialog.innerHTML =
        '<form method="dialog"><h2 id="copy-title">Copy molecule link</h2><p>Your browser needs you to copy this link manually.</p><label for="copy-value">Press Ctrl+C (or ⌘C) to copy the selected link</label><textarea id="copy-value" readonly rows="4"></textarea><p class="hint">Local file links work on this computer. Use MOL files to exchange structures with other people.</p><button class="primary" value="done">Done</button></form>';
      document.body.append(dialog);
    }
    const field = dialog.querySelector("textarea");
    field.value = text;
    dialog.showModal();
    field.focus();
    field.select();
    return false;
  }
}
