/**
 * API client (browser side) — mirrors server/api.ts.
 */
import type { SilkItem } from "./model";

export type CompileResponse = {
  ok: boolean;
  error?: string;
  module?: string;
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
