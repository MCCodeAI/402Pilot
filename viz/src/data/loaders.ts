import type {
  PosteriorSnapshot,
  RoundRecord,
  ScenarioId,
  SummaryFixture,
} from "./types";

/**
 * Typed fetch wrappers for fixtures under `public/data/`.
 *
 * Vite serves files from `public/` at the configured `base` URL; we use
 * `import.meta.env.BASE_URL` so paths work both in `npm run dev` and on
 * GitHub Pages under `/402Pilot/`.
 */

function dataUrl(path: string): string {
  const base = import.meta.env.BASE_URL ?? "/";
  // BASE_URL ends with "/"; path should not start with "/".
  return `${base}data/${path.replace(/^\/+/, "")}`;
}

export async function loadSummary(): Promise<SummaryFixture> {
  const res = await fetch(dataUrl("summary.json"));
  if (!res.ok) throw new Error(`summary.json: ${res.status}`);
  return (await res.json()) as SummaryFixture;
}

/** Parse a JSONL text body into typed records. */
function parseJsonl<T>(text: string): T[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("//"))
    .map((line) => JSON.parse(line) as T);
}

export async function loadPosteriors(
  scenario: ScenarioId,
  seed: number
): Promise<PosteriorSnapshot[]> {
  const res = await fetch(
    dataUrl(`posteriors/${scenario}_padct_seed${seed}_posteriors.jsonl`)
  );
  if (!res.ok) throw new Error(`posteriors ${scenario} seed ${seed}: ${res.status}`);
  return parseJsonl<PosteriorSnapshot>(await res.text());
}

export async function loadRun(
  scenario: ScenarioId,
  policy: string,
  seed: number
): Promise<RoundRecord[]> {
  const res = await fetch(
    dataUrl(`runs/${scenario}_${policy}_seed${seed}.jsonl`)
  );
  if (!res.ok) throw new Error(`run ${scenario} ${policy} seed ${seed}: ${res.status}`);
  return parseJsonl<RoundRecord>(await res.text());
}
