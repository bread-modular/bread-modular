/**
 * API client (browser side) — mirrors server/api.ts.
 */
import type { SilkItem } from "./model";

export type CompileResponse = {
  ok: boolean;
  error?: string;
  module?: string;
  entry?: string;
  /** absolute path of the .circuit.tsx — shown before write-back */
  sourcePath?: string;
  /** source mtime at compile time; echoed on /api/apply as a stale guard */
  entryMtimeMs?: number;
  board?: { width: number; height: number; center: { x: number; y: number } };
  items?: SilkItem[];
  counts?: {
    silkscreenTexts: number;
    refs: number;
    labels: number;
    keptElements: number;
    droppedElements: number;
  };
  svg?: string;
};

/** One write-back edit — mirrors server/patch.ts SilkEdit. */
export type ApplyEdit = {
  fingerprint: string;
  ordinal: number;
  kind: "label" | "ref";
  ref?: string;
  text: string;
  x: number;
  y: number;
  layer: string;
  ops: {
    x?: number;
    y?: number;
    text?: string;
    hidden?: boolean;
    rotation?: number;
    anchor?: string;
    fontSize?: number;
  };
  componentCenter?: { x: number; y: number };
  componentRotation?: number;
};

export type ApplyVerification = {
  fingerprint: string;
  ok: boolean;
  detail: string;
  change?: string;
  newText?: string;
  newX?: number;
  newY?: number;
  newFingerprint?: string;
};

export type ApplyResponse = {
  ok: boolean;
  error?: string;
  module?: string;
  sourcePath?: string;
  entryMtimeMs?: number;
  /** context-free line diff old → new (as written to disk) */
  diff?: string[];
  outcomes?: { fingerprint: string; ok: boolean; reason?: string; change?: string }[];
  verifications?: ApplyVerification[];
  unpatched?: { fingerprint: string; reason?: string }[];
  rolledBack?: boolean;
  stale?: boolean;
  // fresh compile payload (present on success):
  items?: SilkItem[];
  counts?: CompileResponse["counts"];
  board?: CompileResponse["board"];
  svg?: string;
  frameLabels?: unknown;
};

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  return (await res.json()) as T;
}

export function fetchModules(): Promise<{ ok: boolean; modules: string[] }> {
  return getJson("/api/modules");
}

export function fetchCompile(moduleName: string): Promise<CompileResponse> {
  return getJson(`/api/compile?module=${encodeURIComponent(moduleName)}`);
}

export function fetchInventory(moduleName: string): Promise<CompileResponse> {
  return getJson(`/api/inventory?module=${encodeURIComponent(moduleName)}`);
}

export async function applyEdits(
  moduleName: string,
  expectedEntryMtimeMs: number | undefined,
  edits: ApplyEdit[],
): Promise<ApplyResponse> {
  const res = await fetch("/api/apply", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      module: moduleName,
      expectedEntryMtimeMs,
      edits,
    }),
  });
  return (await res.json()) as ApplyResponse;
}
