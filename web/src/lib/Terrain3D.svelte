<script>
  // 3D terrain of Upcountry Maui with the project's layers draped over it.
  //
  // Elevation: a 320 x 293 grid (scripts/fetch_terrain.py), checked against GLOBE
  // observers' phone elevations at 30 sites (median difference 1 m).
  // Everything else — browning patches, fire perimeters, the study-area circle —
  // is painted onto one canvas texture. Because the grid is linear in lat/lon, a
  // canvas pixel maps straight onto the mesh with no reprojection.
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import * as THREE from 'three';
  import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
  import {
    makeProjection, sampleElevation, toCanvas, elevationColor, polygonsOf,
  } from './geo.js';

  export let terrain;            // { meta, grid }
  export let browning;           // GeoJSON FeatureCollection
  export let fires;              // GeoJSON FeatureCollection
  export let sites = [];         // pins from /api/layers/sites
  export let studyArea;          // { lat, lon, radius_m }
  export let show = { browning: true, fires: true, sites: true, study: true };
  export let exaggeration = 2;
  export let selectedId = null;

  const dispatch = createEventDispatcher();
  const CANVAS_W = 2048;

  let container;
  let hover = null;              // { x, y, text } for the tooltip
  let renderer, scene, camera, controls, mesh, texture, overlay, baseLayer;
  let pinGroup, proj, ready = false, pinCount = 0, raf = 0;

  // ---------- scene ----------
  function build() {
    const { meta, grid } = terrain;
    proj = makeProjection(meta.bbox);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    scene.background = new THREE.Color('#0f171b');
    scene.fog = new THREE.Fog('#0f171b', 30, 70);

    camera = new THREE.PerspectiveCamera(48, 1, 0.05, 200);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI * 0.48;   // never go under the ground
    controls.minDistance = 0.6;
    controls.maxDistance = 40;
    controls.addEventListener('change', requestRender);

    // Sun from the north-west, high: gives the slopes readable relief.
    scene.add(new THREE.HemisphereLight('#dfe9ee', '#3a3125', 1.1));
    const sun = new THREE.DirectionalLight('#fff4e0', 1.6);
    sun.position.set(-8, 12, -6);
    scene.add(sun);

    // Terrain mesh: one vertex per grid sample. After rotating the plane flat,
    // its first row lies at -z (north), matching the grid's north-to-south rows.
    const geom = new THREE.PlaneGeometry(proj.widthKm, proj.heightKm, meta.width - 1, meta.height - 1);
    geom.rotateX(-Math.PI / 2);

    overlay = document.createElement('canvas');
    overlay.width = CANVAS_W;
    overlay.height = Math.round((CANVAS_W * proj.heightKm) / proj.widthKm);
    baseLayer = paintBase(meta, grid);
    texture = new THREE.CanvasTexture(overlay);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();

    mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ map: texture, roughness: 1, metalness: 0 }));
    scene.add(mesh);

    pinGroup = new THREE.Group();
    scene.add(pinGroup);

    // Start looking at the study area from the south-west, up the mountain.
    const [sx, sz] = proj.toLocal(studyArea.lon, studyArea.lat);
    const sy = (sampleElevation(grid, meta, studyArea.lon, studyArea.lat) || 0) / 1000;
    controls.target.set(sx, sy * exaggeration, sz);
    camera.position.set(sx - 5.5, sy * exaggeration + 5, sz + 7.5);

    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('pointerup', onPointerUp);

    resize();
    new ResizeObserver(resize).observe(container);
    ready = true;
  }

  // Only render when something changed. Cheaper than a constant loop, and it
  // still renders correctly when the tab is in the background.
  function requestRender() {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (controls.update()) requestRender();   // keep going while damping settles
      renderer.render(scene, camera);
    });
  }
  function renderNow() {
    controls.update();
    renderer.render(scene, camera);
  }

  function resize() {
    if (!renderer || !container) return;
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderNow();
  }

  // ---------- texture ----------
  // The elevation tint is computed once at grid resolution, then scaled up.
  function paintBase(meta, grid) {
    const c = document.createElement('canvas');
    c.width = meta.width; c.height = meta.height;
    const ctx = c.getContext('2d');
    const img = ctx.createImageData(meta.width, meta.height);
    for (let i = 0; i < grid.length; i++) {
      const [r, g, b] = grid[i] <= 0 ? [34, 62, 84] : elevationColor(grid[i]);
      img.data.set([r, g, b, 255], i * 4);
    }
    ctx.putImageData(img, 0, 0);
    return c;
  }

  function tracePolygons(ctx, geometry) {
    const { bbox } = terrain.meta;
    for (const rings of polygonsOf(geometry)) {
      for (const ring of rings) {
        ring.forEach(([lon, lat], i) => {
          const [x, y] = toCanvas(bbox, overlay.width, overlay.height, lon, lat);
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.closePath();
      }
    }
  }

  function paintOverlay() {
    const ctx = overlay.getContext('2d');
    const { bbox } = terrain.meta;
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(baseLayer, 0, 0, overlay.width, overlay.height);

    if (show.browning && browning) {
      // Holes in the patches are unbrowned ground: 'evenodd' leaves them unfilled.
      ctx.beginPath();
      for (const f of browning.features) tracePolygons(ctx, f.geometry);
      ctx.fillStyle = 'rgba(232, 150, 70, 0.9)';
      ctx.fill('evenodd');
    }

    if (show.fires && fires) {
      for (const f of fires.features) {
        const recent = f.properties.year === 2023;
        ctx.beginPath();
        tracePolygons(ctx, f.geometry);
        ctx.fillStyle = recent ? 'rgba(229, 57, 53, 0.30)' : 'rgba(255, 152, 0, 0.18)';
        ctx.fill('evenodd');
        ctx.lineWidth = recent ? 4 : 2.5;
        ctx.setLineDash(recent ? [] : [10, 8]);
        ctx.strokeStyle = recent ? '#ff3b30' : '#ff9800';
        ctx.stroke();
      }
      ctx.setLineDash([]);
    }

    if (show.study && studyArea) {
      const [cx, cy] = toCanvas(bbox, overlay.width, overlay.height, studyArea.lon, studyArea.lat);
      const pxPerKm = overlay.width / proj.widthKm;
      ctx.beginPath();
      ctx.arc(cx, cy, (studyArea.radius_m / 1000) * pxPerKm, 0, Math.PI * 2);
      ctx.lineWidth = 4;
      ctx.setLineDash([14, 10]);
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
      ctx.setLineDash([]);
    }

    texture.needsUpdate = true;
    requestRender();
  }

  // ---------- relief ----------
  function applyExaggeration() {
    const { grid } = terrain;
    const pos = mesh.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      pos.setY(i, (Math.max(grid[i], 0) / 1000) * exaggeration);
    }
    pos.needsUpdate = true;
    mesh.geometry.computeVertexNormals();
    // Keep the camera's focus on the ground as the relief scales.
    const t = controls.target;
    const lonlat = [proj.lon0 + t.x / proj.kx, proj.lat0 - t.z / proj.ky];
    const ground = sampleElevation(grid, terrain.meta, lonlat[0], lonlat[1]);
    if (ground !== null) t.y = (ground / 1000) * exaggeration;
    renderPins();
  }

  // ---------- pins ----------
  function pinColor(f) {
    if (f === null || f === undefined) return '#9aa9b0';    // outside the study area
    return f >= 0.25 ? '#ff9f43' : '#4fb286';
  }

  function renderPins() {
    for (const child of [...pinGroup.children]) {
      pinGroup.remove(child);
      child.geometry?.dispose(); child.material?.dispose();
    }
    pinCount = 0;
    if (!show.sites) { requestRender(); return; }
    const { grid, meta } = terrain;
    for (const pin of sites) {
      const ground = sampleElevation(grid, meta, pin.lon, pin.lat);
      if (ground === null) continue;
      const [x, z] = proj.toLocal(pin.lon, pin.lat);
      const y = (Math.max(ground, 0) / 1000) * exaggeration;
      const selected = pin.land_cover_id === selectedId || pin.site_id === selectedId;
      const stemH = selected ? 0.55 : 0.35;

      const stem = new THREE.Mesh(
        new THREE.CylinderGeometry(0.012, 0.012, stemH, 6),
        new THREE.MeshBasicMaterial({ color: '#e8eff0' })
      );
      stem.position.set(x, y + stemH / 2, z);
      pinGroup.add(stem);

      const head = new THREE.Mesh(
        new THREE.SphereGeometry(selected ? 0.11 : 0.075, 16, 12),
        new THREE.MeshBasicMaterial({ color: pinColor(pin.browned_fraction) })
      );
      head.position.set(x, y + stemH, z);
      head.userData.pin = pin;
      pinGroup.add(head);
      pinCount++;
    }
    requestRender();
  }

  // ---------- picking ----------
  const raycaster = new THREE.Raycaster();
  let downAt = null;

  function pickPin(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1
    );
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObjects(pinGroup.children.filter((c) => c.userData.pin))[0];
    return hit ? hit.object.userData.pin : null;
  }

  function onPointerMove(event) {
    const pin = pickPin(event);
    renderer.domElement.style.cursor = pin ? 'pointer' : 'grab';
    if (!pin) { hover = null; return; }
    const rect = renderer.domElement.getBoundingClientRect();
    const f = pin.browned_fraction;
    hover = {
      x: event.clientX - rect.left, y: event.clientY - rect.top,
      text: `${pin.label} · ${f === null ? 'outside study area' : Math.round(f * 100) + '% browned'}`,
    };
  }
  function onPointerDown(event) { downAt = [event.clientX, event.clientY]; }
  function onPointerUp(event) {
    // A click, not the end of a drag-to-orbit.
    if (!downAt || Math.hypot(event.clientX - downAt[0], event.clientY - downAt[1]) > 5) return;
    const pin = pickPin(event);
    if (pin) dispatch('select', pin);
  }

  /** Swing the view to a lat/lon, e.g. when a site is picked from the list. */
  export function focus(lat, lon) {
    if (!ready) return;
    const [x, z] = proj.toLocal(lon, lat);
    const ground = sampleElevation(terrain.grid, terrain.meta, lon, lat) || 0;
    const offset = camera.position.clone().sub(controls.target);
    controls.target.set(x, (ground / 1000) * exaggeration, z);
    camera.position.copy(controls.target).add(offset);
    requestRender();
  }

  // ---------- lifecycle ----------
  onMount(() => {
    build();
    paintOverlay();
    applyExaggeration();
  });

  onDestroy(() => {
    cancelAnimationFrame(raf);
    controls?.dispose();
    renderer?.dispose();
    texture?.dispose();
    mesh?.geometry.dispose();
    mesh?.material.dispose();
  });

  // Reactive updates once the scene exists.
  $: if (ready) { show; paintOverlay(); }
  $: if (ready) { exaggeration; applyExaggeration(); }
  $: if (ready) { sites; selectedId; show; renderPins(); }
</script>

<div class="map3d" bind:this={container} data-ready={ready} data-pins={pinCount}>
  {#if hover}
    <div class="tip" style="left:{hover.x + 14}px; top:{hover.y + 10}px">{hover.text}</div>
  {/if}
</div>

<style>
  .map3d { position: absolute; inset: 0; overflow: hidden; }
  .map3d :global(canvas) { display: block; cursor: grab; }
  .tip {
    position: absolute; pointer-events: none; white-space: nowrap;
    background: rgba(15, 23, 27, 0.92); border: 1px solid #2c3a41; color: #e8eff0;
    font-size: 12px; padding: 4px 8px; border-radius: 6px;
  }
</style>
