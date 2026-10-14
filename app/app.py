from __future__ import annotations

import hmac
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, joinedload, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Restaurant(Base):
    __tablename__ = "restaurants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    cuisine: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    eta: Mapped[str] = mapped_column(String(30), nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    menu: Mapped[list["MenuItem"]] = relationship(back_populates="restaurant", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (UniqueConstraint("restaurant_id", "name", name="uq_menu_restaurant_item"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    emoji: Mapped[str] = mapped_column(String(12), nullable=False, default="🍽️")
    restaurant: Mapped[Restaurant] = relationship(back_populates="menu")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(300), nullable=False)
    restaurant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PLACED")
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="DEMO - NOT CHARGED")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[Order] = relationship(back_populates="items")


def make_database_url() -> str:
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "mealdash")
    user = quote_plus(os.getenv("DB_USER", "mealdash"))
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


engine = create_engine(make_database_url(), pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv("SECRET_KEY", "local-development-only"), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
csrf = CSRFProtect(app)
STATUSES = ["PLACED", "ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"]
NEXT_STATUS = dict(zip(STATUSES, STATUSES[1:]))


def initialize_database() -> None:
    for attempt in range(30):
        try:
            Base.metadata.create_all(engine)
            with SessionLocal.begin() as db:
                rows = [
                        ("curry-leaf", "Curry Leaf Kitchen", "Indian comfort", "Slow-cooked favourites, bright chutneys and warm naan.", "25-35 min", "4.8", [("Butter Paneer Bowl", "Creamy tomato paneer with jeera rice.", 28900, "🍛"), ("Tandoori Chicken Wrap", "Smoky chicken, mint yoghurt and crunchy slaw.", 24900, "🌯"), ("Masala Fries", "Crisp fries dusted with house masala.", 9900, "🍟")]),
                        ("little-oven", "Little Oven Pizzeria", "Wood-fired pizza", "Hand-stretched dough, bubbling cheese, big Sunday energy.", "30-40 min", "4.7", [("Margherita Verde", "San Marzano tomato, basil and mozzarella.", 32900, "🍕"), ("Hot Honey Veg", "Roasted peppers, chilli honey and feta.", 36900, "🌶️"), ("Garlic Knots", "Six soft knots with roasted garlic butter.", 14900, "🥖")]),
                        ("bowl-club", "Bowl Club", "Fresh bowls", "Colourful bowls built fresh for lunch breaks and late nights.", "20-30 min", "4.9", [("Crispy Tofu Bowl", "Sesame tofu, greens, rice and ginger dressing.", 27900, "🥗"), ("Firecracker Chicken", "Sticky chilli chicken with cucumber crunch.", 31900, "🍗"), ("Mango Lassi", "Yoghurt, mango and a little cardamom.", 8900, "🥭")]),
                ]
                for slug, name, cuisine, description, eta, rating, menu in rows:
                    db.execute(mysql_insert(Restaurant).values(slug=slug, name=name, cuisine=cuisine, description=description, eta=eta, rating=rating).prefix_with("IGNORE"))
                    restaurant_id = db.scalar(select(Restaurant.id).where(Restaurant.slug == slug))
                    for item_name, description, price, emoji in menu:
                        db.execute(mysql_insert(MenuItem).values(restaurant_id=restaurant_id, name=item_name, description=description, price_paise=price, emoji=emoji).prefix_with("IGNORE"))
            return
        except OperationalError:
            if attempt == 29:
                raise
            time.sleep(2)


def is_staff() -> bool:
    return session.get("staff_authenticated") is True


def cart_items(db):
    cart = session.get("cart", {}).get("items", {})
    ids = [int(k) for k, qty in cart.items() if str(qty).isdigit() and int(qty) > 0]
    items = db.scalars(select(MenuItem).options(joinedload(MenuItem.restaurant)).where(MenuItem.id.in_(ids))).all() if ids else []
    return [(item, min(int(cart.get(str(item.id), 0)), 20)) for item in items]


@app.context_processor
def common_template_data():
    cart = session.get("cart", {}).get("items", {})
    return {"cart_count": sum(int(q) for q in cart.values() if str(q).isdigit()), "staff_authenticated": is_staff()}


@app.get("/")
def home():
    query = request.args.get("q", "").strip()
    with SessionLocal() as db:
        stmt = select(Restaurant).options(joinedload(Restaurant.menu)).order_by(Restaurant.id)
        restaurants = db.scalars(stmt).unique().all()
    if query:
        q = query.casefold()
        restaurants = [r for r in restaurants if q in r.name.casefold() or q in r.cuisine.casefold() or any(q in m.name.casefold() for m in r.menu)]
    return render_template("home.html", restaurants=restaurants, query=query)


@app.get("/restaurants/<slug>")
def restaurant_page(slug):
    with SessionLocal() as db:
        restaurant = db.scalars(select(Restaurant).options(joinedload(Restaurant.menu)).where(Restaurant.slug == slug)).unique().first()
        if restaurant is None:
            abort(404)
        return render_template("restaurant.html", restaurant=restaurant)


@app.post("/cart/add/<int:item_id>")
def add_to_cart(item_id):
    with SessionLocal() as db:
        item = db.get(MenuItem, item_id)
        if item is None:
            abort(404)
        cart = session.get("cart", {})
        if cart.get("restaurant_id") and int(cart["restaurant_id"]) != item.restaurant_id:
            flash("Your cart has items from another kitchen. Empty it before switching restaurants.", "error")
            return redirect(url_for("cart_page"))
        cart.setdefault("items", {})
        cart["restaurant_id"] = item.restaurant_id
        key = str(item.id)
        cart["items"][key] = min(int(cart["items"].get(key, 0)) + 1, 20)
        session["cart"] = cart
        restaurant_slug = db.get(Restaurant, item.restaurant_id).slug
        item_name = item.name
    flash(f"{item_name} added to your bag.", "success")
    return redirect(url_for("restaurant_page", slug=restaurant_slug))


@app.route("/cart", methods=["GET", "POST"])
def cart_page():
    if request.method == "POST":
        action = request.form.get("action", "")
        item_id = request.form.get("item_id", "")
        cart = session.get("cart", {})
        items = cart.get("items", {})
        if action == "remove" and item_id in items:
            items.pop(item_id, None)
            if not items:
                cart = {}
        elif action == "clear":
            cart = {}
        session["cart"] = {} if action == "clear" else cart
        return redirect(url_for("cart_page"))
    with SessionLocal() as db:
        lines = cart_items(db)
    return render_template("cart.html", lines=lines, subtotal=sum(item.price_paise * qty for item, qty in lines))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    with SessionLocal() as db:
        lines = cart_items(db)
        if not lines:
            flash("Your bag is empty. Pick a few favourites first.", "error")
            return redirect(url_for("home"))
        subtotal = sum(item.price_paise * qty for item, qty in lines)
        if request.method == "GET":
            return render_template("checkout.html", lines=lines, subtotal=subtotal)
        name = " ".join(request.form.get("name", "").split())
        phone = request.form.get("phone", "").strip()
        address = " ".join(request.form.get("address", "").split())
        if not name or len(name) > 120 or len(phone) < 8 or len(phone) > 24 or not address or len(address) > 300:
            flash("Please enter your name, a valid phone number and delivery address.", "error")
            return render_template("checkout.html", lines=lines, subtotal=subtotal), 400
        restaurant_name = lines[0][0].restaurant.name
        order = Order(code="MD-" + secrets.token_hex(5).upper(), customer_name=name, phone=phone, delivery_address=address, restaurant_name=restaurant_name, total_paise=subtotal)
        order.items = [OrderItem(item_name=item.name, quantity=qty, unit_price_paise=item.price_paise) for item, qty in lines]
        db.add(order)
        db.commit()
        session["cart"] = {}
    return redirect(url_for("track_order", code=order.code))


@app.get("/orders/<code>")
def track_order(code):
    with SessionLocal() as db:
        order = db.scalars(select(Order).options(joinedload(Order.items)).where(Order.code == code.upper())).unique().first()
        if order is None:
            abort(404)
        return render_template("order.html", order=order, statuses=STATUSES)


@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if is_staff():
        return redirect(url_for("staff_dashboard"))
    if request.method == "POST":
        expected = os.getenv("STAFF_PASSWORD", "")
        if request.form.get("username") == "staff" and expected and hmac.compare_digest(request.form.get("password", ""), expected):
            session["staff_authenticated"] = True
            return redirect(url_for("staff_dashboard"))
        flash("Those staff credentials did not match.", "error")
    return render_template("staff_login.html")


@app.post("/staff/logout")
def staff_logout():
    session.pop("staff_authenticated", None)
    return redirect(url_for("home"))


@app.route("/staff", methods=["GET", "POST"])
def staff_dashboard():
    if not is_staff():
        return redirect(url_for("staff_login"))
    if request.method == "POST":
        code = request.form.get("code", "")
        with SessionLocal.begin() as db:
            order = db.scalar(select(Order).where(Order.code == code))
            if order and NEXT_STATUS.get(order.status) == request.form.get("status"):
                order.status = request.form["status"]
                flash(f"Order {order.code} moved to {order.status.replace('_', ' ').title()}.", "success")
            else:
                flash("That order status change is not allowed.", "error")
        return redirect(url_for("staff_dashboard"))
    with SessionLocal() as db:
        orders = db.scalars(select(Order).options(joinedload(Order.items)).order_by(Order.created_at.desc()).limit(100)).unique().all()
        count = db.scalar(select(func.count(Order.id))) or 0
        today_count = db.scalar(select(func.count(Order.id)).where(func.date(Order.created_at) == datetime.now(timezone.utc).date())) or 0
        revenue = db.scalar(select(func.coalesce(func.sum(Order.total_paise), 0)).where(Order.status != "DELIVERED")) or 0
    return render_template("staff.html", orders=orders, count=count, today_count=today_count, revenue=revenue, next_status=NEXT_STATUS)


@app.get("/healthz")
def healthz():
    try:
        with engine.connect() as db:
            db.exec_driver_sql("SELECT 1")
        return {"status": "ok", "database": "reachable"}
    except OperationalError:
        return {"status": "unavailable", "database": "unreachable"}, 503


@app.get("/livez")
def livez():
    return {"status": "ok"}


initialize_database()
