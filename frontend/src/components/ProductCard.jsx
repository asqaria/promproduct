import React, { useState } from "react";

export default function ProductCard({ product, onAdd }) {
  const [open, setOpen] = useState(false);

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
          {/* <div className="price">${product.price?.toFixed(2)}</div> */}
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
            <button className="modal-close" onClick={() => setOpen(false)}>×</button>
            {product.pic_url && (
              <img src={product.pic_url} alt={product.name} className="modal-image" />
            )}
            <h2>{product.name}</h2>
            <p>{product.description}</p>
            <div className="modal-footer">
              {/* <div className="price">${product.price?.toFixed(2)}</div> */}
              <button onClick={() => { onAdd(product); setOpen(false); }}>Добавить в корзину</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}