// Run with:  node --test tests/js/
// No bundler and no dependencies: view-math.mjs has no imports on purpose.
import test from "node:test";
import assert from "node:assert/strict";

import {
  cameraPositionToFace,
  compassName,
  lookingLabel,
  viewFromCameraPosition,
  viewFromControls,
} from "../../app/static/js/view-math.mjs";

const DIRS = {
  North: [0, 0, -1], East: [1, 0, 0], South: [0, 0, 1],
  West: [-1, 0, 0], Upward: [0, 1, 0], Downward: [0, -1, 0],
};

test("compass names cover the circle and wrap", () => {
  assert.equal(compassName(0), "N");
  assert.equal(compassName(90), "E");
  assert.equal(compassName(180), "S");
  assert.equal(compassName(270), "W");
  assert.equal(compassName(359), "N"); // rounds up across the wrap
  assert.equal(compassName(45), "NE");
  assert.equal(compassName(-90), "W");
});

test("facing each horizontal direction reads back as that heading", () => {
  const expected = { North: 0, East: 90, South: 180, West: 270 };
  for (const [name, heading] of Object.entries(expected)) {
    const view = viewFromCameraPosition(cameraPositionToFace(DIRS[name]));
    assert.equal(view.heading, heading, `${name} heading`);
    assert.equal(view.pitch, 0, `${name} should be level`);
  }
});

test("the sky button looks UP and the ground button looks DOWN", () => {
  // Regression: these labels were once inverted ("Sky" read as "Facing Down").
  const up = viewFromCameraPosition(cameraPositionToFace(DIRS.Upward));
  const down = viewFromCameraPosition(cameraPositionToFace(DIRS.Downward));
  assert.ok(up.pitch >= 60, `upward pitch ${up.pitch}`);
  assert.ok(down.pitch <= -60, `downward pitch ${down.pitch}`);
  assert.equal(lookingLabel(up.heading, up.pitch), "Up");
  assert.equal(lookingLabel(down.heading, down.pitch), "Down");
});

test("a camera below the origin is looking up", () => {
  // OrbitControls reports the CAMERA's polar angle; > 90 degrees means below.
  assert.ok(viewFromControls(0, Math.PI * 0.9).pitch > 0);
  assert.ok(viewFromControls(0, Math.PI * 0.1).pitch < 0);
  assert.equal(viewFromControls(0, Math.PI / 2).pitch, 0);
});

test("horizontal labels include the compass name and degrees", () => {
  assert.equal(lookingLabel(90, 0), "E 90°");
  assert.equal(lookingLabel(200, 10), "S 200°");
  assert.equal(lookingLabel(0, 59), "N 0°"); // just under the Up/Down threshold
});

test("pole views are nudged off the exact pole", () => {
  const [x, , z] = cameraPositionToFace(DIRS.Upward);
  assert.ok(x !== 0 && z !== 0, "degenerate on the pole without a nudge");
  const [hx, , hz] = cameraPositionToFace(DIRS.North);
  assert.equal(hx, 0);
  assert.equal(hz, 0.1);
});
