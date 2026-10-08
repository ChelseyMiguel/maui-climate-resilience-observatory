/* Map symbols for community-context points. Each kind has its own SHAPE as well
 * as colour, so the legend works for colour-blind readers and in greyscale. Drawn
 * on a canvas at runtime, so no sprite or font server is needed. */
import type { InfrastructureKind } from './types.ts';

export const KIND_LABEL: Record<InfrastructureKind, string> = {
  fire_stations: 'Fire station', ems_stations: 'EMS station', hospitals: 'Hospital',
  public_schools: 'Public school', private_schools: 'Private school',
};

const SIZE = 44; // drawn at 2x for sharpness; displayed at 22 px

export function drawIcon(kind: InfrastructureKind): ImageData {
  const c = document.createElement('canvas');
  c.width = c.height = SIZE;
  const g = c.getContext('2d')!;
  g.lineWidth = 4;
  g.strokeStyle = '#ffffff';
  const s = SIZE, m = s / 2;
  g.beginPath();
  if (kind === 'fire_stations') {             // triangle
    g.moveTo(m, 5); g.lineTo(s - 5, s - 7); g.lineTo(5, s - 7); g.closePath();
    g.fillStyle = '#b3261e'; g.fill(); g.stroke();
  } else if (kind === 'ems_stations') {        // plus sign
    const a = 9, w = 13;
    g.moveTo(m - w / 2, a); g.lineTo(m + w / 2, a); g.lineTo(m + w / 2, m - w / 2); g.lineTo(s - a, m - w / 2);
    g.lineTo(s - a, m + w / 2); g.lineTo(m + w / 2, m + w / 2); g.lineTo(m + w / 2, s - a); g.lineTo(m - w / 2, s - a);
    g.lineTo(m - w / 2, m + w / 2); g.lineTo(a, m + w / 2); g.lineTo(a, m - w / 2); g.lineTo(m - w / 2, m - w / 2);
    g.closePath(); g.fillStyle = '#0b5cad'; g.fill(); g.stroke();
  } else if (kind === 'hospitals') {           // square with H
    g.rect(7, 7, s - 14, s - 14); g.fillStyle = '#0b5cad'; g.fill(); g.stroke();
    g.fillStyle = '#ffffff'; g.font = 'bold 22px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('H', m, m + 1);
  } else if (kind === 'public_schools') {      // filled circle
    g.arc(m, m, 14, 0, Math.PI * 2); g.fillStyle = '#23472f'; g.fill(); g.stroke();
  } else {                                     // private school: ring
    g.arc(m, m, 13, 0, Math.PI * 2); g.fillStyle = '#ffffff'; g.fill();
    g.lineWidth = 6; g.strokeStyle = '#23472f'; g.stroke();
  }
  return g.getImageData(0, 0, s, s);
}

/** Same shapes as inline SVG for the legend. */
export function iconSvg(kind: InfrastructureKind): string {
  switch (kind) {
    case 'fire_stations': return '<polygon points="11,2 20,19 2,19" fill="#b3261e" stroke="#fff" stroke-width="1.5"/>';
    case 'ems_stations': return '<path d="M8 3h6v5h5v6h-5v5H8v-5H3V8h5z" fill="#0b5cad" stroke="#fff" stroke-width="1.2"/>';
    case 'hospitals': return '<rect x="3" y="3" width="16" height="16" fill="#0b5cad"/><text x="11" y="15.5" font-size="11" font-weight="700" fill="#fff" text-anchor="middle" font-family="sans-serif">H</text>';
    case 'public_schools': return '<circle cx="11" cy="11" r="7.5" fill="#23472f" stroke="#fff" stroke-width="1.5"/>';
    default: return '<circle cx="11" cy="11" r="6.5" fill="#fff" stroke="#23472f" stroke-width="3"/>';
  }
}
