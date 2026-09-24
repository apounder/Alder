import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
await fs.mkdir("test-results", { recursive: true });
const browser = await chromium.launch({
  headless: true,
  args: [
    "--no-sandbox",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  ignoreHTTPSErrors: true,
  permissions: ["clipboard-read", "clipboard-write"],
});
const page = await context.newPage(),
  errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text());
});
const base = process.env.APP_URL || "http://127.0.0.1:5173";
const state = () => page.evaluate(() => structuredClone(alder.model));
const clickAtom = async (i) => {
  const pos = await page.evaluate(async (i) => {
    const { Vector3 } = await import(
      "/node_modules/three/build/three.module.js"
    );
    const v = alder.view,
      a = alder.model.atoms[i],
      r = v.renderer.domElement.getBoundingClientRect();
    for (const dir of [
      [0.1, 0.16, 1],
      [1, 0.2, 0.1],
      [-0.4, 0.9, 0.8],
      [0, 0, -1],
      [1, -1, -1],
    ]) {
      v.controls.enableDamping = false;
      const dist = v.camera.position.distanceTo(v.controls.target);
      v.camera.position
        .copy(v.controls.target)
        .add(new Vector3(...dir).normalize().multiplyScalar(dist));
      v.camera.lookAt(v.controls.target);
      v.controls.update();
      const p = new Vector3(a.x, a.y, a.z).project(v.camera),
        x = ((p.x + 1) * r.width) / 2,
        y = ((1 - p.y) * r.height) / 2;
      if (
        x > 315 &&
        x < 1170 &&
        y > 145 &&
        y < 875 &&
        v.pick({ clientX: x, clientY: y }) === i
      )
        return { x, y };
    }
    throw Error("Atom not pickable " + i);
  }, i);
  await page.mouse.click(pos.x, pos.y);
  return pos;
};
try {
  await page.goto(base);
  await page.waitForFunction(() => window.alder?.model.atoms.length === 21);
  assert.equal(await page.evaluate(() => !!window.initRDKitModule), false);
  assert.equal(
    await page.evaluate(
      () =>
        alder.view.atomMesh.isInstancedMesh &&
        alder.view.bondMesh.isInstancedMesh,
    ),
    true,
  );
  console.log("PASS initial MOL, instancing, no WASM");
  for (const [smiles, name] of [
    ["c1ccccc1", "Benzene"],
    ["O", "Water"],
    ["CC", "Ethane"],
    ["CN1C=NC2=C1C(=O)N(C)C(=O)N2C", "Caffeine"],
  ]) {
    await page.fill("#smiles", smiles);
    await page.click("#render");
    await page.waitForFunction((s) => alder.model.smiles === s, smiles, {
      timeout: 60000,
    });
    const result = await page.evaluate(async (name) => {
      const { measure } = await import("/src/measure.js");
      const m = alder.model;
      if (name === "Benzene")
        return {
          z: Math.max(...m.atoms.map((a) => Math.abs(a.z))),
          length: measure(m.atoms, [0, 1]).value,
          atoms: m.atoms.length,
        };
      if (name === "Water")
        return {
          length: measure(m.atoms, [0, 1]).value,
          angle: measure(m.atoms, [1, 0, 2]).value,
        };
      if (name === "Ethane")
        return { angle: measure(m.atoms, [2, 0, 1, 5]).value };
      return {
        z: Math.max(
          ...m.atoms
            .slice(0, 14)
            .filter((a) => a.el !== "H")
            .map((a) => Math.abs(a.z)),
        ),
        atoms: m.atoms.length,
      };
    }, name);
    if (name === "Benzene") {
      assert.ok(result.z < 0.001);
      assert.ok(Math.abs(result.length - 1.39) < 0.01);
      assert.equal(result.atoms, 12);
    }
    if (name === "Water") {
      assert.ok(Math.abs(result.angle - 104.5) < 0.01);
      assert.ok(Math.abs(result.length - 0.97) < 0.001);
    }
    if (name === "Ethane")
      assert.ok(Math.abs(Math.abs(result.angle) - 60) < 0.01);
    if (name === "Caffeine") {
      assert.ok(result.z < 0.001);
      assert.equal(result.atoms, 24);
    }
    console.log("PASS " + name, JSON.stringify(result));
  }
  // Bad SMILES and bad files preserve the model.
  const previous = await state();
  await page.fill("#smiles", "not a molecule");
  await page.click("#render");
  await page.waitForFunction(
    () => !document.querySelector("#busy").hidden === false,
  );
  assert.deepEqual(await state(), previous);
  await page.setInputFiles("#file", {
    name: "broken.xyz",
    mimeType: "text/plain",
    buffer: Buffer.from("2\nmissing\nC 0 0 0"),
  });
  await page.waitForTimeout(100);
  assert.deepEqual(await state(), previous);
  await page.click("#new");
  assert.equal((await state()).atoms.length, 0);
  await page.mouse.click(740, 440);
  await page.click("#fit");
  assert.equal((await state()).atoms.length, 1);
  await page.click("#elements [data-element=H]");
  for (let k = 0; k < 4; k++) {
    await clickAtom(0);
    await page.click("#fit");
  }
  assert.equal((await state()).atoms.length, 5);
  console.log("PASS hand-built methane");
  await page.keyboard.press("Escape");
  await clickAtom(1);
  await page.click("#elements [data-element=C]");
  await page.click("#apply-element");
  await page.click("[data-tool=add]");
  await page.click("#elements [data-element=H]");
  for (let k = 0; k < 2; k++) {
    await clickAtom(1);
    await page.click("#fit");
  }
  await page.click("#elements [data-element=O]");
  await clickAtom(1);
  await page.click("#fit");
  await page.click("#elements [data-element=H]");
  const preH = await state();
  await clickAtom(7);
  await page.click("#fit");
  const ethanol = await state();
  assert.equal(ethanol.atoms.length, 9);
  assert.equal(ethanol.atoms.filter((a) => a.el === "C").length, 2);
  assert.equal(ethanol.atoms.filter((a) => a.el === "H").length, 6);
  const vals = ethanol.atoms.map(() => 0);
  for (const b of ethanol.bonds) {
    vals[b.a] += b.order;
    vals[b.b] += b.order;
  }
  assert.deepEqual(vals, [4, 4, 1, 1, 1, 1, 1, 2, 1]);
  await page.keyboard.press("Control+z");
  assert.deepEqual(await state(), preH);
  await page.keyboard.press("Control+Shift+z");
  assert.deepEqual(await state(), ethanol);
  console.log("PASS ethanol extension, valences, exact undo/redo");
  // Actual XYZ download and picker reimport.
  let downloadPromise = page.waitForEvent("download");
  await page.click("#xyz");
  const xyzDownload = await downloadPromise,
    xyzPath = "test-results/ethanol.xyz";
  await xyzDownload.saveAs(xyzPath);
  const xyz = await fs.readFile(xyzPath, "utf8");
  assert.equal(xyz.trim().split("\n").length, 11);
  assert.equal(xyz.trim().split("\n").slice(2).length, 9);
  assert.ok(
    xyz
      .trim()
      .split("\n")
      .slice(2)
      .every((l) => /\s-?\d+\.\d{4}\s+-?\d+\.\d{4}\s+-?\d+\.\d{4}$/.test(l)),
  );
  await page.setInputFiles("#file", xyzPath);
  await page.waitForFunction(() => alder.model.name === "ethanol");
  const imported = await state();
  assert.deepEqual(
    imported.atoms.map((a) => a.el),
    ethanol.atoms.map((a) => a.el),
  );
  for (let i = 0; i < 9; i++)
    for (const k of ["x", "y", "z"])
      assert.ok(
        Math.abs(imported.atoms[i][k] - ethanol.atoms[i][k]) <= 0.00005,
      );
  console.log("PASS XYZ download + reimport (9 atom rows + 2 headers)");
  // Measure and group move with actual pointer capture, one undo for the gesture.
  await page.click("[data-tool=select]");
  await clickAtom(0);
  await clickAtom(1);
  await page.click("[data-tool=move]");
  const dragState = await state(),
    undoCount = await page.evaluate(() => alder.editor.undoStack.length);
  const pos = await clickAtom(0);
  await page.mouse.move(pos.x, pos.y);
  await page.mouse.down();
  await page.mouse.move(pos.x + 45, pos.y - 20, { steps: 6 });
  assert.equal(
    await page.evaluate(() => alder.view.controls.enabled),
    false,
  );
  const movedLabel = await page.locator("#measurement").innerText();
  assert.match(movedLabel, /Distance/);
  await page.mouse.up();
  assert.equal(
    await page.evaluate(() => alder.view.controls.enabled),
    true,
  );
  assert.equal(
    await page.evaluate(() => alder.editor.undoStack.length),
    undoCount + 1,
  );
  const moved = await state();
  assert.notEqual(moved.atoms[0].x, dragState.atoms[0].x);
  assert.ok(
    Math.abs(
      moved.atoms[0].x -
        dragState.atoms[0].x -
        (moved.atoms[1].x - dragState.atoms[1].x),
    ) < 1e-8,
  );
  await page.click("#undo");
  assert.deepEqual(await state(), dragState);
  console.log("PASS multi-select drag, measurements, undo transaction");
  // Bond order cycle and undo.
  await page.click("[data-tool=bond]");
  for (const order of [2, 3, 0, 1]) {
    await clickAtom(0);
    await clickAtom(1);
    const m = await state(),
      b = m.bonds.find(
        (b) => (b.a === 0 && b.b === 1) || (b.a === 1 && b.b === 0),
      );
    assert.equal(b?.order || 0, order);
  }
  await page.click("[data-tool=delete]");
  const beforeDelete = await state();
  await clickAtom(8);
  assert.equal((await state()).atoms.length, 8);
  await page.click("#undo");
  assert.deepEqual(await state(), beforeDelete);
  console.log("PASS bond cycling and deletion");
  await page.click("#tidy");
  await page.waitForFunction(() => !alder.editor.locked);
  assert.ok(
    (await state()).atoms.every((a) => [a.x, a.y, a.z].every(Number.isFinite)),
  );
  await page.click("#undo");
  assert.deepEqual(await state(), beforeDelete);
  console.log("PASS Tidy undo");
  await page.click("[data-tool=select]");
  await page.selectOption("#representation", "space");
  await page.selectOption("#palette", "paton");
  await page.uncheck("#hydrogens");
  await page.check("#labels");
  await page.selectOption("#background", "dark");
  assert.equal(
    await page.evaluate(
      () =>
        alder.view.bondMesh.count > 0 &&
        alder.view.labels.children.length === 3,
    ),
    true,
  );
  assert.equal(
    await page.evaluate(() => {
      const v = alder.view,
        a = v.model.atoms.findIndex((a) => a.el === "H");
      const p = v.model.atoms[a];
      return v.visible(a);
    }),
    false,
  );
  await page.check("#spin");
  await page.click("[data-tool=add]");
  assert.equal(await page.isChecked("#spin"), false);
  assert.equal(await page.isDisabled("#spin"), true);
  await page.click("[data-tool=select]");
  console.log("PASS styles, hydrogen hiding, labels, spin restrictions");
  await page.click("#share");
  const url = await page.evaluate(() => navigator.clipboard.readText());
  const fresh = await context.newPage();
  fresh.on("pageerror", (e) => errors.push(e.message));
  await fresh.goto(url);
  await fresh.waitForFunction(() => window.alder?.model.atoms.length === 9);
  assert.deepEqual(
    await fresh.evaluate(() => alder.model.atoms),
    (await state()).atoms,
  );
  assert.deepEqual(
    await fresh.evaluate(() => alder.model.bonds),
    (await state()).bonds,
  );
  assert.deepEqual(
    await fresh.evaluate(() => alder.view.style),
    await page.evaluate(() => alder.view.style),
  );
  assert.equal(
    await fresh.evaluate(() => alder.editor.undoStack.length),
    0,
  );
  await fresh.close();
  console.log("PASS clipboard link + fresh-tab restoration");
  // Actual 4x PNG downloaded, decoded, checked for alpha and nonempty pixels.
  await page.setViewportSize({ width: 1000, height: 760 });
  await page.selectOption("#representation", "ball");
  await page.check("#hydrogens");
  await page.uncheck("#labels");
  await page.selectOption("#background", "transparent");
  await page.selectOption("#png-scale", "4");
  downloadPromise = page.waitForEvent("download");
  await page.click("#png");
  const pngDownload = await downloadPromise;
  await pngDownload.saveAs("test-results/molecule-4x.png");
  const bytes = await fs.readFile("test-results/molecule-4x.png");
  assert.equal(bytes.readUInt32BE(16), 4000);
  assert.equal(bytes.readUInt32BE(20), 3040);
  const png = bytes.toString("base64");
  const pixels = await page.evaluate(async (png) => {
    const img = new Image();
    img.src = "data:image/png;base64," + png;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = img.width;
    c.height = img.height;
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0);
    const d = ctx.getImageData(0, 0, c.width, c.height).data;
    let opaque = 0;
    for (let i = 3; i < d.length; i += 4) if (d[i] > 0) opaque++;
    return { alpha: d[3], opaque };
  }, png);
  assert.equal(pixels.alpha, 0);
  assert.ok(pixels.opaque > 10000);
  console.log("PASS 4× PNG exact dimensions and true alpha", pixels);
  // Real ~50-residue PDB dropped onto the canvas. Time includes parsing, rebuilding and render submission.
  await page.setViewportSize({ width: 1440, height: 1000 });
  const pdb = await fs.readFile("src/fixtures/1crn.pdb", "utf8");
  const timing = await page.evaluate(async (pdb) => {
    const dt = new DataTransfer();
    dt.items.add(new File([pdb], "1crn.pdb", { type: "chemical/x-pdb" }));
    const start = performance.now();
    document
      .querySelector("canvas")
      .dispatchEvent(
        new DragEvent("drop", { bubbles: true, dataTransfer: dt }),
      );
    while (alder.model.name !== "1crn")
      await new Promise(requestAnimationFrame);
    alder.view.renderer.render(alder.view.scene, alder.view.camera);
    return {
      ms: performance.now() - start,
      atoms: alder.model.atoms.length,
    };
  }, pdb);
  assert.equal(timing.atoms, 327);
  assert.ok(timing.ms < 1000, `PDB import ${timing.ms}ms`);
  console.log("PASS 46-residue PDB drag-drop", timing);
  await page.click("[data-sample=Aspirin]");
  await page.waitForFunction(() => alder.model.name === "Aspirin");
  await page.selectOption("#background", "light");
  await page.selectOption("#palette", "cpk");
  await page.mouse.move(1400, 980);
  await page.waitForTimeout(5200);
  await page.screenshot({ path: "test-results/desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.click("#fit");
  await page.screenshot({ path: "test-results/mobile-canvas.png" });
  await page.click("#mobile-toggle");
  assert.equal(
    await page.getAttribute("#mobile-toggle", "aria-expanded"),
    "true",
  );
  assert.equal(
    await page.evaluate(() => document.documentElement.scrollWidth),
    390,
  );
  await page.screenshot({ path: "test-results/mobile-sheet.png" });
  await page.click("#more");
  assert.equal(await page.locator("#periodic button").count(), 118);
  console.log("PASS mobile sheet and full periodic table");
  assert.deepEqual(errors, []);
  console.log("PASS zero browser console errors");
} catch (e) {
  await page.screenshot({ path: "test-results/failure.png" }).catch(() => {});
  console.error(e);
  console.error("Console errors:", errors);
  process.exitCode = 1;
} finally {
  await browser.close();
}
