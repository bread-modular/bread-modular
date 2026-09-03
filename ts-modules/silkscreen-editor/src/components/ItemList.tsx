import { itemKey, type SilkItem } from "../model";

type Props = {
  items: SilkItem[];
  selected: string | null;
  onSelect(fingerprint: string | null): void;
  onToggleHidden(fingerprint: string): void;
  onReset(fingerprint: string): void;
};

function ownerLabel(item: SilkItem): string {
  if (item.owner?.kind === "rv09") return `pot ${item.owner.pot}`;
  return item.owner?.kind ?? item.kind;
}

function Row({
  item,
  ordinal,
  selected,
  onSelect,
  onToggleHidden,
  onReset,
}: {
  item: SilkItem;
  ordinal: number;
  selected: string | null;
  onSelect(f: string | null): void;
  onToggleHidden(f: string): void;
  onReset(f: string): void;
}) {
  const isSel = selected === item.fingerprint;

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
      data-testid={`silk-row-${item.text}`}
      onClick={() => onSelect(isSel ? null : item.fingerprint)}
    >
      <div className="item-row-main">
        <button
          className={`icon-btn eye-btn ${item.readonly ? "icon-btn-disabled" : ""}`}
          title={
            item.readonly
              ? "lib/frame-owned item — cannot hide"
              : item.hidden
                ? "Show (removes hide on Save)"
                : "Hide (writes hide on Save)"
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
          <span
            title={
              item.readonly
                ? "lib/frame-owned label — not editable here"
                : "click to select on the board"
            }
          >
            {item.text}
          </span>
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
        {ownerLabel(item)} · {item.layer}
        {item.readonly ? " · ghost" : ""}
      </span>
    </div>
  );
}

/**
 * Inventory side panel: every silkscreen text grouped by editability —
 * editable items first (drag on the board or hide here), lib/frame-owned
 * ghosts below. Per-item hide/show, dirty markers and per-item reset.
 */
export function ItemList({
  items,
  selected,
  onSelect,
  onToggleHidden,
  onReset,
}: Props) {
  const editable = items.filter((i) => !i.readonly);
  const ghosts = items.filter((i) => i.readonly);
  const renderRow = (item: SilkItem, i: number) => (
    <Row
      key={itemKey(item, i)}
      item={item}
      ordinal={i}
      selected={selected}
      onSelect={onSelect}
      onToggleHidden={onToggleHidden}
      onReset={onReset}
    />
  );
  return (
    <aside className="item-list">
      <section>
        <h2>
          Editable <span className="count">{editable.length}</span>
        </h2>
        <div>{editable.map(renderRow)}</div>
        {editable.length === 0 && <p className="empty">no editable items</p>}
      </section>
      <section>
        <h2>
          Ghosts (lib/frame-owned) <span className="count">{ghosts.length}</span>
        </h2>
        <div>{ghosts.map(renderRow)}</div>
        {ghosts.length === 0 && <p className="empty">no ghosts</p>}
      </section>
    </aside>
  );
}
