/* CSV export that carries its own provenance. Every file starts with comment lines
 * stating the source, the area and period it covers, and its limitations, so a
 * downloaded table can't drift away from the caveats that belong to it. */

export interface CsvColumn<T> { header: string; value: (row: T) => string | number | null | undefined }

function cell(v: unknown): string {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\n#]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv<T>(rows: T[], columns: CsvColumn<T>[], notes: string[]): string {
  const head = notes.map((n) => `# ${n.replace(/\n/g, ' ')}`);
  const lines = rows.map((r) => columns.map((c) => cell(c.value(r))).join(','));
  return [...head, columns.map((c) => cell(c.header)).join(','), ...lines].join('\n') + '\n';
}

export function downloadCsv(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
