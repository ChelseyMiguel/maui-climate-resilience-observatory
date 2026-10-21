/* Cube-map viewer for a GLOBE land cover observation.
 *
 * The land cover protocol gives six photos taken from one standing point:
 * N/S/E/W plus straight up and straight down. That is the same sampling a cube
 * map uses, so we map each photo to one face of a box and put the camera inside
 * it. The result is a look-around reconstruction of the site.
 *
 * This is deliberately NOT photogrammetry. Six photos from a single point have
 * no parallax, so there is no recoverable depth — this reprojects the photos
 * onto a cube so a viewer can look around, and the seams between faces are real
 * (phone FOV is narrower than the 90 degrees a true cube face needs). Honest
 * framing of that limit is part of the project's story.
 *
 * Same stack as the CoralPulse species viewer: vendored ESM + htm tagged
 * templates, no JSX, no build step.
 */

import React, { useState, useEffect, useMemo, useRef } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import htm from "htm";
import {
  cameraPositionToFace, lookingLabel, viewFromControls,
} from "/static/js/view-math.mjs";

const html = htm.bind(React.createElement);

/* Where each of the six photos sits, as one inward-facing plane per direction.
 *
 * The camera stands at the origin looking down -Z, matching a person standing
 * at the site facing north. Each plane is pushed out to the cube face and
 * rotated so its front side looks back at the viewer, which means every photo
 * reads the right way round with no mirroring correction.
 */
const HALF = 5; // half-extent of the cube, in scene units
const HALF_PI = Math.PI / 2;

export const FACES = [
  { direction: "North", position: [0, 0, -HALF], rotation: [0, 0, 0] },
  { direction: "South", position: [0, 0, HALF], rotation: [0, Math.PI, 0] },
  { direction: "East", position: [HALF, 0, 0], rotation: [0, -HALF_PI, 0] },
  { direction: "West", position: [-HALF, 0, 0], rotation: [0, HALF_PI, 0] },
  { direction: "Upward", position: [0, HALF, 0], rotation: [HALF_PI, 0, 0] },
  { direction: "Downward", position: [0, -HALF, 0], rotation: [-HALF_PI, 0, 0] },
];

const NEUTRAL = "#2b3a34"; // fill for a direction the observer skipped

/* Phone cameras do not see 90 degrees, so stretching a photo across a whole cube
 * face (the default "fill" view) distorts it and puts seams where the scene does
 * not actually join. "True field of view" instead draws each photo at the angle
 * it really covers. We have no EXIF here, so this ASSUMES a ~65 degree view along
 * the photo's long side, typical of a phone's main camera; the toggle says so.
 */
export const ASSUMED_LONG_SIDE_FOV_DEG = 65;

function faceSize(image, trueFov) {
  const full = HALF * 2;
  if (!trueFov || !image || !image.width || !image.height) return [full, full];
  const long = 2 * HALF * Math.tan((ASSUMED_LONG_SIDE_FOV_DEG * Math.PI) / 360);
  const landscape = image.width >= image.height;
  return landscape
    ? [long, (long * image.height) / image.width]
    : [(long * image.width) / image.height, long];
}

/* The six faces.
 *
 * Textures load imperatively rather than through `useLoader`/Suspense: an
 * observation can be missing directions, so the loader would have to suspend on
 * a ragged list and then re-associate results back to face slots. Loading each
 * face on its own means a skipped direction simply stays flat colour, and faces
 * appear as they arrive instead of all-or-nothing. Citizen-submitted photos vary
 * a lot in size, so a failed face degrades to flat colour rather than breaking
 * the whole reconstruction. */
