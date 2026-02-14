import React from "react";
import ProductCard from "./ProductCard";

export default function CategoryDetail({ categoryId, categories, products, onAdd, onBack, onProductClick }) {
  const category = categories.find(c => c.id === categoryId);

  return (
    <section className="catalog">
      <div className="category-detail">
        <button className="back-button" onClick={onBack}>← Назад</button>

        <div className="category-header">
          <h1>{category?.name || "Категория"}</h1>
          <p>{products.length} товаров</p>
        </div>

        {products.length > 0 ? (
          <div className="product-grid">
            {products.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                onAdd={onAdd}
                onClick={() => onProductClick(p.id)}
              />
            ))}
          </div>
        ) : (
          <div className="empty-category">
            <p>В этой категории пока нет товаров.</p>
          </div>
        )}
      </div>
    </section>
  );
}