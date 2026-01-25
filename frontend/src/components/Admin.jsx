import React, { useState, useEffect } from "react";
import { fetchProducts } from "../api";
import RichTextEditor from "./RichTextEditor";
import "../styles.css";

export default function Admin({ onLogout }) {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadProducts() {
      try {
        setLoading(true);
        const data = await fetchProducts();
        setProducts(data);
        if (data.length > 0) {
          setSelectedProduct(data[0]);
          setEditForm(JSON.parse(JSON.stringify(data[0])));
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    loadProducts();
  }, []);

  const handleSelectProduct = (product) => {
    setSelectedProduct(product);
    setEditForm(JSON.parse(JSON.stringify(product)));
  };

  const handleFormChange = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (!selectedProduct) return;
    try {
      setSaving(true);
      const API_BASE =
        import.meta.env.VITE_API_BASE ?? "https://prom-products.kz/api";
      const res = await fetch(`${API_BASE}/products/${selectedProduct.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editForm),
      });
      if (!res.ok) throw new Error("Failed to save product");

      // Update local products list
      setProducts((prev) =>
        prev.map((p) => (p.id === selectedProduct.id ? editForm : p)),
      );
      setSelectedProduct(editForm);
      alert("Product saved successfully!");
    } catch (e) {
      setError(e.message);
      alert("Error saving product: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAddNew = () => {
    const newProduct = {
      id: Date.now(),
      name: "New Product",
      description: "",
      pic_url: "",
      category: null,
    };
    setProducts((prev) => [newProduct, ...prev]);
    setSelectedProduct(newProduct);
    setEditForm(newProduct);
  };

  const handleDelete = async () => {
    if (
      !selectedProduct ||
      !confirm("Are you sure you want to delete this product?")
    )
      return;
    try {
      setSaving(true);
      const API_BASE =
        import.meta.env.VITE_API_BASE ?? "https://prom-products.kz/api";
      const res = await fetch(`${API_BASE}/products/${selectedProduct.id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete product");

      setProducts((prev) => prev.filter((p) => p.id !== selectedProduct.id));
      setSelectedProduct(null);
      setEditForm({});
      alert("Product deleted successfully!");
    } catch (e) {
      setError(e.message);
      alert("Error deleting product: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading)
    return (
      <div className="admin-container">
        <p>Loading...</p>
      </div>
    );
  if (error)
    return (
      <div className="admin-container error">
        <p>Error: {error}</p>
      </div>
    );

  return (
    <div className="admin-container">
      <div className="admin-sidebar">
        <div className="admin-header-actions">
          <h2>Products</h2>
          <button className="btn-back" onClick={onLogout}>
            ← Back to Shop
          </button>
        </div>
        <button className="btn-primary" onClick={handleAddNew}>
          + Add New Product
        </button>
        <div className="products-list">
          {products.map((product) => (
            <div
              key={product.id}
              className={`product-list-item ${selectedProduct?.id === product.id ? "active" : ""}`}
              onClick={() => handleSelectProduct(product)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSelectProduct(product);
              }}
            >
              <div className="product-name">{product.name}</div>
              {product.pic_url && (
                <img
                  src={product.pic_url}
                  alt={product.name}
                  className="product-thumb"
                />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="admin-editor">
        {selectedProduct ? (
          <>
            <h2>Edit Product</h2>
            <div className="form-group">
              <label>Product Name</label>
              <input
                type="text"
                value={editForm.name || ""}
                onChange={(e) => handleFormChange("name", e.target.value)}
                placeholder="Product name"
              />
            </div>

            <div className="form-group">
              <label>Image URL</label>
              <input
                type="text"
                value={editForm.pic_url || ""}
                onChange={(e) => handleFormChange("pic_url", e.target.value)}
                placeholder="Image URL"
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <RichTextEditor
                value={editForm.description || ""}
                onChange={(html) => handleFormChange("description", html)}
              />
            </div>

            <div className="form-group">
              <label>Category ID</label>
              <input
                type="number"
                value={editForm.category?.id || ""}
                onChange={(e) =>
                  handleFormChange("category", {
                    id: parseInt(e.target.value),
                    name: editForm.category?.name || "",
                  })
                }
                placeholder="Category ID"
              />
            </div>

            <div className="admin-actions">
              <button
                className="btn-save"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
              <button
                className="btn-delete"
                onClick={handleDelete}
                disabled={saving}
              >
                {saving ? "Deleting..." : "Delete Product"}
              </button>
            </div>
          </>
        ) : (
          <div className="no-selection">No product selected</div>
        )}
      </div>
    </div>
  );
}
