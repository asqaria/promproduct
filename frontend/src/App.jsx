import React, { useEffect, useState } from "react";
import { fetchProducts, fetchCategories, sendCartToAdmin } from "./api";
import ProductCard from "./components/ProductCard";
import Cart from "./components/Cart";
import Admin from "./components/Admin";
import AdminLogin from "./components/AdminLogin";

export default function App() {
  const [currentPage, setCurrentPage] = useState("catalog"); // "catalog" or "admin"
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [grouped, setGrouped] = useState({});
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [cart, setCart] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  // Mobile drawers
  const [catsOpen, setCatsOpen] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);

  // Check admin authentication on mount
  useEffect(() => {
    const adminToken = localStorage.getItem("adminToken");
    if (adminToken === "authenticated") {
      setIsAdminAuthenticated(true);
    }
  }, []);

  // Handle hash-based routing
  useEffect(() => {
    const hash = window.location.hash.slice(1) || "catalog"; // Remove # and default to "catalog"
    setCurrentPage(hash);

    const handleHashChange = () => {
      const newHash = window.location.hash.slice(1) || "catalog";
      setCurrentPage(newHash);
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const navigateTo = (page) => {
    window.location.hash = page;
  };

  const handleAdminLogin = () => {
    setIsAdminAuthenticated(true);
    window.location.hash = "admin";
  };

  const handleAdminLogout = () => {
    localStorage.removeItem("adminToken");
    setIsAdminAuthenticated(false);
    window.location.hash = "catalog";
  };

  useEffect(() => {
    async function load() {
      try {
        const [cats, prods] = await Promise.all([
          fetchCategories(),
          fetchProducts(),
        ]);
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

  // Lock body scroll when any mobile drawer is open
  useEffect(() => {
    const body = document.body;
    if (catsOpen || cartOpen) body.classList.add("no-scroll");
    else body.classList.remove("no-scroll");
    return () => body.classList.remove("no-scroll");
  }, [catsOpen, cartOpen]);

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

  const cartCount = cart.length;
  const cartCountLabel = cartCount > 99 ? "99+" : String(cartCount);

  return (
    <div className="app">
      <header className="app-header">
        <button
          className="icon-btn burger"
          aria-label="Открыть категории"
          aria-expanded={catsOpen}
          aria-controls="drawer-categories"
          onClick={() => {
            setCatsOpen((v) => !v);
            if (cartOpen) setCartOpen(false);
          }}
        >
          <span className="icon-glyph" aria-hidden="true" />
        </button>

        {/* Title centered */}
        <h1 className="app-title">ТОО Батыс Курылыс XXI</h1>

        <div className="header-right">
          {/* Admin/Login link (only show on admin page) */}
          {currentPage === "admin" &&
            (isAdminAuthenticated ? (
              <>
                <button
                  className="nav-link logout-btn"
                  onClick={handleAdminLogout}
                  aria-label="Logout"
                >
                  Logout
                </button>
              </>
            ) : (
              <button
                className="nav-link"
                onClick={() => navigateTo("admin")}
                aria-label="Go to admin"
              >
                🔐 Login
              </button>
            ))}

          {/* Cart icon on the right with count (only show on catalog) */}
          {currentPage === "catalog" && (
            <button
              className="icon-btn cart"
              aria-label={`Открыть корзину. Товаров: ${cartCount}`}
              aria-expanded={cartOpen}
              aria-controls="drawer-cart"
              onClick={() => {
                setCartOpen((v) => !v);
                if (catsOpen) setCatsOpen(false);
              }}
            >
              <span className="icon-glyph" aria-hidden="true" />
              <span className="icon-count" aria-hidden="true">
                <svg
                  className="icon-count-cart"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M7 4h-2l-1 2h-2v2h2l3.6 7.59-1.35 2.41A2 2 0 0 0 9 20h11v-2h-10.42l1.1-2h6.32a2 2 0 0 0 1.79-1.11l3.58-7.16a1 1 0 0 0-.9-1.42H6.63l-.31-.59A2 2 0 0 0 5 4z" />
                </svg>
                {cartCountLabel}
              </span>
            </button>
          )}
        </div>
      </header>

      {(catsOpen || cartOpen) && (
        <div
          className="drawer-backdrop"
          onClick={() => {
            setCatsOpen(false);
            setCartOpen(false);
          }}
        />
      )}

      {/* Mobile categories drawer (only on catalog) */}
      {currentPage === "catalog" && (
        <aside
          id="drawer-categories"
          className={
            catsOpen
              ? "drawer drawer-left open mobile-only"
              : "drawer drawer-left mobile-only"
          }
          role="dialog"
          aria-modal="true"
          aria-label="Категории"
        >
          <div className="category-list">
            <button
              className={
                selectedCategory === null ? "cat-item active" : "cat-item"
              }
              onClick={() => {
                setSelectedCategory(null);
                setCatsOpen(false);
              }}
            >
              Все
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                className={
                  selectedCategory === c.id ? "cat-item active" : "cat-item"
                }
                onClick={() => {
                  setSelectedCategory(c.id);
                  setCatsOpen(false);
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
        </aside>
      )}

      {/* Mobile cart drawer (only on catalog) */}
      {currentPage === "catalog" && (
        <aside
          id="drawer-cart"
          className={
            cartOpen
              ? "drawer drawer-right open mobile-only"
              : "drawer drawer-right mobile-only"
          }
          role="dialog"
          aria-modal="true"
          aria-label="Корзина"
        >
          <Cart
            items={cart}
            onRemove={removeFromCart}
            onSend={async (contact) => {
              await sendToAdmin(contact);
              setCartOpen(false);
            }}
            sending={sending}
          />
        </aside>
      )}

      {currentPage === "admin" ? (
        isAdminAuthenticated ? (
          <Admin onLogout={handleAdminLogout} />
        ) : (
          <AdminLogin onLogin={handleAdminLogin} />
        )
      ) : (
        <main>
          {toast && <div className="toast">{toast}</div>}

          {/* Desktop: sidebar left */}
          <aside className="sidebar">
            <h3>Категории</h3>
            <div className="category-list">
              <button
                className={
                  selectedCategory === null ? "cat-item active" : "cat-item"
                }
                onClick={() => setSelectedCategory(null)}
              >
                Все
              </button>
              {categories.map((c) => (
                <button
                  key={c.id}
                  className={
                    selectedCategory === c.id ? "cat-item active" : "cat-item"
                  }
                  onClick={() => setSelectedCategory(c.id)}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </aside>

          <section className="catalog">
            {error && <div className="error">{error}</div>}
            {Object.values(grouped)
              .filter((g) =>
                selectedCategory === null
                  ? true
                  : g.category.id === selectedCategory,
              )
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

          {/* Desktop inline cart remains */}
          <Cart
            items={cart}
            onRemove={removeFromCart}
            onSend={sendToAdmin}
            sending={sending}
          />
        </main>
      )}
    </div>
  );
}
