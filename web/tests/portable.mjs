import { chromium } from "playwright";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { mkdtemp, copyFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import assert from "node:assert/strict";
const folder = await mkdtemp(resolve(tmpdir(), "MolStudio offline space "));
const target = resolve(folder, "MolStudio.html");
await copyFile("portable/MolStudio.html", target);
const browser = await chromium.launch({
  headless: true,
  args: [
    "--no-sandbox",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const context = await browser.newContext({
  offline: true,
  viewport: { width: 1280, height: 900 },
});
const page = await context.newPage(),
  errors = [],
  network = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text());
});
page.on("request", (r) => {
  if (/^https?:/.test(r.url())) network.push(r.url());
});
try {
  await page.goto(pathToFileURL(target).href);
  await page.waitForFunction(() => window.molstudio?.model.atoms.length === 21);
  assert.equal(await page.evaluate(() => !!window.initRDKitModule), false);
  assert.equal(
    await page.evaluate(
      () => document.querySelector(".brand img").naturalWidth > 0,
    ),
    true,
  );
  console.log(
    "PASS standalone file:// cold launch with network disabled, embedded branding, no WASM until needed",
  );
  await page.click("[data-sample=Benzene]");
  await page.waitForFunction(
    () => molstudio.model.name === "Benzene",
    {},
    { timeout: 60000 },
  );
  assert.equal(await page.evaluate(() => molstudio.model.atoms.length), 12);
  assert.ok(
    await page.evaluate(
      () =>
        Math.abs(
          Math.hypot(
            molstudio.model.atoms[0].x - molstudio.model.atoms[1].x,
            molstudio.model.atoms[0].y - molstudio.model.atoms[1].y,
          ) - 1.39,
        ) < 0.01,
    ),
  );
  await page.fill("#smiles", "O");
  await page.click("#render");
  await page.waitForFunction(() => molstudio.model.atoms.length === 3);
  console.log("PASS offline SMILES -> 3D from embedded RDKit JS/WASM");
  const downloadEvent = page.waitForEvent("download");
  await page.click("#mol");
  const download = await downloadEvent;
  const molPath = resolve(folder, "water.mol");
  await download.saveAs(molPath);
  assert.match(await readFile(molPath, "utf8"), /V2000/);
  await page.click("#new");
  assert.equal(await page.evaluate(() => molstudio.model.atoms.length), 0);
  await page.mouse.click(670, 430);
  assert.equal(await page.evaluate(() => molstudio.model.atoms.length), 1);
  await page.click("#undo");
  assert.equal(await page.evaluate(() => molstudio.model.atoms.length), 0);
  await page.setInputFiles("#file", molPath);
  await page.waitForFunction(() => molstudio.model.atoms.length === 3);
  console.log(
    "PASS local download/import, atom addition and undo without a server",
  );
  await page.selectOption("#background", "transparent");
  const pngEvent = page.waitForEvent("download");
  await page.click("#png");
  const png = await pngEvent;
  const pngPath = resolve(folder, "water.png");
  await png.saveAs(pngPath);
  const bytes = await readFile(pngPath);
  assert.equal(bytes.readUInt32BE(16), 2560);
  assert.equal(bytes.readUInt32BE(20), 1800);
  // Exercise a browser denying clipboard access, without requiring security flags or permissions.
  await page.evaluate(() =>
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: () => Promise.reject(new Error("denied")) },
    }),
  );
  await page.click("#share");
  await page.waitForSelector("#copy-dialog[open]");
  const link = await page.inputValue("#copy-value");
  assert.ok(link.startsWith("file:"));
  assert.ok(link.includes("#m="));
  await page.click("#copy-dialog button");
  const fresh = await context.newPage();
  fresh.on("pageerror", (e) => errors.push(e.message));
  await fresh.goto(link);
  await fresh.waitForFunction(() => molstudio.model.atoms.length === 3);
  assert.equal(
    await fresh.evaluate(() => molstudio.view.style.background),
    "transparent",
  );
  await fresh.close();
  assert.equal(
    await page.getAttribute(".brand", "href"),
    pathToFileURL(target).href,
  );
  assert.deepEqual(network, []);
  assert.deepEqual(errors, []);
  console.log(
    "PASS offline PNG, clipboard fallback, file permalink restoration; zero HTTP requests or console errors",
  );
} catch (error) {
  console.error("Browser errors:", errors);
  console.error("Network requests:", network);
  throw error;
} finally {
  await browser.close();
  await rm(folder, { recursive: true, force: true });
}
