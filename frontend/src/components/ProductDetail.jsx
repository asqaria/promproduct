import React from "react";

export default function ProductDetail({ productId, products, onAdd, onBack }) {
  const product = products.find(p => p.id === productId);

  if (!product) {
    return (
      <section className="catalog">
        <div className="product-detail">
          <button className="back-button" onClick={onBack}>← Назад</button>
          <div className="error">Продукт не найден</div>
        </div>
      </section>
    );
  }

  return (
    <section className="catalog">
      <div className="product-detail">
        <button className="back-button" onClick={onBack}>← Назад</button>

        <div className="product-detail-content">
          <div className="product-detail-info">
            <h1>{product.name}</h1>
            <div
              className="product-detail-description"
              dangerouslySetInnerHTML={{ __html: product?.description ?? "" }}
            />
            {/* <div className="price">${product.price?.toFixed(2)}</div> */}
            <button className="add-to-cart-button" onClick={() => onAdd(product)}>
              Добавить в корзину
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}