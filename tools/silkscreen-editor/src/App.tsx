import { useEffect, useState } from "react";
import { fetchCompile, fetchModules, type CompileResponse } from "./api";
import type { SilkItem } from "./model";
import { BoardCanvas } from "./components/BoardCanvas";
import { ItemList } from "./components/ItemList";

export function App() {
  const [modules, setModules] = useState<string[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [result, setResult] = useState<CompileResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetchModules()
      .then((r) => setModules(r.modules ?? []))
      .catch((e) => setError(String(e)));
  }, []);

  const load = (moduleName: string) => {
    setLoading(true);
    setError(null);
    setSelected(null);
    fetchCompile(moduleName)
      .then((r) => {
        if (!r.ok) setError(r.error ?? "compile failed");
        setResult(r);
        setCurrent(moduleName);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  const items: SilkItem[] = result?.items ?? [];

  return (
    <div className="app">
      <header className="topbar">
        <h1>🔧 Bread Modular — Silkscreen Editor</h1>
        <nav className="module-picker">
          {modules.map((m) => (
            <button
              key={m}
              className={`module-btn ${m === current ? "module-btn-active" : ""}`}
              onClick={() => load(m)}
            >
              {m}
            </button>
          ))}
        </nav>
        <div className="status">
          {loading && <span className="spinner">⏳ compiling…</span>}
          {result?.counts && (
            <span>
              {result.counts.silkscreenTexts} texts · {result.counts.refs} refs ·{" "}
              {result.counts.labels} labels · board{" "}
              {result.board?.width}×{result.board?.height}mm
            </span>
          )}
        </div>
      </header>

      {error && <div className="error-banner">⚠ {error}</div>}

      {!current && !loading && (
        <div className="placeholder">
          <p>Pick a module to compile its silkscreen (routing-disabled eval).</p>
        </div>
      )}

      <main className="workspace">
        {result?.svg && result.board && current && (
          <>
            <BoardCanvas
              svg={result.svg}
              board={result.board}
              items={items}
              selected={selected}
              onSelect={setSelected}
            />
            <ItemList items={items} selected={selected} onSelect={setSelected} />
          </>
        )}
      </main>
    </div>
  );
}
