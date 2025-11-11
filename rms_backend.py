import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from typing import List, Optional, Tuple
from datetime import datetime, date
from urllib.parse import quote_plus
from decimal import Decimal

# --- Database Setup (MySQL) ---
DB_USER = "root"
DB_PASSWORD = "Prasanna@9361340677"
DB_HOST = "localhost"
DB_NAME = "rms_db"

DATABASE_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL, echo=True)  # Added echo for debugging
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# --- SQLAlchemy Models ---

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    contact_name = Column(String(100))
    phone = Column(String(50))
    email = Column(String(100))
    address = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    products = relationship("Product", back_populates="supplier")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    unit_price_cents = Column(Integer, nullable=False)
    quantity_available = Column(Integer, default=0)
    reorder_level = Column(Integer, default=10)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    supplier = relationship("Supplier", back_populates="products")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    phone = Column(String(50))
    email = Column(String(100), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now)

    sales = relationship("Sale", back_populates="customer")


class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    subtotal_cents = Column(Integer, nullable=False)
    tax_cents = Column(Integer, nullable=False)
    total_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    customer = relationship("Customer", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_price_cents = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    line_total_cents = Column(Integer, nullable=False)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")


# --- Pydantic Schemas ---

orm_config = ConfigDict(from_attributes=True)


class SupplierBase(BaseModel):
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierSchema(SupplierBase):
    id: int
    created_at: datetime
    model_config = orm_config


class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerSchema(CustomerBase):
    id: int
    created_at: datetime
    model_config = orm_config


class ProductBase(BaseModel):
    name: str
    sku: str
    unit_price_cents: int
    quantity_available: int
    reorder_level: Optional[int] = 10
    supplier_id: Optional[int] = None


class ProductCreate(ProductBase):
    pass


class ProductSchema(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    supplier: Optional[SupplierSchema] = None
    model_config = orm_config


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    unit_price_cents: Optional[int] = None
    quantity_available: Optional[int] = None
    reorder_level: Optional[int] = None
    supplier_id: Optional[int] = None


class SaleItemBase(BaseModel):
    product_id: int
    quantity: int


class SaleItemRead(SaleItemBase):
    unit_price_cents: int
    line_total_cents: int
    model_config = orm_config


class SaleCreate(BaseModel):
    customer_id: Optional[int] = None
    items: List[SaleItemBase]


class SaleRead(BaseModel):
    id: int
    customer_id: Optional[int] = None
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    created_at: datetime
    items: List[SaleItemRead]
    customer: Optional[CustomerSchema] = None
    model_config = orm_config


class SalesSummary(BaseModel):
    from_date: date
    to_date: date
    total_revenue_cents: int
    transaction_count: int
    average_order_value_cents: int


# --- Core Service Logic ---

TAX_RATE = 0.08


def create_sale(db: Session, sale_data: SaleCreate) -> Sale:
    products_to_update: List[Tuple[Product, int]] = []
    line_items_data: List[dict] = []
    subtotal_cents = 0

    if not sale_data.items:
        raise HTTPException(status_code=400, detail="Sale must contain at least one item.")

    for item in sale_data.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Item quantity must be positive: Product {item.product_id}")

        product = db.query(Product).filter(Product.id == item.product_id).with_for_update().first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: id {item.product_id}")

        if product.quantity_available < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name} (SKU: {product.sku}). "
                       f"Requested: {item.quantity}, Available: {product.quantity_available}"
            )

        products_to_update.append((product, item.quantity))

        line_total = product.unit_price_cents * item.quantity
        subtotal_cents += line_total

        line_items_data.append({
            "product_id": product.id,
            "unit_price_cents": product.unit_price_cents,
            "quantity": item.quantity,
            "line_total_cents": line_total
        })

    tax_cents = int(subtotal_cents * TAX_RATE)
    total_cents = subtotal_cents + tax_cents

    new_sale = Sale(
        customer_id=sale_data.customer_id,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=total_cents
    )
    db.add(new_sale)
    db.flush()

    for item_data in line_items_data:
        sale_item = SaleItem(sale_id=new_sale.id, **item_data)
        db.add(sale_item)

    for product, quantity_sold in products_to_update:
        product.quantity_available -= quantity_sold
        db.add(product)

    return new_sale


# --- FastAPI App ---

app = FastAPI(title="Retail Management System API", version="1.0")

# CORS Middleware - MUST be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the RMS API. Check out the docs at /docs"}


# --- Product Endpoints ---

@app.post("/api/products", response_model=ProductSchema, status_code=201)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    try:
        db_product = db.query(Product).filter(Product.sku == product.sku).first()
        if db_product:
            raise HTTPException(status_code=400, detail="Product with this SKU already exists")
        new_product = Product(**product.model_dump())
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        return new_product
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating product: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating product: {str(e)}")


@app.get("/api/products", response_model=List[ProductSchema])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        products = db.query(Product).order_by(Product.name).offset(skip).limit(limit).all()
        return products
    except Exception as e:
        print(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching products: {str(e)}")


@app.get("/api/products/{product_id}", response_model=ProductSchema)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.put("/api/products/{product_id}", response_model=ProductSchema)
def update_product(product_id: int, product_update: ProductUpdate, db: Session = Depends(get_db)):
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        update_data = product_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)

        db.commit()
        db.refresh(product)
        return product
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating product: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating product: {str(e)}")


