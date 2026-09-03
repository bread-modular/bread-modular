import { groupItems, itemKey, type SilkItem } from "../model";

type Props = {
  items: SilkItem[];
  selected: string | null;
  onSelect(fingerprint: string | null): void;
};

function Row({
  item,
  ordinal,
  selected,
  onSelect,
}: {
  item: SilkItem;
  ordinal: number;
  selected: string | null;
  onSelect(f: string | null): void;
}) {
  const isSel = selected === item.fingerprint;
  return (
    <button
      className={`item-row ${isSel ? "item-row-selected" : ""} ${
        item.readonly ? "item-row-readonly" : ""
      }`}
      onClick={() => onSelect(isSel ? null : item.fingerprint)}
    >
      <span className="item-text">
        {item.readonly && <span title="frame-computed position">🔒 </span>}
        {item.text}
      </span>
      {item.kind === "ref" && <span className="item-ref">{item.ref}</span>}
      <span className="item-pos">
        x {item.x.toFixed(3)}, y {item.y.toFixed(3)}
      </span>
      <span className="item-meta">
        rot {item.rotation}° · {item.anchor} · {item.fontSize}mm · {item.layer}
      </span>
    </button>
  );
}

/**
 * Inventory side panel (M2, read-only): every silkscreen text grouped into
 * Labels / Ref designators with text, ref, position, rotation, anchor, layer.
 */
export function ItemList({ items, selected, onSelect }: Props) {
  const { labels, refs } = groupItems(items);
  return (
    <aside className="item-list">
      <section>
        <h2>Labels <span className="count">{labels.length}</span></h2>
        <div>
          {labels.map((item, i) => (
            <Row key={itemKey(item, i)} item={item} ordinal={i} selected={selected} onSelect={onSelect} />
          ))}
          {labels.length === 0 && <p className="empty">no labels</p>}
        </div>
      </section>
      <section>
        <h2>Ref designators <span className="count">{refs.length}</span></h2>
        <div>
          {refs.map((item, i) => (
            <Row key={itemKey(item, i)} item={item} ordinal={i} selected={selected} onSelect={onSelect} />
          ))}
          {refs.length === 0 && <p className="empty">no ref-linked texts</p>}
        </div>
      </section>
    </aside>
  );
}
