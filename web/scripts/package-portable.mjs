import { build } from "vite";
import { readFile, writeFile, readdir, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
process.chdir(root);
const out = ".portable-build";
await build({
  configFile: false,
  build: {
    outDir: out,
    copyPublicDir: false,
    emptyOutDir: true,
    lib: {
      entry: "src/main.js",
      name: "MolStudio",
      formats: ["iife"],
      fileName: () => "app.js",
    },
  },
});
const read = (p) => readFile(p, "utf8");
const script = (await read(`${out}/app.js`)).replace(
  /<\/script/gi,
  "<\\/script",
);
const css = (
  await Promise.all(
    (await readdir(out))
      .filter((f) => f.endsWith(".css"))
      .map((f) => read(`${out}/${f}`)),
  )
).join("\n");
const js = await readFile("public/vendor/rdkit/RDKit_minimal.js");
const wasm = await readFile("public/vendor/rdkit/RDKit_minimal.wasm");
if (wasm.readUInt32LE(0) !== 0x6d736100)
  throw Error("Missing or invalid RDKit WASM.");
const packed = JSON.stringify({
  js: js.toString("base64"),
  wasm: wasm.toString("base64"),
});
const icon =
  "data:image/svg+xml;base64," +
  (await readFile("public/favicon.svg")).toString("base64");
let html = await read("index.html");
html = html.replace(
  /<script type="module" src="\/src\/main.js"><\/script>/,
  "",
);
html = html.replace('href="/favicon.svg"', `href="${icon}"`);
html = html.replace("</head>", () => `<style>${css}</style></head>`);
html = html.replace(
  "</body>",
  () =>
    `<script type="application/json" id="molstudio-rdkit">${packed}</script><script>${script}</script></body>`,
);
await mkdir("portable", { recursive: true });
let licenses = "MolStudio portable: third-party notices\n\n";
for (const [name, path] of [
  ["Three.js", "node_modules/three/LICENSE"],
  ["LZ-String", "node_modules/lz-string/LICENSE"],
  ["RDKit", "public/vendor/rdkit/LICENSE"],
])
  licenses += `\n===== ${name} =====\n${await read(path)}\n`;
await writeFile("portable/THIRD-PARTY-LICENSES.txt", licenses);
html = html.replace(
  "</body>",
  () =>
    `<script type="text/plain" id="third-party-notices">${licenses.replace(/<\/script/gi, "<\\/script")}</script></body>`,
);
await writeFile("portable/MolStudio.html", html);
await rm(out, { recursive: true });
console.log(
  `Portable app: portable/MolStudio.html (${(Buffer.byteLength(html) / 1024 / 1024).toFixed(1)} MiB). No server or installation required.`,
);
