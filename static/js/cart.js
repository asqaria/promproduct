(function () {
  "use strict";

  var STORAGE_KEY = "quote_cart";
  var MAX_QTY = 999;
  var MAX_ITEMS = 50;
  var toastTimer = null;

  function isValidItem(item) {
    return item && Number.isInteger(item.id) && Number.isInteger(item.qty) && typeof item.name === "string";
  }

  function readCart() {
    try {
      var data = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(data) ? data.filter(isValidItem) : [];
    } catch (error) {
      return [];
    }
  }

  function writeCart(items) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      // Приватный режим или переполнение хранилища: корзина не сохранится между страницами.
    }
    render();
  }

  function clampQty(value) {
    var qty = parseInt(value, 10);
    if (isNaN(qty) || qty < 1) return 1;
    return Math.min(qty, MAX_QTY);
  }

  function safePath(url) {
    return typeof url === "string" && url.charAt(0) === "/" && url.charAt(1) !== "/" ? url : "";
  }

  function addItem(product, qty) {
    var items = readCart();
    var existing = items.find(function (item) { return item.id === product.id; });
    if (existing) {
      existing.qty = clampQty(existing.qty + qty);
    } else {
      if (items.length >= MAX_ITEMS) {
        showToast("В запросе уже " + MAX_ITEMS + " позиций — отправьте его или удалите лишнее.", false);
        return;
      }
      items.push({ id: product.id, name: product.name, url: product.url, thumb: product.thumb, qty: clampQty(qty) });
    }
    writeCart(items);
    showToast("Добавлено в запрос.", true);
  }

  function setQty(id, qty) {
    var items = readCart();
    items.forEach(function (item) {
      if (item.id === id) item.qty = clampQty(qty);
    });
    writeCart(items);
  }

  function removeItem(id) {
    writeCart(readCart().filter(function (item) { return item.id !== id; }));
  }

  function showToast(message, withLink) {
    var toast = document.querySelector(".toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      toast.setAttribute("role", "status");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    if (withLink) {
      var link = document.createElement("a");
      link.href = "#quote-panel";
      link.textContent = "К запросу";
      toast.appendChild(link);
    }
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { toast.hidden = true; }, 3500);
  }

  function renderItem(item) {
    var li = document.createElement("li");
    li.className = "quote-item";

    var name = document.createElement("a");
    name.className = "quote-item__name";
    name.href = safePath(item.url) || "#";
    name.textContent = item.name;
    li.appendChild(name);

    var row = document.createElement("div");
    row.className = "quote-item__row";

    var qtyWrap = document.createElement("div");
    qtyWrap.className = "qty";
    var input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = String(MAX_QTY);
    input.value = String(item.qty);
    input.setAttribute("aria-label", "Количество: " + item.name);
    input.addEventListener("change", function () { setQty(item.id, input.value); });
    qtyWrap.appendChild(input);
    row.appendChild(qtyWrap);

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "quote-item__remove";
    remove.setAttribute("aria-label", "Удалить из запроса: " + item.name);
    remove.textContent = "×";
    remove.addEventListener("click", function () { removeItem(item.id); });
    row.appendChild(remove);

    li.appendChild(row);
    return li;
  }

  function render() {
    var items = readCart();
    var count = items.length;

    document.querySelectorAll("[data-cart-count]").forEach(function (badge) {
      badge.textContent = String(count);
      badge.hidden = count === 0;
    });

    var list = document.querySelector("[data-quote-list]");
    if (!list) return;
    list.replaceChildren.apply(list, items.map(renderItem));

    var empty = document.querySelector("[data-quote-empty]");
    if (empty) empty.hidden = count > 0;

    var field = document.querySelector('[data-quote-form] [name="items"]');
    if (field) {
      field.value = JSON.stringify(items.map(function (item) { return { id: item.id, qty: item.qty }; }));
    }

    var submit = document.querySelector("[data-quote-submit]");
    if (submit) submit.disabled = count === 0;
  }

  function drawerParts() {
    var toggle = document.querySelector("[data-drawer-toggle]");
    var menu = toggle ? document.getElementById(toggle.getAttribute("aria-controls")) : null;
    var backdrop = document.querySelector("[data-drawer-backdrop]");
    return { toggle: toggle, menu: menu, backdrop: backdrop };
  }

  function setDrawer(open, returnFocus) {
    var parts = drawerParts();
    if (!parts.toggle || !parts.menu) return;
    parts.menu.classList.toggle("sidebar--open", open);
    parts.toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (parts.backdrop) parts.backdrop.hidden = !open;
    if (open) {
      var firstLink = parts.menu.querySelector("a");
      if (firstLink) firstLink.focus();
    } else if (returnFocus) {
      parts.toggle.focus();
    }
  }

  document.addEventListener("click", function (event) {
    var addButton = event.target.closest("[data-add-to-quote]");
    if (addButton) {
      var container = addButton.closest("[data-product]");
      if (!container) return;
      var qtyInput = container.querySelector("[data-qty]");
      addItem(
        {
          id: parseInt(container.dataset.id, 10),
          name: container.dataset.name || "",
          url: container.dataset.url || "",
          thumb: container.dataset.thumb || ""
        },
        clampQty(qtyInput ? qtyInput.value : 1)
      );
      return;
    }

    if (event.target.closest("[data-drawer-toggle]")) {
      var parts = drawerParts();
      setDrawer(!(parts.menu && parts.menu.classList.contains("sidebar--open")), false);
      return;
    }

    if (event.target.closest("[data-drawer-backdrop]")) {
      setDrawer(false, true);
      return;
    }

    var galleryThumb = event.target.closest("[data-gallery-thumb]");
    if (galleryThumb) {
      var main = document.querySelector("[data-gallery-main]");
      if (main && safePath(galleryThumb.dataset.full)) {
        main.src = galleryThumb.dataset.full;
        main.alt = galleryThumb.dataset.alt || "";
      }
      document.querySelectorAll("[data-gallery-thumb]").forEach(function (button) {
        button.setAttribute("aria-current", button === galleryThumb ? "true" : "false");
      });
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var parts = drawerParts();
    if (parts.menu && parts.menu.classList.contains("sidebar--open")) setDrawer(false, true);
  });

  window.addEventListener("storage", function (event) {
    if (event.key === STORAGE_KEY) render();
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (document.querySelector("[data-cart-clear]")) {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch (error) {
        // Хранилище недоступно — очищать нечего.
      }
    }
    var form = document.querySelector("[data-quote-form]");
    if (form) form.addEventListener("submit", render);
    render();
  });
})();