@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        if db.query(SaleItem).filter(SaleItem.product_id == product_id).first():
            raise HTTPException(
                status_code=400,
                detail="Cannot delete product, it is associated with existing sales."
            )

        db.delete(product)
        db.commit()
        return
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting product: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")


# --- Supplier Endpoints ---

@app.post("/api/suppliers", response_model=SupplierSchema, status_code=201)
def create_supplier(supplier: SupplierCreate, db: Session = Depends(get_db)):
    try:
        print(f"Received supplier data: {supplier.model_dump()}")
        new_supplier = Supplier(**supplier.model_dump())
        db.add(new_supplier)
        db.commit()
        db.refresh(new_supplier)
        print(f"Created supplier with ID: {new_supplier.id}")
        return new_supplier
    except Exception as e:
        db.rollback()
        print(f"Error creating supplier: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating supplier: {str(e)}")


@app.get("/api/suppliers", response_model=List[SupplierSchema])
def get_suppliers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        suppliers = db.query(Supplier).order_by(Supplier.name).offset(skip).limit(limit).all()
        return suppliers
    except Exception as e:
        print(f"Error fetching suppliers: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching suppliers: {str(e)}")


# --- Customer Endpoints ---

@app.post("/api/customers", response_model=CustomerSchema, status_code=201)
def create_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    try:
        db_customer = db.query(Customer).filter(Customer.email == customer.email).first()
        if db_customer and customer.email:
            raise HTTPException(status_code=400, detail="Customer with this email already exists")
        new_customer = Customer(**customer.model_dump())
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        return new_customer
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating customer: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating customer: {str(e)}")


@app.get("/api/customers", response_model=List[CustomerSchema])
def get_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        customers = db.query(Customer).order_by(Customer.name).offset(skip).limit(limit).all()
        return customers
    except Exception as e:
        print(f"Error fetching customers: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching customers: {str(e)}")


# --- Sale Endpoints ---

@app.post("/api/sales", response_model=SaleRead, status_code=201)
def create_new_sale(sale_data: SaleCreate, db: Session = Depends(get_db)):
    try:
        new_sale = create_sale(db, sale_data)
        db.commit()
        db.refresh(new_sale)
        return new_sale
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        print(f"Error creating sale: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/api/sales", response_model=List[SaleRead])
def get_sales(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        sales = db.query(Sale).order_by(Sale.created_at.desc()).offset(skip).limit(limit).all()
        return sales
    except Exception as e:
        print(f"Error fetching sales: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching sales: {str(e)}")


# --- Report Endpoints ---

@app.get("/api/reports/sales-summary", response_model=SalesSummary)
def get_sales_summary(
        from_date: date = Query(..., description="Start date in YYYY-MM-DD"),
        to_date: date = Query(..., description="End date in YYYY-MM-DD"),
        db: Session = Depends(get_db)
):
    try:
        from_datetime = datetime.combine(from_date, datetime.min.time())
        to_datetime = datetime.combine(to_date, datetime.max.time())

        summary = db.query(
            func.sum(Sale.total_cents).label("total_revenue_cents"),
            func.count(Sale.id).label("transaction_count")
        ).filter(
            Sale.created_at >= from_datetime,
            Sale.created_at <= to_datetime
        ).first()

        # Handle None, Decimal, and int types
        total_revenue = summary.total_revenue_cents if summary.total_revenue_cents is not None else 0
        tx_count = summary.transaction_count if summary.transaction_count is not None else 0

        # Convert to int - handles Decimal, float, and int
        if isinstance(total_revenue, Decimal):
            total_revenue_int = int(total_revenue)
        else:
            total_revenue_int = int(total_revenue)

        tx_count_int = int(tx_count)

        avg_order_value = (total_revenue_int // tx_count_int) if tx_count_int > 0 else 0

        return SalesSummary(
            from_date=from_date,
            to_date=to_date,
            total_revenue_cents=total_revenue_int,
            transaction_count=tx_count_int,
            average_order_value_cents=avg_order_value
        )
    except Exception as e:
        print(f"Error in sales summary: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating sales summary: {str(e)}")


@app.get("/api/reports/low-stock", response_model=List[ProductSchema])
def get_low_stock_report(
        threshold: Optional[int] = None,
        db: Session = Depends(get_db)
):
    try:
        if threshold is not None:
            query = db.query(Product).filter(Product.quantity_available <= threshold)
        else:
            query = db.query(Product).filter(Product.quantity_available <= Product.reorder_level)

        return query.order_by(Product.quantity_available.asc()).all()
    except Exception as e:
        print(f"Error in low stock report: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating low stock report: {str(e)}")


if __name__ == "__main__":
    try:
        # Create database tables
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully.")
        print("Starting server... Go to http://127.0.0.1:8000")
        print("API docs available at http://127.0.0.1:8000/docs")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback

        traceback.print_exc()