function CubeFaces({ photos, trueFov }) {
  const urls = useMemo(
    () => FACES.map((f) => (photos && photos[f.direction] && photos[f.direction].photo_url) || null),
    [photos]
  );
  const [textures, setTextures] = useState(() => FACES.map(() => null));

  useEffect(() => {
    let cancelled = false;
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin("anonymous");

    setTextures(FACES.map(() => null));
    const loaded = FACES.map(() => null);

    urls.forEach((url, i) => {
      if (!url) return;
      loader.load(
        url,
        (texture) => {
          if (cancelled) {
            texture.dispose();
            return;
          }
          texture.colorSpace = THREE.SRGBColorSpace;
          loaded[i] = texture;
          setTextures([...loaded]);
        },
        undefined,
        () => {} // leave the face flat if the photo will not load
      );
    });

    return () => {
      cancelled = true;
      loaded.forEach((t) => t && t.dispose());
    };
  }, [urls]);

  // The material's `key` flips once the texture arrives, so the material is
  // rebuilt rather than mutated: a three.js material compiled with no map will
  // not pick one up later without a shader recompile, and would otherwise keep
  // rendering as flat white.
  return html`
    <group>
      ${trueFov ? html`
        <mesh>
          <boxGeometry args=${[HALF * 2 + 0.2, HALF * 2 + 0.2, HALF * 2 + 0.2]} />
          <meshBasicMaterial color="#0d1316" side=${THREE.BackSide} />
        </mesh>` : null}
      ${FACES.map((face, i) => {
        const tex = textures[i];
        const [w, h] = faceSize(tex && tex.image, trueFov && !!tex);
        return html`
          <mesh key=${face.direction} position=${face.position} rotation=${face.rotation}>
            <planeGeometry args=${[w, h]} />
            <meshBasicMaterial
              key=${tex ? "textured" : "empty"}
              map=${tex}
              color=${tex ? "#ffffff" : NEUTRAL}
              side=${THREE.DoubleSide}
              toneMapped=${false} />
          </mesh>`;
      })}
    </group>`;
}

/* Compass/orientation readout so a viewer knows which way they are facing. */
function HeadingBadge({ observation }) {
  // The badge carries a lot (readout, sparkline) and sits over the 3D view, so it
  // can be folded down to one line. The choice is remembered across sites and
  // reloads, but a blocked/unavailable localStorage must never break rendering.
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("globe:badgeCollapsed") === "1"; } catch (e) { return false; }
  });
  const toggle = () => {
    setCollapsed((c) => {
      try { localStorage.setItem("globe:badgeCollapsed", c ? "0" : "1"); } catch (e) { /* ignore */ }
      return !c;
    });
  };
  if (!observation) return null;
  const missing = observation.missing_directions || [];

  if (collapsed) {
    return html`
      <div className="viewer-badge viewer-badge-collapsed">
        <span className="viewer-site">${observation.site_name}</span>
        <span className="viewer-meta"> ${(observation.measured_at || "").slice(0, 10)}</span>
        <button className="badge-toggle" onClick=${toggle}
                aria-label="Show details" title="Show details">+</button>
      </div>`;
  }
  return html`
    <div className="viewer-badge">
      <button className="badge-toggle" onClick=${toggle}
              aria-label="Hide details" title="Hide details">−</button>
      <div className="viewer-site">${observation.site_name}</div>
      <div className="viewer-meta">
        ${(observation.measured_at || "").slice(0, 10)} ·
        ${observation.latitude.toFixed(4)}, ${observation.longitude.toFixed(4)}
        ${observation.elevation_m != null ? ` · ${Math.round(observation.elevation_m)} m` : ""}
      </div>
      ${observation.muc_description
        ? html`<div className="viewer-muc">${observation.muc_description}</div>`
        : null}
      ${missing.length
        ? html`<div className="viewer-warn">
            missing ${missing.length}/6: ${missing.join(", ")}
          </div>`
        : null}
      <${BrowningReadout} vegetation=${observation.vegetation} />
      ${observation.fire && observation.fire.available ? html`
        <div className="veg-sub fire-line">
          Nearest Aug 2023 fire: ${observation.fire.nearest_fire},
          ${observation.fire.inside_perimeter ? " inside its perimeter" : ` ${observation.fire.distance_km} km away`}
        </div>` : null}
      <${SatellitePanel} satellite=${observation.satellite} />
      ${observation.vegetation && observation.vegetation.in_analysis_area
        ? html`<${NdviSparkline} />`
        : null}
    </div>`;
}

/* What three satellite land-cover maps call this spot, next to what the
 * observer standing here recorded. At parks and roadsides a 10-30 m pixel mixes
 * grass with pavement, and the maps often disagree with each other; the photos
 * around you are the ground truth they lack. Agreement is shown as a symbol AND
 * a word, never colour alone. */
