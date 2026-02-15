import React, { useEffect, useState } from "react";
import { fetchProducts, fetchCategories, sendCartToAdmin } from "./api";
import ProductCard from "./components/ProductCard";
import ProductDetail from "./components/ProductDetail";
import CategoryDetail from "./components/CategoryDetail";
import Cart from "./components/Cart";
import Admin from "./components/Admin";
import AdminLogin from "./components/AdminLogin";
import logo from "./img/logo_white.png";

export default function App() {
  const [currentPage, setCurrentPage] = useState("catalog"); // "catalog", "admin", "product", or "category"
  const [currentProductId, setCurrentProductId] = useState(null);
  const [currentCategoryId, setCurrentCategoryId] = useState(null);
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

    if (hash.startsWith("product/")) {
      const productId = parseInt(hash.split("/")[1]);
      setCurrentPage("product");
      setCurrentProductId(productId);
      setCurrentCategoryId(null);
      setSelectedCategory(-1); // Don't highlight any category when viewing product
    } else if (hash.startsWith("category/")) {
      const categoryId = parseInt(hash.split("/")[1]);
      setCurrentPage("category");
      setCurrentCategoryId(categoryId);
      setSelectedCategory(categoryId); // Keep category active in sidebar
      setCurrentProductId(null);
    } else {
      setCurrentPage(hash);
      setCurrentProductId(null);
      setCurrentCategoryId(null);
      setSelectedCategory(null); // Reset category selection for catalog page
    }

    const handleHashChange = () => {
      const newHash = window.location.hash.slice(1) || "catalog";

      if (newHash.startsWith("product/")) {
        const productId = parseInt(newHash.split("/")[1]);
        setCurrentPage("product");
        setCurrentProductId(productId);
        setCurrentCategoryId(null);
        setSelectedCategory(-1); // Don't highlight any category when viewing product
      } else if (newHash.startsWith("category/")) {
        const categoryId = parseInt(newHash.split("/")[1]);
        setCurrentPage("category");
        setCurrentCategoryId(categoryId);
        setSelectedCategory(categoryId); // Keep category active in sidebar
        setCurrentProductId(null);
      } else {
        setCurrentPage(newHash);
        setCurrentProductId(null);
        setCurrentCategoryId(null);
        setSelectedCategory(null); // Reset category selection for catalog page
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  // Scroll to top when route changes
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [currentPage, currentProductId, currentCategoryId]);

  const navigateTo = (page) => {
    window.location.hash = page;
  };

  const navigateToProduct = (productId) => {
    window.location.hash = `product/${productId}`;
  };

  const navigateToCategory = (categoryId) => {
    window.location.hash = `category/${categoryId}`;
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

    // Add uncategorized category if there are products without categories
    if (g[0] && g[0].items.length > 0 && !categories.some((c) => c.id === 0)) {
      setCategories([...categories, { id: 0, name: "Uncategorized" }]);
    }
  }, [products, categories]);

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
        {/* Title centered */}
        <img src={logo} alt="ТОО Батыс Курылыс XXI" className="app-logo" />
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
                  navigateToCategory(c.id);
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
      ) : currentPage === "product" ? (
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
                onClick={() => navigateTo("catalog")}
              >
                Все
              </button>
              {categories.map((c) => (
                <div key={c.id} className="category-group">
                  <button
                    className={
                      selectedCategory === c.id ? "cat-item active" : "cat-item"
                    }
                    onClick={() => navigateToCategory(c.id)}
                  >
                    {c.name}
                  </button>
                  <div className="product-submenu">
                    {grouped[c.id]?.items.map((p) => (
                      <button
                        key={p.id}
                        className={`product-submenu-item ${currentProductId === p.id ? "active" : ""}`}
                        onClick={() => navigateToProduct(p.id)}
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </aside>

          <ProductDetail
            productId={currentProductId}
            products={products}
            onAdd={addToCart}
            onBack={() => navigateTo("catalog")}
          />

          {/* Desktop inline cart remains */}
          <Cart
            items={cart}
            onRemove={removeFromCart}
            onSend={sendToAdmin}
            sending={sending}
          />
        </main>
      ) : currentPage === "category" ? (
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
                onClick={() => navigateTo("catalog")}
              >
                Все
              </button>
              {categories.map((c) => (
                <div key={c.id} className="category-group">
                  <button
                    className={
                      selectedCategory === c.id ? "cat-item active" : "cat-item"
                    }
                    onClick={() => navigateToCategory(c.id)}
                  >
                    {c.name}
                  </button>
                  <div className="product-submenu">
                    {grouped[c.id]?.items.map((p) => (
                      <button
                        key={p.id}
                        className={`product-submenu-item ${currentProductId === p.id ? "active" : ""}`}
                        onClick={() => navigateToProduct(p.id)}
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </aside>

          <CategoryDetail
            categoryId={currentCategoryId}
            categories={categories}
            products={grouped[currentCategoryId]?.items || []}
            onAdd={addToCart}
            onBack={() => navigateTo("catalog")}
            onProductClick={navigateToProduct}
          />

          {/* Desktop inline cart remains */}
          <Cart
            items={cart}
            onRemove={removeFromCart}
            onSend={sendToAdmin}
            sending={sending}
          />
        </main>
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
                <div key={c.id} className="category-group">
                  <button
                    className={
                      selectedCategory === c.id ? "cat-item active" : "cat-item"
                    }
                    onClick={() => navigateToCategory(c.id)}
                  >
                    {c.name}
                  </button>
                  <div className="product-submenu">
                    {grouped[c.id]?.items.map((p) => (
                      <button
                        key={p.id}
                        className={`product-submenu-item ${currentProductId === p.id ? "active" : ""}`}
                        onClick={() => navigateToProduct(p.id)}
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
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
                      <ProductCard
                        key={p.id}
                        product={p}
                        onAdd={addToCart}
                        onClick={() => navigateToProduct(p.id)}
                      />
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
