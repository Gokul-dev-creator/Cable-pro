# CablePro - Cable Operator Management Portal

CablePro is a comprehensive web application designed to help cable TV operators and administrators manage their business efficiently. It provides tools for customer management, payment tracking, user role administration, and detailed reporting.

 # Preview 

<img src="https://github.com/Gokul-dev-creator/Cable-pro/blob/main/static/images/preview.gif">

---

## Key Features

*   **Role-Based Access Control**:
    *   **Administrator**: Full access to all data, can manage other users (operators), and view aggregated reports.
    *   **Operator**: Can only access and manage the customers assigned to them.

*   **Customer Management (CRUD)**:
    *   Add, view, edit, and delete customer records.
    *   Search for customers by name, address, phone, or Set-Top Box (STB) number.

*   **Payment Tracking**:
    *   Record new payments for customers with details like payment method and billing period.
    *   View a paginated log of all historical payments.

*   **Dashboard Analytics**:
    *   At-a-glance view of key metrics: total customers, active customers, outstanding payments, and collections for the day.
    *   Admin dashboard includes a breakdown of stats for each operator.

*   **Data Portability**:
    *   **CSV Import/Export**: Operators can bulk-import new customers from a CSV file and export their entire customer list.
    *   **PDF Reports**: Download a formatted PDF of the payments log for any customizable date range.

*   **Reporting**:
    *   Generate reports for outstanding monthly dues.
    *   Generate collection reports for specific date ranges.
    *   All reports are filtered based on the user's role (admins see all, operators see their own).

---

## Tech Stack

*   **Backend**: Python 3, Flask Framework
*   **Database**: PostgreSQL
*   **ORM**: SQLAlchemy (via Flask-SQLAlchemy)
*   **Frontend**: HTML, Jinja2 Templating, Bootstrap 4
*   **PDF Generation**: WeasyPrint
*   **Deployment**: Configured for Serverless deployment on Vercel with a Supabase database.

---

## Local Development Setup

Follow these steps to run the project on your local machine for development or testing.

### Prerequisites
*   Python 3.10+
*   PostgreSQL installed and running.
*   Git for version control.

### Installation Steps

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Create and Activate a Virtual Environment** (Recommended)
    ```bash
    # Create the environment
    python -m venv venv
    # Activate it (on Windows)
    venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Local PostgreSQL Database**
    *   Open the PostgreSQL shell (`psql`).
    *   Run the following SQL commands to create a user and database:
    ```sql
    CREATE DATABASE cablepro_db;
    CREATE USER cablepro_user WITH PASSWORD 'your_secure_password';
    GRANT ALL PRIVILEGES ON DATABASE cablepro_db TO cablepro_user;
    
    -- Connect to the new database before the next command
    \c cablepro_db
    
    -- Grant permission on the public schema (crucial step)
    GRANT ALL ON SCHEMA public TO cablepro_user;
    ```

5.  **Configure Environment Variables**
    *   In the project root, create a file named `.env`.
    *   Add the following lines to it, replacing the password with the one you created above.
    ```
    # .env file
    DATABASE_URL="postgresql://cablepro_user:your_secure_password@localhost/cablepro_db"
    SECRET_KEY="a_very_secret_key_for_local_development"
    ```
    *   To load this file, we need one more dependency. Install it and add it to `requirements.txt`:
    ```bash
    pip install python-dotenv
    pip freeze > requirements.txt
    ```
    *   **Important**: Make sure your `app.py` loads this file. Add these lines near the top of `app.py`:
    ```python
    from dotenv import load_dotenv
    load_dotenv()
    ```
    

6.  **Initialize the Database**
    *   Run the Flask command to create all the tables and the default admin user.
    ```bash
    flask init-db
    ```

7.  **Run the Application**
    ```bash
    flask run
    ```
    The application will be available at `http://127.0.0.1:5000`. You can log in with `address@app-py-code.com` and password `admin`.
# Cable-pro
