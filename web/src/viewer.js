import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { CPK, dispR, vdWR } from "./chemistry.js";
import { measure, measurementText } from "./measure.js";
const V = (a) => new THREE.Vector3(a.x, a.y, a.z);
const up = new THREE.Vector3(0, 1, 0);
export class MolecularView {
  constructor(host) {
    this.host = host;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(
      38,
      innerWidth / innerHeight,
      0.05,
      5000,
    );
    this.camera.position.set(0, 0, 16);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.setPixelRatio(1);
    host.append(this.renderer.domElement);
    const pmrem = new THREE.PMREMGenerator(this.renderer),
      room = new RoomEnvironment();
    this.environment = pmrem.fromScene(room);
    this.scene.environment = this.environment.texture;
    room.dispose();
    pmrem.dispose();
    const light = new THREE.DirectionalLight(0xffffff, 1.0);
    light.position.set(5, 8, 6);
    this.scene.add(light);
    this.sphereGeometry = new THREE.SphereGeometry(1, 48, 32);
    this.cylinderGeometry = new THREE.CylinderGeometry(1, 1, 1, 20);
    this.coneGeometry = new THREE.ConeGeometry(1, 1, 24);
    this.style = {
      representation: "ball",
      palette: "cpk",
      hydrogens: true,
      labels: false,
      spin: false,
      size: 1,
      background: "light",
    };
    this.model = { atoms: [], bonds: [] };
    this.labels = new THREE.Group();
    this.scene.add(this.labels);
    this.initOverlays();
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = false;
    this.active = true;
    this.frameCount = 0;
    this.controls.addEventListener("change", () => this.invalidate());
    this.controls.autoRotateSpeed = 0.8;
    this.resize = () => {
      this.renderer.setSize(host.clientWidth, host.clientHeight);
      this.camera.aspect = host.clientWidth / host.clientHeight;
      this.camera.updateProjectionMatrix();
      this.invalidate();
    };
    this.resize();
    this.observer = new ResizeObserver(this.resize);
    this.observer.observe(host);
    this.invalidate();
  }
  invalidate() {
    if (this.disposed || !this.active || this.drawing || this.pendingFrame) return;
    this.pendingFrame = requestAnimationFrame((now) => {
      this.pendingFrame = null;
      if (!this.active || this.disposed) return;
      this.drawing = true;
      try {
        const delta=Math.min(0.1,Math.max(0,(now-(this.lastFrameTime??now))/1000));
        this.lastFrameTime=now;
        this.updateControls(delta);
        this.onFrame?.(now,delta);
        this.render();
        this.frameCount++;
      } finally { this.drawing = false; }
      if (this.controls.autoRotate || this.isAnimating?.()) this.invalidate();
    });
  }
  updateControls() { this.controls.update(); }
  render() { this.renderer.render(this.scene, this.camera); }
  setActive(active) {
    this.active = active;
    this.lastFrameTime=null;
    if (!active) { cancelAnimationFrame(this.pendingFrame); this.pendingFrame = null; }
    else { this.resize(); this.invalidate(); }
  }

