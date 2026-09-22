import { Plane, Vector3 } from "three";
import { placement, point } from "./placement.js";
import { maxValence } from "../chemistry.js";
import { relax } from "./relax.js";
export class Editor {
  constructor(view, { getModel, onChange, onState, toast }) {
    Object.assign(this, { view, getModel, onChange, onState, toast });
    this.tool = "select";
    this.element = "C";
    this.selection = [];
    this.undoStack = [];
    this.redoStack = [];
    this.armed = null;
    this.hover = null;
    this.drag = null;
    this.locked = false;
    const canvas = view.renderer.domElement;
    canvas.addEventListener("pointerdown", (e) => this.down(e), true);
    canvas.addEventListener("pointermove", (e) => this.move(e), true);
    canvas.addEventListener("pointerup", (e) => this.up(e), true);
    canvas.addEventListener("pointercancel", (e) => this.cancel(e), true);
    canvas.addEventListener("lostpointercapture", (e) => {
      if (this.drag) this.cancel(e);
    });
    canvas.addEventListener("pointerleave", () => {
      this.hover = null;
      view.updateOverlays(this.selection, null, this.armed);
      view.showGhost(null, null, this.element);
    });
    view.onFrame = () => {
      if (this.drag) this.update();
      if (this.tool === "add" && this.hover !== null && !this.locked) {
        const p = placement(
          this.getModel(),
          this.hover,
          this.element,
          view.camera.getWorldDirection(new Vector3()),
        );
        view.showGhost(p, this.hover, this.element);
      }
    };
  }
  snapshot() {
    return structuredClone({
      model: this.getModel(),
      selection: this.selection,
    });
  }
  push(snapshot = this.snapshot()) {
    this.undoStack.push(snapshot);
    if (this.undoStack.length > 50) this.undoStack.shift();
    this.redoStack = [];
  }
  mutate(fn) {
    if (this.locked) return;
    this.push();
    fn(this.getModel());
    this.getModel().smiles = "";
    this.armed = null;
    this.hover = null;
    this.view.showGhost(null, null, this.element);
    this.onChange(this.getModel(), true);
    this.warn();
    this.update();
  }
  warn() {
    const m = this.getModel(),
      vals = m.atoms.map(() => 0);
    for (const b of m.bonds) {
      vals[b.a] += b.order === 4 ? 1.5 : b.order;
      vals[b.b] += b.order === 4 ? 1.5 : b.order;
    }
    const over = m.atoms
      .map((a, i) =>
        !a.charge && maxValence[a.el] && vals[i] > maxValence[a.el]
          ? `${a.el}${i + 1} (${vals[i]})`
          : null,
      )
      .filter(Boolean);
    if (over.length)
      this.toast(
        "Valence warning: " + over.slice(0, 4).join(", ") + ". Edit kept.",
        "warning",
      );
  }
  reset() {
    this.cancel();
    this.selection = [];
    this.armed = null;
    this.hover = null;
    this.undoStack = [];
    this.redoStack = [];
    this.update();
  }
  setTool(tool) {
    if (this.locked) return;
    this.cancel();
    this.tool = tool;
    this.armed = null;
    this.hover = null;
    this.view.showGhost(null, null, this.element);
    if (tool !== "select") this.view.style.spin = false;
    this.view.controls.autoRotate = this.view.style.spin;
    this.view.renderer.domElement.style.cursor =
      tool === "move"
        ? "move"
        : ["add", "delete", "bond"].includes(tool)
          ? "crosshair"
          : "grab";
    this.update();
  }
  update() {
    this.selection = this.selection.filter(
      (i) => this.getModel().atoms[i] && this.view.visible(i),
    );
    this.view.updateOverlays(this.selection, this.hover, this.armed);
    this.onState?.(this);
  }
  undo() {
    if (this.locked || !this.undoStack.length) return;
    this.cancel();
    this.redoStack.push(this.snapshot());
    const s = this.undoStack.pop();
    this.selection = s.selection;
    this.armed = null;
    this.hover = null;
    this.onChange(s.model, true);
    this.update();
  }
  redo() {
    if (this.locked || !this.redoStack.length) return;
    this.cancel();
    this.undoStack.push(this.snapshot());
    const s = this.redoStack.pop();
    this.selection = s.selection;
    this.armed = null;
    this.hover = null;
    this.onChange(s.model, true);
    this.update();
  }
  select(i) {
    const k = this.selection.indexOf(i);
    if (k >= 0) this.selection.splice(k, 1);
    else {
      if (this.selection.length === 4) this.selection = [];
      this.selection.push(i);
    }
    this.update();
  }
  add(parent, position) {
    this.mutate((m) => {
      const p =
        parent === null
          ? position
          : placement(
              m,
              parent,
              this.element,
              this.view.camera.getWorldDirection(new Vector3()),
            );
      if (!p) throw Error("Could not place atom on the viewing plane.");
      const i = m.atoms.length;
      m.atoms.push({ el: this.element, x: p.x, y: p.y, z: p.z });
      if (parent !== null) m.bonds.push({ a: parent, b: i, order: 1 });
      this.selection = [i];
    });
  }
  delete(ids) {
    if (!ids.length) return;
    this.mutate((m) => {
      const removed = new Set(ids),
        map = new Map();
      m.atoms = m.atoms.filter((a, i) => {
        if (removed.has(i)) return false;
        map.set(i, map.size);
        return true;
      });
      m.bonds = m.bonds
        .filter((b) => !removed.has(b.a) && !removed.has(b.b))
        .map((b) => ({ ...b, a: map.get(b.a), b: map.get(b.b) }));
      this.selection = [];
    });
  }
  bond(i) {
    if (this.armed === null) {
      this.armed = i;
      this.update();
      return;
    }
    if (this.armed === i) {
      this.armed = null;
      this.update();
      return;
    }
    const a = this.armed;
    this.mutate((m) => {
      const k = m.bonds.findIndex(
        (b) => (b.a === a && b.b === i) || (b.b === a && b.a === i),
      );
      if (k < 0) m.bonds.push({ a, b: i, order: 1 });
      else if (m.bonds[k].order >= 3) m.bonds.splice(k, 1);
      else m.bonds[k].order++;
    });
  }
  applyElement() {
    if (this.selection.length)
      this.mutate((m) => {
        for (const i of this.selection) m.atoms[i].el = this.element;
      });
  }
  async tidy() {
    if (this.locked || !this.getModel().atoms.length) return;
    const snapshot = this.snapshot(),
      candidate = structuredClone(this.getModel());
    this.locked = true;
    this.view.controls.autoRotate = false;
    this.update();
    const dismiss = this.toast("Relaxing geometry…", "info", 600000);
    try {
      await new Promise(requestAnimationFrame);
      await relax(candidate, 300, (progress) => {
        dismiss.update?.(`Relaxing geometry… ${Math.round(progress * 100)}%`);
        this.onProgress?.(progress);
      });
      this.push(snapshot);
      candidate.smiles = "";
      this.onChange(candidate, true);
      this.toast("Geometry tidied. Undo restores the original.");
    } catch (e) {
      this.toast(e.message, "error");
    } finally {
      dismiss();
      this.locked = false;
      this.view.controls.autoRotate = this.view.style.spin;
      this.update();
    }
  }
  new() {
    this.mutate((m) => {
      m.name = "Untitled molecule";
      m.smiles = "";
      m.atoms = [];
      m.bonds = [];
      this.selection = [];
    });
    this.setTool("add");
    this.view.fit();
  }
  down(e) {
    const hit = this.view.pick(e);
    if (e.button !== 0 || this.locked) return;
    this.start = { x: e.clientX, y: e.clientY, hit, pointerId: e.pointerId };
    if (this.tool === "move" && hit !== null) {
      const snapshot = this.snapshot();
      if (!this.selection.includes(hit))
        this.selection = e.shiftKey ? [...this.selection, hit] : [hit];
      const p = point(this.getModel().atoms[hit]),
        plane = new Plane().setFromNormalAndCoplanarPoint(
          this.view.camera.getWorldDirection(new Vector3()),
          p,
        ),
        origin = this.view.raycaster.ray.intersectPlane(plane, new Vector3());
      if (!origin) return;
      this.drag = {
        snapshot,
        plane,
        origin,
        positions: this.selection.map((i) => [
          i,
          point(this.getModel().atoms[i]),
        ]),
        moved: false,
        pointerId: e.pointerId,
      };
      this.view.controls.enabled = false;
      e.stopImmediatePropagation();
      this.view.renderer.domElement.setPointerCapture(e.pointerId);
      this.update();
    }
  }
  move(e) {
    const hit = this.view.pick(e);
    if (this.locked) return;
    if (this.drag && this.drag.pointerId === e.pointerId) {
      const p = this.view.raycaster.ray.intersectPlane(
        this.drag.plane,
        new Vector3(),
      );
      if (!p) return;
      const delta = p.sub(this.drag.origin);
      if (delta.length() > 0.001) this.drag.moved = true;
      for (const [i, start] of this.drag.positions) {
        const pos = start.clone().add(delta);
        Object.assign(this.getModel().atoms[i], {
          x: pos.x,
          y: pos.y,
          z: pos.z,
        });
      }
      this.view.syncModel(this.getModel(), {
        full: false,
        changed: this.drag.positions.map(([i]) => i),
      });
      this.update();
      e.stopImmediatePropagation();
      return;
    }
    this.hover = hit;
    this.view.updateOverlays(this.selection, hit, this.armed);
    if (this.tool === "add" && hit === null) {
      const plane = new Plane().setFromNormalAndCoplanarPoint(
        this.view.camera.getWorldDirection(new Vector3()),
        this.view.centroid(),
      );
      this.view.showGhost(
        this.view.raycaster.ray.intersectPlane(plane, new Vector3()),
        null,
        this.element,
      );
    } else if (this.tool !== "add")
      this.view.showGhost(null, null, this.element);
  }
  up(e) {
    const hit = this.view.pick(e);
    if (this.drag && this.drag.pointerId === e.pointerId) {
      const d = this.drag;
      this.drag = null;
      this.view.controls.enabled = true;
      if (d.moved) {
        this.push(d.snapshot);
        this.getModel().smiles = "";
        this.onChange(this.getModel(), false);
      }
      if (this.view.renderer.domElement.hasPointerCapture(e.pointerId))
        this.view.renderer.domElement.releasePointerCapture(e.pointerId);
      this.start = null;
      this.update();
      e.stopImmediatePropagation();
      return;
    }
    const start = this.start;
    this.start = null;
    if (
      !start ||
      start.pointerId !== e.pointerId ||
      e.button !== 0 ||
      Math.hypot(e.clientX - start.x, e.clientY - start.y) > 5 ||
      this.locked
    )
      return;
    if (this.tool === "add") {
      if (hit !== null) this.add(hit);
      else {
        const plane = new Plane().setFromNormalAndCoplanarPoint(
            this.view.camera.getWorldDirection(new Vector3()),
            this.view.centroid(),
          ),
          p = this.view.raycaster.ray.intersectPlane(plane, new Vector3());
        if (p) this.add(null, p);
      }
    } else if (hit !== null) {
      if (this.tool === "select" || this.tool === "move") this.select(hit);
      else if (this.tool === "delete") this.delete([hit]);
      else if (this.tool === "bond") this.bond(hit);
    }
  }
  cancel() {
    if (this.drag) {
      const d = this.drag;
      this.drag = null;
      this.selection = d.snapshot.selection;
      this.onChange(d.snapshot.model, true);
      const canvas = this.view.renderer.domElement;
      if (canvas.hasPointerCapture(d.pointerId))
        canvas.releasePointerCapture(d.pointerId);
    }
    this.start = null;
    this.view.controls.enabled = true;
  }
}
