import React, { useEffect, useState } from "react";
import { fetchProducts, fetchCategories, sendCartToAdmin } from "./api";
import ProductCard from "./components/ProductCard";
import Cart from "./components/Cart";
import "./styles.css";

export default function App() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [grouped, setGrouped] = useState({});
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [cart, setCart] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [mobileCatsOpen, setMobileCatsOpen] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [cats, prods] = await Promise.all([fetchCategories(), fetchProducts()]);
        console.log("Loaded categories and products", cats, prods);
        setCategories(cats);
        setProducts(prods);
      } catch (e) {
        setError(e.message);
      }
    }
    load();
  }, []);

  useEffect(() => {
    const g = {};
    products.forEach((p) => {
      const cat = p.category ?? { id: 0, name: "Uncategorized" };
      const cid = cat.id ?? 0;
      if (!g[cid]) g[cid] = { category: cat, items: [] };
      g[cid].items.push(p);
    });
    setGrouped(g);
  }, [products]);

  function addToCart(product) {
    setCart((c) => [...c, product]);
  }

  function removeFromCart(idx) {
    setCart((c) => c.filter((_, i) => i !== idx));
  }

  async function sendToAdmin(contact) {
    setSending(true);
    setError(null);
    try {
      const sanitized = cart.map(({ description, pic_url, ...rest }) => rest);
      const res = await sendCartToAdmin(sanitized, contact);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed");
      }
      setCart([]);
      setToast("Запрос успешно отправлен администратору!");
      setTimeout(() => setToast(null), 3500);
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>ТОО Батыс Курылыс XXI</h1>
      </header>

      <main>
        {toast && <div className="toast">{toast}</div>}

        {/* Mobile toolbar for toggling categories */}
        <div className="mobile-toolbar">
          <button
            className="toggle-categories"
            onClick={() => setMobileCatsOpen((v) => !v)}
            aria-expanded={mobileCatsOpen}
            aria-controls="mobile-categories"
          >
            Категории
          </button>
        </div>

        <aside
          id="mobile-categories"
          className={mobileCatsOpen ? "sidebar open" : "sidebar"}
        >
          <h3>Категории</h3>
          <div className="category-list">
            <button
              className={selectedCategory === null ? "cat-item active" : "cat-item"}
              onClick={() => {
                setSelectedCategory(null);
                setMobileCatsOpen(false);
              }}
            >
              Все
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                className={selectedCategory === c.id ? "cat-item active" : "cat-item"}
                onClick={() => {
                  setSelectedCategory(c.id);
                  setMobileCatsOpen(false);
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
        </aside>

        <section className="catalog">
          {error && <div className="error">{error}</div>}
          {Object.values(grouped)
            .filter((g) => (selectedCategory === null ? true : g.category.id === selectedCategory))
            .map((g) => (
              <div key={g.category.id} className="category-block">
                <h2>{g.category.name}</h2>
                <div className="product-grid">
                  {g.items.map((p) => (
                    <ProductCard key={p.id} product={p} onAdd={addToCart} />
                  ))}
                </div>
              </div>
            ))}
        </section>

        <Cart items={cart} onRemove={removeFromCart} onSend={sendToAdmin} sending={sending} />
      </main>
    </div>
  );
}