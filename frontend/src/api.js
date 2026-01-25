<<<<<<< HEAD
const API_BASE = import.meta.env.VITE_API_BASE ?? "https://prom-products.kz/api";
=======
const API_BASE =
  import.meta.env.VITE_API_BASE ?? "https://prom-products.kz/api";
>>>>>>> 8fe8eec09b11638d3586ada2d6ea41150914e334

export async function fetchProducts() {
  const res = await fetch(`${API_BASE}/products`);
  if (!res.ok) throw new Error("Failed to load products");
  return res.json();
}

export async function fetchCategories() {
  const res = await fetch(`${API_BASE}/categories`);
  if (!res.ok) throw new Error("Failed to load categories");
  return res.json();
}

export async function sendCartToAdmin(cart, contact = {}) {
  // backend should implement /admin/request to accept this
  const payload = { items: cart, contact };
  const res = await fetch(`${API_BASE}/admin/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res;
}
