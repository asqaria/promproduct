from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db import engine, get_db
from models_db import Category, Product, Request as RequestModel
from schemas import CategorySchema, ProductSchema, ProductCreate, ProductUpdate, AdminRequest
import json
from schemas import RequestSchema

import os
import asyncio
import aiosmtplib
from email.message import EmailMessage
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# allow requests from your dev frontend (Vite)
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello"}


# new endpoint: list all categories from DB
@app.get("/categories", response_model=list[CategorySchema])
async def read_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category))
    categories = result.scalars().all()
    return categories


# GET all products
@app.get("/products", response_model=list[ProductSchema])
async def read_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).options(selectinload(Product.category)))
    products = result.scalars().all()
    return products


# GET single product by id
@app.get("/products/{product_id}", response_model=ProductSchema)
async def read_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product).where(Product.id == product_id).options(selectinload(Product.category))
    )
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


# GET products by category id
@app.get("/category/{cat_id}/", response_model=list[ProductSchema])
async def read_products_by_category(cat_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product).where(Product.category_id == cat_id).options(selectinload(Product.category))
    )
    products = result.scalars().all()
    return products


# POST create product
@app.post("/products", response_model=ProductSchema, status_code=201)
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db)):
    new_product = Product(**payload.dict())
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)

    # ensure relationship is loaded so response serialization doesn't trigger a lazy load
    if new_product.category_id:
        result = await db.execute(select(Category).where(Category.id == new_product.category_id))
        new_product.category = result.scalars().first()

    return new_product


# UPDATE product by id
@app.put("/products/{product_id}", response_model=ProductSchema)
async def update_product(product_id: int, payload: ProductUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id).options(selectinload(Product.category)))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.add(product)
    await db.commit()
    await db.refresh(product)

    # reload/attach category if needed to avoid lazy-load during response serialization
    if product.category_id:
        result = await db.execute(select(Category).where(Category.id == product.category_id))
        product.category = result.scalars().first()

    return product


# Endpoint to receive admin requests (cart + contact) and store in DB
@app.post("/admin/request", status_code=201)
async def receive_admin_request(payload: AdminRequest, db: AsyncSession = Depends(get_db)):
    items_data = [it.dict() if hasattr(it, "dict") else it for it in payload.items]
    product_list_json = json.dumps(items_data, ensure_ascii=False)

    new_req = RequestModel(
        customer_name=payload.contact.name,
        customer_phone=payload.contact.phone,
        product_list=product_list_json,
    )
    db.add(new_req)
    await db.commit()
    await db.refresh(new_req)

    async def send_admin_email(req_id: int, contact: dict, items_json: str):
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", "0"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        admin_email = os.environ.get("ADMIN_EMAIL", "BATYSKURYLYSXXI@gmail.com")
        from_email = os.environ.get("FROM_EMAIL", smtp_user or "BATYSKURYLYSXXI@gmail.com")

        if not smtp_host or not smtp_port or not admin_email:
            print("SMTP not configured; skipping email send")
            return

        try:
            items = json.loads(items_json)
        except Exception:
            items = []

        subject = f"New request #{req_id} from {contact.get('name')}"
        lines = [f"Request ID: {req_id}", f"Customer: {contact.get('name')}", f"Phone: {contact.get('phone')}", "", "Items:"]
        for it in items:
            lines.append(f"- {it.get('name')} (id={it.get('id')}) price={it.get('price')}")

        body = "\n".join(lines)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = admin_email
        msg.set_content(body)

        use_tls = smtp_port == 465
        try:
            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, timeout=30, use_tls=use_tls)
            await smtp.connect()
            if not use_tls:
                try:
                    await smtp.starttls()
                except Exception:
                    pass
            if smtp_user and smtp_pass:
                try:
                    await smtp.login(smtp_user, smtp_pass)
                except Exception:
                    pass
            await smtp.send_message(msg)
            try:
                await smtp.quit()
            except Exception:
                pass
        except Exception as exc:
            print("Failed sending admin email (async):", exc)

    # schedule async send without blocking response
    try:
        asyncio.get_running_loop()
        asyncio.create_task(send_admin_email(new_req.id, {"name": payload.contact.name, "phone": payload.contact.phone}, product_list_json))
    except RuntimeError:
        # no running loop (unlikely under uvicorn), run synchronously
        try:
            asyncio.run(send_admin_email(new_req.id, {"name": payload.contact.name, "phone": payload.contact.phone}, product_list_json))
        except Exception:
            pass

    return {"status": "ok", "id": new_req.id}


@app.get("/admin/requests", response_model=list[RequestSchema])
async def list_admin_requests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RequestModel))
    rows = result.scalars().all()
    out = []
    for r in rows:
        try:
            items = json.loads(r.product_list)
        except Exception:
            items = []
        out.append({
            "id": r.id,
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
            "product_list": items,
        })
    return out


@app.get("/admin/requests/{request_id}", response_model=RequestSchema)
async def get_admin_request(request_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RequestModel).where(RequestModel.id == request_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    try:
        items = json.loads(r.product_list)
    except Exception:
        items = []
    return {
        "id": r.id,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "product_list": items,
    }