  radius(a) {
    return (
      (this.style.representation === "space"
        ? (vdWR[a.el] ?? 1.6)
        : this.style.representation === "sticks"
          ? 0.16
          : (dispR[a.el] ?? 0.7)) * this.style.size
    );
  }
  color(a) {
    return this.style.palette === "paton"
      ? { C: "#d9d9d9", H: "#fafafa", N: "#8080ff", O: "#ff0000" }[a.el] ||
          CPK[a.el] ||
          "#D9D9D9"
      : CPK[a.el] || "#D9D9D9";
  }
  visible(i) {
    return this.style.hydrogens || this.model.atoms[i].el !== "H";
  }
  centroid() {
    const c = new THREE.Vector3();
    for (const a of this.model.atoms) c.add(V(a));
    return c.divideScalar(this.model.atoms.length || 1);
  }
  material() {
    return new THREE.MeshPhysicalMaterial({
      roughness: 0.3,
      metalness: 0,
      clearcoat: 0.5,
      clearcoatRoughness: 0.25,
    });
  }
  bondRadius() { return this.style.representation === "sticks" ? 0.16 : 0.1; }
  bondColor(atom) { return this.color(atom); }
  bondAxis(dir) {
    return dir.clone().cross(Math.abs(dir.dot(up)) > 0.9 ? new THREE.Vector3(1, 0, 0) : up).normalize();
  }
  syncModel(model, { full = true, changed = [] } = {}) {
    this.model = model;
    if (full) {
      for (const mesh of [this.atomMesh, this.bondMesh, this.arrowMesh])
        if (mesh) {
          this.scene.remove(mesh);
          mesh.material.dispose();
          mesh.dispose();
        }
      this.atomMesh = new THREE.InstancedMesh(
        this.sphereGeometry,
        this.material(),
        model.atoms.length,
      );
      this.scene.add(this.atomMesh);
      this.halves = [];
      this.arrows = [];
      model.bonds.forEach((b, index) => {
        if(b.kind==='ts') {
          for(let i=0;i<8;i++)this.halves.push({bond:index,offset:0,side:i<4?0:1,start:i/8,end:(i+.55)/8});
          return;
        }
        if(b.kind==='dative')this.arrows.push({bond:index});
        const offsets =
          !b.kind && b.order === 2
            ? [-0.16, 0.16]
            : b.order === 3
              ? [-0.22, 0, 0.22]
              : [0];
        for (const offset of offsets)
          for (let side = 0; side < 2; side++)
            this.halves.push({ bond: index, offset, side });
      });
      this.bondMesh = new THREE.InstancedMesh(
        this.cylinderGeometry,
        this.material(),
        this.halves.length,
      );
      this.scene.add(this.bondMesh);
      this.arrowMesh=new THREE.InstancedMesh(this.coneGeometry,this.material(),this.arrows.length);
      this.scene.add(this.arrowMesh);
      changed = model.atoms.map((_, i) => i);
      this.rebuildLabels();
    }
    const matrix = new THREE.Matrix4(),
      q = new THREE.Quaternion(),
      scale = new THREE.Vector3(),
      color = new THREE.Color(),
      dirty = new Set(changed);
    for (const i of changed) {
      const a = model.atoms[i],
        r = this.visible(i) ? this.radius(a) : 0;
      matrix.compose(V(a), q.identity(), scale.setScalar(r));
      this.atomMesh.setMatrixAt(i, matrix);
      this.atomMesh.setColorAt(i, color.set(this.color(a)));
    }
    for (let k = 0; k < this.halves.length; k++) {
      const h = this.halves[k],
        b = model.bonds[h.bond];
      if (!full && !dirty.has(b.a) && !dirty.has(b.b)) continue;
      const pa = V(model.atoms[b.a]),
        pb = V(model.atoms[b.b]),
        dir = pb.clone().sub(pa),
        length = dir.length();
      dir.normalize();
      const axis = h.offset ? this.bondAxis(dir, b) : up;
      const start=h.start??(h.side?.5:0),end=h.end??(h.side?1:.5);
      const usable=b.kind==='dative'?Math.max(0,length-this.radius(model.atoms[b.b])-.28):length;
      const pos = pa
        .clone()
        .addScaledVector(dir,usable*(start+end)/2)
        .addScaledVector(axis, h.offset);
      q.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        dir.lengthSq() ? dir : up,
      );
      const shown =
          this.visible(b.a) &&
          this.visible(b.b) &&
          this.style.representation !== "space" &&
          length > 1e-8,
        r = shown ? this.bondRadius() : 0;
      matrix.compose(pos, q, scale.set(b.kind==='ts'?r*.65:r, usable*(end-start), b.kind==='ts'?r*.65:r));
      this.bondMesh.setMatrixAt(k, matrix);
      this.bondMesh.setColorAt(
        k,
        color.set(this.bondColor(model.atoms[h.side ? b.b : b.a])),
      );
    }
    this.arrows.forEach((h,k)=>{
      const b=model.bonds[h.bond];if(!full&&!dirty.has(b.a)&&!dirty.has(b.b))return;
      const a=V(model.atoms[b.a]),dir=V(model.atoms[b.b]).sub(a),length=dir.length();dir.normalize();
      const tip=Math.max(0,length-this.radius(model.atoms[b.b])),height=Math.min(.45,tip*.5);
      const shown=this.visible(b.a)&&this.visible(b.b)&&this.style.representation!=='space'&&length>1e-8;
      q.setFromUnitVectors(up,length>1e-8?dir:up);
      matrix.compose(a.addScaledVector(dir,tip-height/2),q,scale.set(shown?this.bondRadius()*2.4:0,height,shown?this.bondRadius()*2.4:0));
      this.arrowMesh.setMatrixAt(k,matrix);this.arrowMesh.setColorAt(k,color.set(this.bondColor(model.atoms[b.b])));
    });
    for (const mesh of [this.atomMesh, this.bondMesh, this.arrowMesh]) {
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
    this.updateLabels();
    this.invalidate();
  }
  rebuildLabels() {
    for (const sprite of [...this.labels.children]) {
      sprite.material.map.dispose();
      sprite.material.dispose();
      this.labels.remove(sprite);
    }
    if (!this.style.labels) return;
    this.model.atoms.forEach((a, i) => {
      if (!this.visible(i)) return;
      const sprite = this.textSprite(a.el, 128, 128);
      sprite.scale.set(0.6, 0.6, 1);
      sprite.userData.atom = i;
      this.labels.add(sprite);
    });
  }
  textSprite(text, width = 256, height = 64) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.font = `600 ${height * 0.44}px system-ui`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineWidth = height * 0.065;
    ctx.strokeStyle = "white";
    ctx.strokeText(text, width / 2, height / 2);
    ctx.fillStyle = "#1a1d21";
    ctx.fillText(text, width / 2, height / 2);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: texture, depthTest: false }),
    );
    sprite.renderOrder = 5;
    return sprite;
  }
  updateLabels() {
    const c = this.centroid();
    for (const s of this.labels.children)
      s.position
        .copy(V(this.model.atoms[s.userData.atom]))
        .sub(c)
        .multiplyScalar(1.2)
        .add(c);
  }
  fit() {
    const c = this.centroid();
    let r = this.model.atoms.length ? 1 : 3;
    for (const a of this.model.atoms)
      r = Math.max(r, V(a).distanceTo(c) + this.radius(a));
    const fov = THREE.MathUtils.degToRad(this.camera.fov),
      distance = (r / Math.sin(fov / 2)) * 1.15;
    const narrow = Math.min(1, this.camera.aspect);
    this.camera.position
      .copy(c)
      .add(
        new THREE.Vector3(0.1, 0.16, 1)
          .normalize()
          .multiplyScalar(distance / narrow),
      );
    this.camera.up.set(0,1,0);
    this.controls.target.copy(c);
    this.camera.lookAt(c);
    this.controls.update();
  }
  initOverlays() {
    this.overlays = new THREE.Group();
    this.scene.add(this.overlays);
    const material = (opacity) =>
      new THREE.MeshBasicMaterial({
        color: 0x4f6df5,
        transparent: true,
        opacity,
        depthWrite: false,
      });
    this.hover = new THREE.Mesh(this.sphereGeometry, material(0.35));
    this.ghost = new THREE.Mesh(this.sphereGeometry, material(0.35));
    this.halos = new THREE.InstancedMesh(
      this.sphereGeometry,
      material(0.25),
      10000,
    );
    this.halos.count = 0;
    this.overlays.add(this.hover, this.ghost, this.halos);
    this.hover.visible = this.ghost.visible = false;
    this.prospect = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineDashedMaterial({
        color: 0x4f6df5,
        dashSize: 0.12,
        gapSize: 0.08,
        depthTest: false,
      }),
    );
    this.measureLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineDashedMaterial({
        color: 0x4f6df5,
        dashSize: 0.12,
        gapSize: 0.08,
        depthTest: false,
      }),
    );
    this.overlays.add(this.prospect, this.measureLine);
    this.prospect.visible = this.measureLine.visible = false;
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.selection = [];
    this.measurementCount = 0;
    this.hoverIndex = null;
  }
  pick(event) {
    const r = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(
      ((event.clientX - r.left) / r.width) * 2 - 1,
      (-(event.clientY - r.top) / r.height) * 2 + 1,
    );
    this.camera.updateMatrixWorld();
    this.atomMesh?.updateMatrixWorld();
    this.raycaster.setFromCamera(this.pointer, this.camera);
    if (!this.atomMesh) return null;
    const hit = this.raycaster
      .intersectObject(this.atomMesh)
      .find((h) => this.visible(h.instanceId));
    return hit?.instanceId ?? null;
  }
  updateOverlays(
    selection = this.selection,
    hover = this.hoverIndex,
    armed = null,
  ) {
    this.selection = selection;
    this.hoverIndex = hover;
    const shown =
      hover !== null && this.model.atoms[hover] && this.visible(hover);
    this.hover.visible = !!shown;
    if (shown) {
      this.hover.position.copy(V(this.model.atoms[hover]));
      this.hover.scale.setScalar(this.radius(this.model.atoms[hover]) * 1.35);
    }
    const ids = [
      ...new Set([...selection, ...(armed === null ? [] : [armed])]),
    ].filter((i) => this.model.atoms[i] && this.visible(i));
    this.halos.count = ids.length;
    const obj = new THREE.Object3D();
    ids.forEach((i, k) => {
      obj.position.copy(V(this.model.atoms[i]));
      obj.scale.setScalar(this.radius(this.model.atoms[i]) * 1.45);
      obj.updateMatrix();
      this.halos.setMatrixAt(k, obj.matrix);
    });
    this.halos.instanceMatrix.needsUpdate = true;
    this.halos.computeBoundingSphere();
    this.updateMeasurement();
    this.invalidate();
  }
  updateMeasurement() {
    const ids = this.selection.filter(
        (i) => this.model.atoms[i] && this.visible(i),
      ),
      m = ids.length === this.selection.length && (!this.measurementCount || ids.length === this.measurementCount)
        ? measure(this.model.atoms, ids) : null,
      text = measurementText(m);
    this.measureLine.visible = !!m;
    if (m) {
      this.measureLine.geometry.dispose();
      this.measureLine.geometry = new THREE.BufferGeometry().setFromPoints(
        ids.map((i) => V(this.model.atoms[i])),
      );
      this.measureLine.computeLineDistances();
      if (this.measureText !== text) {
        if (this.measureLabel) {
          this.overlays.remove(this.measureLabel);
          this.measureLabel.material.map.dispose();
          this.measureLabel.material.dispose();
        }
        this.measureLabel = this.textSprite(text, 512, 96);
        this.measureLabel.scale.set(2, 0.375, 1);
        this.overlays.add(this.measureLabel);
        this.measureText = text;
      }
      this.measureLabel.position
        .copy(
          ids
            .reduce(
              (v, i) => v.add(V(this.model.atoms[i])),
              new THREE.Vector3(),
            )
            .divideScalar(ids.length),
        )
        .add(new THREE.Vector3(0, 0.35, 0));
    }
    if (this.measureLabel) this.measureLabel.visible = !!m;
    this.onMeasurement?.(m, text);
    this.reportMeasurement?.(m, text, ids);
  }
  showGhost(position, parent, el) {
    if (position || this.ghost.visible) this.invalidate();
    this.ghost.visible = !!position;
    this.prospect.visible = !!position && parent !== null;
    if (!position) return;
    this.ghost.position.copy(position);
    this.ghost.scale.setScalar(this.radius({ el }));
    this.ghost.material.color.set(this.color({ el }));
    if (parent !== null) {
      this.prospect.geometry.dispose();
      this.prospect.geometry = new THREE.BufferGeometry().setFromPoints([
        V(this.model.atoms[parent]),
        position,
      ]);
      this.prospect.computeLineDistances();
    }
  }
  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.pendingFrame);
    this.renderer.setAnimationLoop(null);
    this.observer.disconnect();
    this.controls.dispose();
    this.scene.traverse((o) => {
      if (o.material) {
        o.material.map?.dispose();
        o.material.dispose();
      }
      if (o.isInstancedMesh) o.dispose();
      if (
        o.geometry &&
        o.geometry !== this.sphereGeometry &&
        o.geometry !== this.cylinderGeometry && o.geometry !== this.coneGeometry
      )
        o.geometry.dispose();
    });
    this.sphereGeometry.dispose();
    this.cylinderGeometry.dispose();
    this.coneGeometry.dispose();
    this.environment.dispose();
    this.renderer.dispose();
  }
}
