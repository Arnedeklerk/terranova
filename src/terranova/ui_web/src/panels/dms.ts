/**
 * DMS ↔ Decimal Degrees helpers — TypeScript mirror of the Python pair in
 * src/terranova/ui/dialogs/catalog_search.py.
 *
 * `parseDMS` is deliberately forgiving:
 *     "51.50722"          → 51.50722
 *     "51 30 26 N"        → 51.50722
 *     "51° 30' 26\" N"    → 51.50722
 *     "-51 30 26"         → -51.50722
 *     "51 30.5 N"         → 51.508333  (DDM)
 *     "51,5 N"            → 51.5       (comma decimal)
 */

export function parseDMS(text: string): number {
  if (text == null) throw new Error("empty coordinate");
  let s = text.trim();
  if (!s) throw new Error("empty coordinate");

  // Normalise minus + strip degree / minute / second markers.
  s = s.replace(/[−]/g, "-");
  s = s.replace(/[°º]/g, " ").replace(/['′]/g, " ").replace(/["″]/g, " ");
  s = s.replace(/,/g, ".");

  // Trailing N/S/E/W hemisphere flag.
  let hemi = 1;
  const m = s.match(/([NSEW])\s*$/i);
  if (m) {
    if (m[1].toUpperCase() === "S" || m[1].toUpperCase() === "W") hemi = -1;
    s = s.slice(0, m.index).trim();
  }

  const parts = s.split(/\s+/).filter(Boolean);
  if (!parts.length) throw new Error(`no numbers in ${JSON.stringify(text)}`);
  const nums = parts.map((p) => {
    const v = parseFloat(p);
    if (!Number.isFinite(v)) throw new Error(`can't parse ${JSON.stringify(text)}`);
    return v;
  });

  let deg: number;
  if (nums.length === 1) {
    deg = nums[0];
  } else if (nums.length === 2) {
    deg = Math.abs(nums[0]) + nums[1] / 60;
    if (nums[0] < 0) deg = -deg;
  } else if (nums.length === 3) {
    deg = Math.abs(nums[0]) + nums[1] / 60 + nums[2] / 3600;
    if (nums[0] < 0) deg = -deg;
  } else {
    throw new Error(`too many parts in ${JSON.stringify(text)}: ${nums}`);
  }
  return hemi * deg;
}

export function formatDMS(value: number, isLat: boolean): string {
  const hemi = value >= 0 ? (isLat ? "N" : "E") : isLat ? "S" : "W";
  const abs = Math.abs(value);
  const deg = Math.floor(abs);
  const minutesFull = (abs - deg) * 60;
  const minutes = Math.floor(minutesFull);
  const seconds = (minutesFull - minutes) * 60;
  const mm = String(minutes).padStart(2, "0");
  const ss = seconds.toFixed(2).padStart(5, "0");
  return `${deg}° ${mm}' ${ss}" ${hemi}`;
}
