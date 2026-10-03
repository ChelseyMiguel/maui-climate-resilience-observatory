/* Pure view maths for the cube-map viewer: no imports, so it can be unit-tested
 * with plain `node --test` and no bundler.
 *
 * Conventions (matching the scene in cubemap-viewer.mjs): the camera sits just
 * off the origin, OPPOSITE the way it looks. North is -Z, East is +X, Up is +Y.
 */

export const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export function compassName(heading) {
  return COMPASS[Math.round(((heading % 360) + 360) % 360 / 45) % 8];
}

/* OrbitControls reports where the CAMERA is (azimuth around Y, polar angle from
 * +Y). The viewer looks the other way, so:
 *   heading: degrees clockwise from north, 0..359
 *   pitch:   view elevation in degrees, POSITIVE = looking up
 * A camera below the origin (polar angle > 90 degrees) is therefore looking UP. */
export function viewFromControls(azimuthRad, polarRad) {
  const heading = (((-azimuthRad * 180) / Math.PI) % 360 + 360) % 360;
  const pitch = ((polarRad - Math.PI / 2) * 180) / Math.PI;
  return { heading: Math.round(heading), pitch: Math.round(pitch) };
}

/* Text for the HUD: a compass heading, or Up/Down when looking steeply. */
export function lookingLabel(heading, pitch) {
  if (pitch >= 60) return "Up";
  if (pitch <= -60) return "Down";
  return `${compassName(heading)} ${heading}°`;
}

/* Camera position that makes the viewer face `dir` (a view direction vector).
 * On a pole the spherical coordinates degenerate, so nudge off it slightly. */
export function cameraPositionToFace(dir, radius = 0.1) {
  const onPole = dir[0] === 0 && dir[2] === 0;
  const eps = onPole ? 0.002 : 0;
  return [-dir[0] * radius + eps, -dir[1] * radius, -dir[2] * radius + eps];
}

/* Inverse of the two functions above, for round-trip checks: where does a camera
 * at `pos` look? Returns the same {heading, pitch}. */
export function viewFromCameraPosition(pos) {
  const [x, y, z] = pos;
  const r = Math.hypot(x, y, z);
  const azimuth = Math.atan2(x, z);
  const polar = Math.acos(y / r);
  return viewFromControls(azimuth, polar);
}