const VERDICT = {
  agree: ["✓", "matches the observer"],
  partial: ["≈", "partly matches"],
  disagree: ["✗", "differs from the observer"],
  unmapped: ["–", "not comparable"],
};

function SatellitePanel({ satellite }) {
  if (!satellite || !satellite.available) return null;
  const hasObserver = Boolean(satellite.observer_label);
  return html`
    <div className="sat">
      <div className="sat-title">What satellites call this spot</div>
      ${hasObserver
        ? html`<div className="sat-sub">Observer recorded: <b>${satellite.observer_label}</b></div>`
        : null}
      <ul className="sat-list">
        ${satellite.maps.map((m) => {
          const [mark, words] = VERDICT[m.verdict] || VERDICT.unmapped;
          return html`
            <li key=${m.product} className=${"sat-row sat-" + m.verdict}>
              <span className="sat-mark" aria-hidden="true">${hasObserver ? mark : "·"}</span>
              <span className="sat-name">${m.name} <span className="sat-res">${m.resolution}, ${m.year}</span></span>
              <span className="sat-class">${m.class_name.replace(/_/g, " ")}</span>
              ${hasObserver ? html`<span className="sr-only">${words}</span>` : null}
            </li>`;
        })}
      </ul>
      <div className="sat-note">
        ${satellite.maps_agree === false
          ? "The satellite maps disagree here. A pixel 10–30 m across can mix grass with pavement; the photos around you show what is actually on the ground."
          : "Satellite pixels are 10–30 m; this site is a 100 m square."}
      </div>
    </div>`;
}

/* How much of this site browned between 2019 and 2022.
 *
 * The headline is the browned share of the site's 100 m footprint, not whether
 * one GPS point landed in a patch. Citizen-science fixes are good to anywhere
 * from 3 m to over 1 km, and the patches are fragmented, so a single point flips
 * with the phone's error while the footprint share barely moves. The range shows
 * how far the answer moves across the recorded GPS error, and the AOI-wide share
 * is the yardstick: 60% browned reads very differently if the whole area is 43%.
 * The single-point result stays as a secondary line with its own confidence. */
function BrowningReadout({ vegetation }) {
  if (!vegetation || !vegetation.available) return null;
  if (!vegetation.in_analysis_area) {
    return html`<div className="veg-row veg-muted">
      Outside the Pukalani browning study area — no vegetation measurement here.
    </div>`;
  }

  const pct = (v) => `${Math.round(v * 100)}%`;
  const f = vegetation.site_browned_fraction;
  const range = vegetation.site_browned_range;
  const aoi = vegetation.aoi_browned_fraction;
  const acc = vegetation.location_accuracy_m;
  // Only quote a range when it says something the single number does not.
  const wide = range && range[1] - range[0] >= 0.05;

  const gps = (() => {
    if (vegetation.inside_browning_patch === null || vegetation.inside_browning_patch === undefined) return null;
    const conf = vegetation.location_confidence;
    const edge = Math.round(vegetation.edge_distance_m);
    if (!vegetation.inside_browning_patch) {
      return `GPS point is outside any mapped patch (${edge} m to the nearest).`;
    }
    const where = `GPS point is inside a ${vegetation.patch_area_ha} ha patch`;
    if (conf === "confident") return `${where}, ${edge} m from its edge.`;
    if (conf === "uncertain") return `${where}, but ±${Math.round(acc)} m of GPS error reaches past its edge (${edge} m) — approximate.`;
    return `${where}; no GPS accuracy was recorded.`;
  })();

  return html`
    <div>
      <div className=${"veg-row " + (f >= 0.25 ? "veg-browned" : "veg-near")}>
        ${pct(f)} of this 100 m site browned
        ${wide ? html`<span className="veg-range"> (${pct(range[0])}–${pct(range[1])} across GPS error)</span>` : null}
      </div>
      <div className="veg-sub">
        dNDVI ${"<"} ${vegetation.threshold}, 2019→2022 · whole study area: ${pct(aoi)}
        ${acc != null ? ` · GPS ±${Math.round(acc)} m` : " · GPS accuracy unknown"}
      </div>
      ${gps ? html`<div className="veg-sub veg-gps">${gps}</div>` : null}
    </div>`;
}

