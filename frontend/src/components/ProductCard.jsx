import React from "react";

export default function ProductCard({ product, onAdd, onClick }) {
  return (
    <div
      className="card"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" && onClick) onClick();
      }}
    >
      {product.pic_url && (
        <img
          src={product.pic_url}
          alt={product.name}
          className="product-image"
        />
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
  );
}
