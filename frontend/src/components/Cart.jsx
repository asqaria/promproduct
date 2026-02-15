import React, { useState } from "react";

export default function Cart({ items, onRemove, onSend, sending }) {
  const total = items.reduce((s, it) => s + (it.price || 0), 0);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  const canSend = items.length > 0 && name.trim().length > 1 && phone.trim().length > 5;

  return (
    <aside className="cart">
      <h3>Корзина</h3>
      <div>
        Чтобы узнать цену, добавьте товар в корзину для рассмотрения. Мы с вами
        свяжемся.
      </div>
      <ul>
        {items.map((it, idx) => (
          <li key={idx}>
            {it.name}
            <button
              onClick={() => onRemove(idx)}
              aria-label={`Удалить ${it.name}`}
            >
              x
            </button>
          </li>
        ))}
      </ul>

      <div className="form-row">
        <label>Имя</label>
        <input
          type="text"
          placeholder="Ваше имя"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="form-row">
        <label>Телефон</label>
        <input
          type="tel"
          placeholder="+7 777 305 4243"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
      </div>

      <div className="cart-footer">
        <button
          onClick={() => onSend({ name: name.trim(), phone: phone.trim() })}
          disabled={!canSend || sending}
        >
          {sending ? "Отправляем..." : "Отправить запрос администратору"}
        </button>
      </div>

      <div className="contact-block">
        <h3>Контакты</h3>
        <p>Казахстан, город Астана, улица Керей Жанибек хандар, 50/3</p>
        <div className="contact-phones">
          <a
            href="https://wa.me/77773054243"
            target="_blank"
            rel="noreferrer"
            className="contact-btn whatsapp"
          >
            WhatsApp +7 777 305 4243
          </a>
          <a
            href="https://wa.me/77773773763"
            target="_blank"
            rel="noreferrer"
            className="contact-btn whatsapp"
          >
            WhatsApp +7 777 377 3763
          </a>
        </div>
      </div>

      <div className="contact-block">
  <h3>Прайс-лист</h3>

  <p className="contact-desc">
    Актуальный список товаров и цен в формате Excel
  </p>

  <a
    href="/files/pricelist.xlsx"
    target="_blank"
    rel="noreferrer"
    className="download-btn"
  >
    📥 Скачать прайс-лист
  </a>
</div>
    </aside>
  );
}