/* AOI-wide NDVI, Dec 2018 - Dec 2023, as a compact sparkline. Marks the Aug 2022
 * drought trough and the Aug 2023 Upcountry fires so the site's photos can be
 * read against the vegetation trend for the same ground. Fetched once and shared
 * by every observation, since the series is AOI-wide rather than per-site. */
function NdviSparkline() {
  const [series, setSeries] = useState(null);
  useEffect(() => {
    fetch("/api/sites/vegetation-series")
      .then((r) => r.json())
      .then((d) => setSeries(d.ndvi || []))
      .catch(() => setSeries([]));
  }, []);
  if (!series || series.length < 2) return null;

  const W = 300, H = 46, PAD = 3;
  const vals = series.map((p) => p.value);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const span = hi - lo || 1;
  const x = (i) => PAD + (i * (W - 2 * PAD)) / (series.length - 1);
  const y = (v) => H - PAD - ((v - lo) / span) * (H - 2 * PAD);
  const points = series.map((p, i) => `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");

  const markAt = (prefix) => series.findIndex((p) => p.date.startsWith(prefix));
  const trough = markAt("2022-08");
  const fire = markAt("2023-08");

  return html`
    <div className="veg-spark">
      <div className="veg-spark-title">Study-area mean NDVI · 2018–2023 (not this exact site)</div>
      <svg viewBox=${`0 0 ${W} ${H}`} width="100%" height=${H} preserveAspectRatio="none">
        <polyline points=${points} fill="none" stroke="#4fb286" strokeWidth="1.5" />
        ${trough >= 0 ? html`<line key="t" x1=${x(trough)} y1="0" x2=${x(trough)} y2=${H}
            stroke="#d9a441" strokeWidth="1" strokeDasharray="2 2" />` : null}
        ${fire >= 0 ? html`<line key="f" x1=${x(fire)} y1="0" x2=${x(fire)} y2=${H}
            stroke="#e0644f" strokeWidth="1" strokeDasharray="2 2" />` : null}
      </svg>
      <div className="veg-spark-key">
        <span className="k-drought">Aug 2022 drought low</span>
        <span className="k-fire">Aug 2023 fires</span>
      </div>
    </div>`;
}

/* Unit view vectors for each direction. The camera sits just off the origin,
 * opposite the way it looks, so facing a direction means placing the camera on
 * the far side of the origin from it. */
const VIEW_DIRS = {
  North: [0, 0, -1], East: [1, 0, 0], South: [0, 0, 1],
  West: [-1, 0, 0], Upward: [0, 1, 0], Downward: [0, -1, 0],
};
/* Lives inside the Canvas to reach the camera and controls. It reports where the
 * viewer is looking, and exposes face() so the HUD buttons can snap to a
 * direction. Heading comes from the controls' own change events rather than a
 * per-frame loop, so it updates exactly when the view does. */
function ViewDriver({ apiRef, onView, onUserStart }) {
  const { camera, controls, invalidate } = useThree();

  useEffect(() => {
    if (!controls) return undefined;
    const report = () => {
      const { heading, pitch } = viewFromControls(
        controls.getAzimuthalAngle(), controls.getPolarAngle()
      );
      onView(heading, pitch);
    };
    controls.addEventListener("change", report);
    // "start" fires only when a person grabs the view (not for auto-rotate or
    // the N/E/S/W jumps), which is exactly when a pan should stop.
    if (onUserStart) controls.addEventListener("start", onUserStart);
    apiRef.current = {
      face(name) {
        const d = VIEW_DIRS[name];
        if (!d) return;
        camera.position.set(...cameraPositionToFace(d));
        controls.update();
        invalidate();
        report();
      },
    };
    report();
    return () => {
      controls.removeEventListener("change", report);
      if (onUserStart) controls.removeEventListener("start", onUserStart);
      apiRef.current = null;
    };
  }, [controls, camera, invalidate, onUserStart]);

  return null;
}

/* Which way you are facing, jump buttons, and the field-of-view toggle. */
function ViewHud({ apiRef, view, missing, trueFov, onToggleFov, spinning, onToggleSpin, onFullscreen }) {
  const { heading, pitch } = view;
  const looking = lookingLabel(heading, pitch);
  const btn = (name, label) => html`
    <button key=${name}
            className=${"hud-btn" + (missing.includes(name) ? " hud-missing" : "")}
            title=${missing.includes(name) ? `${name} — no photo for this direction` : `Look ${name.toLowerCase()}`}
            onClick=${() => apiRef.current && apiRef.current.face(name)}>${label}</button>`;
  return html`
    <div className="viewer-hud">
      <div className="hud-heading">Facing <b>${looking}</b></div>
      <div className="hud-btns">
        ${btn("North", "N")}${btn("East", "E")}${btn("South", "S")}${btn("West", "W")}
        <span className="hud-sep"></span>
        ${btn("Upward", "↑ Sky")}${btn("Downward", "↓ Ground")}
      </div>
      <button className="hud-fov" onClick=${onToggleFov}
              title=${`Draws each photo at the angle it really covers. Assumes a ~${ASSUMED_LONG_SIDE_FOV_DEG}° phone camera (no EXIF available).`}>
        ${trueFov ? "True field of view" : "Fill cube"}
      </button>
      <span className="hud-sep"></span>
      <button className="hud-btn" aria-pressed=${spinning} onClick=${onToggleSpin}
              title="Slowly pan around the site (space). Dragging stops it.">
        ${spinning ? "❚❚ Stop" : "⟳ Look around"}
      </button>
      <button className="hud-btn" onClick=${onFullscreen} title="Full screen (for presenting or recording)">⛶</button>
    </div>`;
}

/* Inset map: where this site is relative to the study area and the 2023 fire
 * perimeters, with a wedge showing which way the viewer is facing. Plain SVG in a
 * flat local projection (accurate to well under 1% over the 8 km shown). Layers
 * are fetched once and shared by every site. */
const MINI = { size: 150, halfKm: 4 };
let miniLayers = null;

function MiniMap({ observation, heading }) {
  const [layers, setLayers] = useState(miniLayers);
  useEffect(() => {
    if (miniLayers) return;
    Promise.all([
      fetch("/api/layers/study-area").then((r) => (r.ok ? r.json() : null)),
      fetch("/api/layers/fires").then((r) => (r.ok ? r.json() : null)),
    ]).then(([sa, fires]) => {
      miniLayers = { sa, fires };
      setLayers(miniLayers);
    }).catch(() => setLayers(false));
  }, []);
  if (!layers || !observation) return null;

  const { size, halfKm } = MINI;
  const lat0 = observation.latitude, lon0 = observation.longitude;
  const kx = 111.32 * Math.cos((lat0 * Math.PI) / 180);
  const px = (lon, lat) => [
    size / 2 + (((lon - lon0) * kx) / halfKm) * (size / 2),
    size / 2 - (((lat - lat0) * 111.32) / halfKm) * (size / 2),
  ];
  const ringPath = (ring) => {
    const step = Math.max(1, Math.floor(ring.length / 300));
    return ring.filter((_, i) => i % step === 0)
      .map((p, i) => `${i ? "L" : "M"}${px(p[0], p[1]).map((v) => v.toFixed(1)).join(",")}`).join(" ") + "Z";
  };
  const fires = (layers.fires?.features || []).filter((f) => f.properties.year === 2023);
  const firePaths = fires.flatMap((f) => {
    const g = f.geometry;
    const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    return polys.map((rings) => ringPath(rings[0]));
  });
  const sa = layers.sa;
  const [sx, sy] = sa ? px(sa.lon, sa.lat) : [0, 0];
  const sr = sa ? ((sa.radius_m / 1000) / halfKm) * (size / 2) : 0;

  // Facing wedge: +/-30 degrees around the heading, 0 = north (up the map).
  const c = size / 2, len = 34, rad = (d) => ((d - 90) * Math.PI) / 180;
  const pt = (d) => `${(c + len * Math.cos(rad(d))).toFixed(1)},${(c + len * Math.sin(rad(d))).toFixed(1)}`;
  const wedge = `M${c},${c} L${pt(heading - 30)} A${len},${len} 0 0 1 ${pt(heading + 30)} Z`;
  const kmBar = (1 / halfKm) * (size / 2);
  const fire = observation.fire && observation.fire.available ? observation.fire : null;
  const label = `Map: this site${fire ? `, ${fire.inside_perimeter ? "inside" : `${fire.distance_km} km from`} the ${fire.nearest_fire} fire perimeter` : ""}, facing ${Math.round(heading)} degrees.`;

  return html`
    <figure className="minimap" aria-label=${label} role="img">
      <svg viewBox=${`0 0 ${size} ${size}`} width=${size} height=${size}>
        <defs><clipPath id="miniclip"><rect width=${size} height=${size} /></clipPath></defs>
        <g clipPath="url(#miniclip)">
          <rect width=${size} height=${size} fill="#16211f" />
          ${firePaths.map((d, i) => html`<path key=${i} d=${d} fill="rgba(229,57,53,0.32)" stroke="#ff5a4f" strokeWidth="1.2" />`)}
          ${sa ? html`<circle cx=${sx} cy=${sy} r=${sr} fill="none" stroke="#e8eff0" strokeWidth="1.2" strokeDasharray="4 3" />` : null}
          <path d=${wedge} fill="rgba(79,178,134,0.45)" stroke="#4fb286" strokeWidth="1" />
          <circle cx=${c} cy=${c} r="4" fill="#4fb286" stroke="#fff" strokeWidth="1.5" />
          <text x=${size - 10} y="16" fill="#e8eff0" fontSize="11" fontWeight="700" textAnchor="middle">N</text>
          <path d=${`M${size - 10},20 L${size - 14},28 L${size - 6},28 Z`} fill="#e8eff0" />
          <line x1="8" x2=${8 + kmBar} y1=${size - 10} y2=${size - 10} stroke="#e8eff0" strokeWidth="2" />
          <text x="8" y=${size - 14} fill="#c9d4d8" fontSize="9">1 km</text>
        </g>
      </svg>
      <figcaption>
        <span className="mk mk-fire"></span>2023 fires
        <span className="mk mk-study"></span>study area
      </figcaption>
    </figure>`;
}

/* Hooks live here, not in CubeMapViewer, so that component can return early for
 * the empty state without breaking the rules of hooks. */
// OrbitControls' auto-rotate speed: 2 = one full turn in ~30 s at 60 fps, slow
// enough to read each photo. Positive sweeps N → E → S → W here (checked in a
// browser: heading rises 0° → 90° → …).
const SPIN_SPEED = 2;

/* Keys that jump to a photo, as on the HUD buttons. */
const KEY_FACES = { n: "North", e: "East", s: "South", w: "West", u: "Upward", d: "Downward" };

function LoadedViewer({ observation }) {
  const apiRef = useRef(null);
  const stageRef = useRef(null);
  const [view, setView] = useState({ heading: 0, pitch: 0 });
  const [trueFov, setTrueFov] = useState(false);
  // A slow automatic pan, for presenting the site (and for screen recordings).
  // Any drag stops it, so it never fights the person holding the mouse.
  const [spinning, setSpinning] = useState(false);
  // Stable identity, so ViewDriver attaches its "start" listener once.
  const stopSpin = useRef(() => setSpinning(false));
  const onView = (heading, pitch) =>
    setView((v) => (v.heading === heading && v.pitch === pitch ? v : { heading, pitch }));

  useEffect(() => {
    const onKey = (e) => {
      const t = e.target;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (t && (t.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(t.tagName))) return;
      const face = KEY_FACES[e.key.toLowerCase()];
      if (face) { setSpinning(false); apiRef.current && apiRef.current.face(face); e.preventDefault(); }
      else if (e.key === " ") { setSpinning((v) => !v); e.preventDefault(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleFullscreen = () => {
    const el = stageRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else if (el.requestFullscreen) el.requestFullscreen();
  };

  return html`
    <div className="viewer-stage" ref=${stageRef}>
      <${Canvas} camera=${{ position: [0, 0, 0.1], fov: 75 }} dpr=${[1, 2]}>
        <${CubeFaces} photos=${observation.photos} trueFov=${trueFov} key=${observation.land_cover_id} />
        <${OrbitControls}
          makeDefault
          enablePan=${false}
          enableZoom=${true}
          minDistance=${0.01}
          maxDistance=${1.2}
          rotateSpeed=${-0.35}
          enableDamping=${true}
          autoRotate=${spinning}
          autoRotateSpeed=${SPIN_SPEED} />
        <${ViewDriver} apiRef=${apiRef} onView=${onView} onUserStart=${stopSpin.current} />
      <//>
      <${HeadingBadge} observation=${observation} />
      <${MiniMap} observation=${observation} heading=${view.heading} />
      <${ViewHud} apiRef=${apiRef} view=${view}
                  missing=${observation.missing_directions || []}
                  trueFov=${trueFov} onToggleFov=${() => setTrueFov((v) => !v)}
                  spinning=${spinning} onToggleSpin=${() => setSpinning((v) => !v)}
                  onFullscreen=${toggleFullscreen} />
      <div className="viewer-hint">drag to look around · scroll to zoom · keys N E S W U D · space to pan</div>
    </div>`;
}

export function CubeMapViewer({ observation }) {
  if (!observation) {
    return html`<div className="viewer-empty">
      Pick an observation to reconstruct its site.
    </div>`;
  }
  return html`<${LoadedViewer} observation=${observation} />`;
}

/* LCMS trajectories for Maui County — independent USFS corroboration of the
 * browning story. Deliberately rendered in the sidebar rather than the per-site
 * badge, because these are COUNTY-WIDE figures: putting them on a site would
 * imply a measurement at that site, which LCMS-via-dashboard cannot support.
 * Per-site LCMS classes need scripts/gee/lcms_site_sample.js. */
export function LcmsPanel() {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch("/api/sites/lcms").then((r) => r.json()).then(setData).catch(() => {});
  }, []);
  if (!data || !data.available) return null;

  const fmt = (n) => n.toLocaleString();
  const delta = (h) => {
    if (h.change_pct_vs_baseline === null) {
      // Baseline of zero acres: report the absolute change instead of a ratio.
      return `${h.change_acres_vs_baseline >= 0 ? "+" : ""}${fmt(h.change_acres_vs_baseline)} ac`;
    }
    const v = h.change_pct_vs_baseline;
    return `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`;
  };

  return html`
    <div className="lcms">
      <div className="lcms-title">LCMS · ${data.summary_area}</div>
      <div className="lcms-sub">
        USDA Forest Service ${data.data_version} · county-wide, not per-site
      </div>
      ${data.highlights.map((h) => {
        const rising = (h.change_pct_vs_baseline ?? h.change_acres_vs_baseline) > 0;
        const concerning = rising && h.section === "Vegetation Change";
        const losing = h.class_name === "Agriculture";
        return html`
          <div className="lcms-row" key=${h.class_name} title=${h.why}>
            <div className="lcms-name">${h.class_name}</div>
            <div className="lcms-vals">
              ${h.points.map((p) => html`
                <span className="lcms-yr" key=${p.year}>
                  <b>${p.year.slice(2)}</b> ${fmt(p.acres)}
                </span>`)}
              <span className=${"lcms-delta" + (concerning || losing ? " bad" : "")}>
                ${delta(h)}
              </span>
            </div>
          </div>`;
      })}
    </div>`;
}

/* Shared fetch path. fetch() only rejects on network failure, so a 4xx/5xx has to
 * be turned into an Error here — and it should carry the API's own `detail`
 * ("GLOBE data unavailable and not cached…") rather than a bare status code,
 * since that message says what to do about it. */
async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = String(res.status);
    try { detail = (await res.json()).detail || detail; } catch (e) { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

export const fetchObservation = (landCoverId) =>
  getJson(`/api/sites/observation/${encodeURIComponent(landCoverId)}`);

export const searchSites = (params) =>
  getJson(`/api/sites/search?${new URLSearchParams(params).toString()}`);

export { html };
