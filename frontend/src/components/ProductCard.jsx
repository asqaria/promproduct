import React, { useEffect, useState } from "react";

export default function ProductCard({ product, onAdd }) {
  const [open, setOpen] = useState(false);

  // Prevent background scroll when modal is open (mobile)
  useEffect(() => {
    const body = document.body;
    if (open) {
      body.classList.add("no-scroll");
    } else {
      body.classList.remove("no-scroll");
    }
    return () => body.classList.remove("no-scroll");
  }, [open]);

  return (
    <>
      <div
        className="card"
        onClick={() => setOpen(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter") setOpen(true); }}
      >
        {product.pic_url && (
          <img src={product.pic_url} alt={product.name} className="product-image" />
        )}
        <div className="card-header">{product.name}</div>
        <div className="card-body">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAdd(product);
            }}
          >
            Добавить в корзину
          </button>
        </div>
      </div>

      {open && (
        <div className="modal-overlay" onClick={() => setOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setOpen(false)} aria-label="Закрыть">×</button>
            {product.pic_url && (
              <img src={product.pic_url} alt={product.name} className="modal-image" />
            )}
            <h2>{product.name}</h2>
            <div
              className="modal-description"
              dangerouslySetInnerHTML={{ __html: product?.description ?? "" }}
            />
            <div className="modal-footer">
              <button onClick={() => { onAdd(product); setOpen(false); }}>
                Добавить в корзину
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}