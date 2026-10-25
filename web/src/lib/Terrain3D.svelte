<script>
  // 3D terrain of Upcountry Maui with the project's layers draped over it.
  //
  // Elevation: a 320 x 293 grid (scripts/fetch_terrain.py), checked against GLOBE
  // observers' phone elevations at 30 sites (median difference 1 m).
  // Everything else, browning patches, fire perimeters, the study-area circle,
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
  // Optional real imagery (a canvas covering exactly the terrain bbox, linear in
  // lat/lon. See scripts/gee/imagery_before_after.js). Replaces the elevation tint.
  export let imagery = null;
  // Optional pixel-level browning: { canvas, corners } from raster.renderBelow, with
  // corners as [lon, lat] NW, NE, SE, SW. Replaces the patch polygons when given.
  // The UTM pixel grid is drawn axis-aligned in lat/lon; over the 3 km raster the
  // grid's rotation against true north moves edges by about one 10 m pixel.
  export let change = null;
  // Optional (lon, lat) => tooltip text for the ground under the pointer, so the
  // page can report raster values without this component knowing about them.
  export let probe = null;
  // Optional lidar points ({ lon, lat, hag, count } typed arrays): drawn at their
  // height above ground on top of this mesh, coloured by that height.
  export let points = null;
  export let pointColour = (hag) => [1, 1, 1];

  const dispatch = createEventDispatcher();
  const CANVAS_W = 2048;

  let container;
  let hover = null;              // { x, y, text } for the tooltip
  let renderer, scene, camera, controls, mesh, texture, overlay, baseLayer;
  let pinGroup, proj, ready = false, pinCount = 0, raf = 0, cloud = null;

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
    ctx.drawImage(imagery || baseLayer, 0, 0, overlay.width, overlay.height);

    if (show.browning && change) {
      const [nw, , se] = change.corners;
      const [x0, y0] = toCanvas(bbox, overlay.width, overlay.height, nw[0], nw[1]);
      const [x1, y1] = toCanvas(bbox, overlay.width, overlay.height, se[0], se[1]);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(change.canvas, x0, y0, x1 - x0, y1 - y0);
      ctx.imageSmoothingEnabled = true;
    } else if (show.browning && browning) {
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

      // Square markers, not spheres (no round symbols anywhere).
      const head = new THREE.Mesh(
        new THREE.BoxGeometry(...(selected ? [0.18, 0.18, 0.18] : [0.12, 0.12, 0.12])),
        new THREE.MeshBasicMaterial({ color: pinColor(pin.browned_fraction) })
      );
      head.position.set(x, y + stemH, z);
      head.userData.pin = pin;
      pinGroup.add(head);
      pinCount++;
    }
    requestRender();
  }

  // ---------- lidar point cloud ----------
  function renderPoints() {
    if (cloud) { scene.remove(cloud); cloud.geometry.dispose(); cloud.material.dispose(); cloud = null; }
    if (!points || !show.points) { requestRender(); return; }
    const { grid, meta } = terrain;
    const pos = new Float32Array(points.count * 3), col = new Float32Array(points.count * 3);
    for (let i = 0; i < points.count; i++) {
      const [x, z] = proj.toLocal(points.lon[i], points.lat[i]);
      const ground = sampleElevation(grid, meta, points.lon[i], points.lat[i]) ?? 0;
      // Height above the lidar ground, set on this mesh's ground, so the cloud
      // sits on the surface whatever the vertical datum of either source.
      pos[i * 3] = x; pos[i * 3 + 1] = ((Math.max(ground, 0) + Math.max(points.hag[i], 0)) / 1000) * exaggeration + 0.002; pos[i * 3 + 2] = z;
      const c = pointColour(points.hag[i]);
      col[i * 3] = c[0]; col[i * 3 + 1] = c[1]; col[i * 3 + 2] = c[2];
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    cloud = new THREE.Points(g, new THREE.PointsMaterial({ size: 2, sizeAttenuation: false, vertexColors: true }));
    scene.add(cloud);
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

  /** lon/lat of the terrain surface under the pointer, or null (sky). */
  function pickGround(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1), camera);
    const hit = raycaster.intersectObject(mesh)[0];
    if (!hit) return null;
    return { lon: proj.lon0 + hit.point.x / proj.kx, lat: proj.lat0 - hit.point.z / proj.ky };
  }

  function onPointerMove(event) {
    const pin = pickPin(event);
    renderer.domElement.style.cursor = pin ? 'pointer' : 'grab';
    const rect = renderer.domElement.getBoundingClientRect();
    if (!pin) {
      const g = probe && pickGround(event);
      const text = g ? probe(g.lon, g.lat) : null;
      hover = text ? { x: event.clientX - rect.left, y: event.clientY - rect.top, text } : null;
      return;
    }
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
    if (pin) { dispatch('select', pin); return; }
    const g = pickGround(event);
    if (g) dispatch('inspect', g);
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

  // ---------- camera moves (guided tour) ----------
  const reduceMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  let flight = 0;

  /** Move the camera to look at lat/lon from a heading (degrees clockwise from
   *  north), pitch above the horizon, and distance in km. Eased; instant when the
   *  viewer prefers reduced motion. Resolves when the move finishes. */
  export function flyTo(lat, lon, { distanceKm = 6, headingDeg = 135, pitchDeg = 35, duration = 2200 } = {}) {
    if (!ready) return Promise.resolve();
    const [x, z] = proj.toLocal(lon, lat);
    const ground = (Math.max(sampleElevation(terrain.grid, terrain.meta, lon, lat) || 0, 0) / 1000) * exaggeration;
    const h = (headingDeg * Math.PI) / 180, p = (pitchDeg * Math.PI) / 180;
    const endTarget = new THREE.Vector3(x, ground, z);
    // The camera sits behind the look direction: north is -z, east is +x.
    const endPos = endTarget.clone().add(new THREE.Vector3(
      -Math.sin(h) * Math.cos(p) * distanceKm, Math.sin(p) * distanceKm, Math.cos(h) * Math.cos(p) * distanceKm));
    const startTarget = controls.target.clone(), startPos = camera.position.clone();
    const id = ++flight;
    const ms = reduceMotion ? 0 : duration;
    return new Promise((resolve) => {
      const t0 = performance.now();
      const step = (now) => {
        if (id !== flight) return resolve();           // superseded by a newer move
        const t = ms ? Math.min(1, (now - t0) / ms) : 1;
        const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        controls.target.lerpVectors(startTarget, endTarget, e);
        camera.position.lerpVectors(startPos, endPos, e);
        renderNow();
        if (t < 1) requestAnimationFrame(step); else resolve();
      };
      requestAnimationFrame(step);
    });
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
  $: if (ready) { show; imagery; change; paintOverlay(); }
  $: if (ready) { exaggeration; applyExaggeration(); }
  $: if (ready) { sites; selectedId; show; renderPins(); }
  $: if (ready) { points; show; exaggeration; renderPoints(); }
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
    background: #0f171b; border: 1px solid #2c3a41; font-family: var(--mono); color: #e8eff0;
    font-size: 12px; padding: 4px 8px; border-radius: 0;
  }
</style>
