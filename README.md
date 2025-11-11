# Retail Management System (RMS) Showcase

This is a complete, local-only Retail Management System (RMS) built as a showcase project. It features a modern Python backend (FastAPI) and a lightweight, single-file vanilla JavaScript frontend.

The system is designed to demonstrate a full end-to-end workflow, including:
* Managing master data (Products, Suppliers, Customers)
* Recording sales with transactional integrity
* Atomic inventory updates
* Real-time reporting

## Features

* **Login:** A simple, hard-coded admin login screen (`admin` / `pass`) to protect the application.
* **Dashboard:** At-a-glance view of "Today's Sales" and "Low Stock Items."
* **Product Management:** Full CRUD (Create, Read, Update, Delete) for products, including SKU, price, and stock levels.
* **Supplier & Customer Management:** Full CRUD for suppliers and customers.
* **New Sale:** A point-of-sale (POS) interface to add products to a cart, calculate totals (subtotal, tax, total), and complete the sale.
* **Transactional Sales:** When a sale is completed, the system *atomically* updates product inventory. A sale will fail if stock is insufficient, ensuring data integrity.
* **Reports:**
  * **Sales Summary:** View total revenue, transaction count, and average order value over a custom date range.
  * **Low Stock Report:** See all products that are at or below their pre-defined reorder level.

## Tech Stack

* **Backend:** **Python 3** with **FastAPI**
* **Database:** **MySQL**
* **ORM:** **SQLAlchemy**
* **Data Validation:** **Pydantic** (natively included in FastAPI)
* **Frontend:** **Vanilla HTML5, CSS3, and JavaScript (ES6+ Modules)**
* **Styling:** **Tailwind CSS** (via CDN for simplicity)
* **Production Server (for hosting):** **Gunicorn** & **Uvicorn**

## Local Setup & Run Instructions

Follow these steps to run the project on your local machine.

### 1. Prerequisites
* **Python 3.10+**
* A running **MySQL** server (e.g., MySQL Community Server, XAMPP, WAMP)

### 2. Setup the Database
You must create the database in MySQL *before* running the backend.
```sql
CREATE DATABASE rms_db;
```

### 3. Setup the Backend
1. **Clone the repository** (or download the files into a folder).
2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```
3. **Activate the environment:**
   * **Windows:** `venv\Scripts\activate`
   * **macOS/Linux:** `source venv/bin/activate`
4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
5. **Configure Database Connection:**
   Open `rms_backend.py` and edit these lines with your MySQL username and password:
   ```python
   DB_USER = "your_mysql_username"
   DB_PASSWORD = "your_mysql_password"
   ```
6. **Run the backend server:**
   ```bash
   python rms_backend.py
   ```
   The server will start on `http://127.0.0.1:8000`. The first time it runs, it will automatically connect to your `rms_db` and create all the tables.

### 4. Run the Frontend
1. Open a **new terminal window** in the same project folder.
2. Run a simple web server for the frontend. (This is necessary to avoid CORS errors).
   ```bash
   python -m http.server 8080
   ```
3. **Important:** In `rms_frontend.html`, make sure the `API_BASE_URL` is set correctly. If you used different ports, you may need to update the `allow_origins` list in `rms_backend.py`.

### 5. Access the Application
* **Application:** Open your browser to `http://localhost:8080/rms_frontend.html`
* **Login:** Use the hard-coded credentials:
  * **Username:** `admin`
  * **Password:** `pass`
* **API Docs:** You can test the backend API directly by visiting `http://127.0.0.1:8000/docs`
