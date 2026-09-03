import { useEffect, useRef, useState } from "react";
import { groupItems, itemKey, type SilkItem } from "../model";

type Props = {
  items: SilkItem[];
  selected: string | null;
  onSelect(fingerprint: string | null): void;
  onToggleHidden(fingerprint: string): void;
  onTextEdit(fingerprint: string, text: string): void;
  onReset(fingerprint: string): void;
};

function Row({
  item,
  ordinal,
  selected,
  onSelect,
  onToggleHidden,
  onTextEdit,
  onReset,
}: {
  item: SilkItem;
  ordinal: number;
  selected: string | null;
  onSelect(f: string | null): void;
  onToggleHidden(f: string): void;
  onTextEdit(f: string, text: string): void;
  onReset(f: string): void;
}) {
  const isSel = selected === item.fingerprint;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.text);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      setDraft(item.text);
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing, item.text]);

  const commit = () => {
    const t = draft.trim();
    if (t && t !== item.text) onTextEdit(item.fingerprint, t);
    setEditing(false);
  };

  const moved =
    item.dirty &&
    item.originX !== undefined &&
    item.originY !== undefined &&
    (item.x !== item.originX || item.y !== item.originY);

  return (
    <div
      className={`item-row ${isSel ? "item-row-selected" : ""} ${
        item.readonly ? "item-row-readonly" : ""
      } ${item.hidden ? "item-row-hidden" : ""}`}
      onClick={() => onSelect(isSel ? null : item.fingerprint)}
    >
      <div className="item-row-main">
        <button
          className={`icon-btn eye-btn ${item.readonly ? "icon-btn-disabled" : ""}`}
          title={
            item.readonly
              ? "frame-owned item — cannot hide"
              : item.hidden
                ? "Show (removes visibility=hidden on Apply)"
                : "Hide (writes silkscreenTextVisibility on Apply)"
          }
          disabled={item.readonly}
          onClick={(e) => {
            e.stopPropagation();
            if (!item.readonly) onToggleHidden(item.fingerprint);
          }}
        >
          {item.readonly ? "🔒" : item.hidden ? "🚫" : "👁"}
        </button>

        <span className="item-text">
          {item.dirty && <span className="dirty-star" title="unsaved edit">✳ </span>}
          {editing ? (
            <input
              ref={inputRef}
              className="text-edit"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => {
                if (e.key === "Enter") commit();
                if (e.key === "Escape") setEditing(false);
              }}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span
              onDoubleClick={(e) => {
                e.stopPropagation();
                if (!item.readonly && item.kind === "label") setEditing(true);
              }}
              title={
                item.kind === "ref"
                  ? "ref designator — text is its netlist identity (rename not supported)"
                  : item.readonly
                    ? "frame-owned label — not editable"
                    : "double-click to edit text"
              }
              style={{ cursor: item.readonly || item.kind === "ref" ? "default" : "text" }}
            >
              {item.text}
            </span>
          )}
        </span>

        {item.kind === "ref" && <span className="item-ref">{item.ref}</span>}

        <span className="item-row-actions">
          {item.dirty && (
            <button
              className="icon-btn reset-btn"
              title="reset local edits for this item"
              onClick={(e) => {
                e.stopPropagation();
                onReset(item.fingerprint);
              }}
            >
              ↺
            </button>
          )}
          {!item.readonly && item.kind === "label" && !editing && (
            <button
              className="icon-btn edit-btn"
              title="edit text"
              onClick={(e) => {
                e.stopPropagation();
                setEditing(true);
              }}
            >
              ✏
            </button>
          )}
        </span>
      </div>
      <span className="item-pos">
        {moved ? (
          <>
            <s>
              x {item.originX!.toFixed(3)}, y {item.originY!.toFixed(3)}
            </s>{" "}
            → x {item.x.toFixed(3)}, y {item.y.toFixed(3)}
          </>
        ) : (
          <>
            x {item.x.toFixed(3)}, y {item.y.toFixed(3)}
          </>
        )}
      </span>
      <span className="item-meta">
        rot {item.rotation}° · {item.anchor} · {item.fontSize}mm · {item.layer}
      </span>
    </div>
  );
}

/**
 * Inventory side panel (M2 list + M3 controls): every silkscreen text grouped
 * into Labels / Ref designators, with per-item hide/show, inline text edit
 * (double-click or ✏; labels only — a ref's text is its netlist identity),
 * dirty markers and per-item reset.
 */
export function ItemList({
  items,
  selected,
  onSelect,
  onToggleHidden,
  onTextEdit,
  onReset,
}: Props) {
  const { labels, refs } = groupItems(items);
  const renderRow = (item: SilkItem, i: number) => (
    <Row
      key={itemKey(item, i)}
      item={item}
      ordinal={i}
      selected={selected}
      onSelect={onSelect}
      onToggleHidden={onToggleHidden}
      onTextEdit={onTextEdit}
      onReset={onReset}
    />
  );
  return (
    <aside className="item-list">
      <section>
        <h2>
          Labels <span className="count">{labels.length}</span>
        </h2>
        <div>{labels.map(renderRow)}</div>
        {labels.length === 0 && <p className="empty">no labels</p>}
      </section>
      <section>
        <h2>
          Ref designators <span className="count">{refs.length}</span>
        </h2>
        <div>{refs.map(renderRow)}</div>
        {refs.length === 0 && <p className="empty">no ref-linked texts</p>}
      </section>
    </aside>
  );
}
