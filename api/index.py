import os
from datetime import datetime, date
from calendar import month_name
from functools import wraps
from collections import defaultdict
import io
import csv

from flaSsk import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from weasyprint import HTML, CSS

# --- App and DB Configuration ---g
app = Flask(__name__)
app.config ['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_that_should_be_changed')
# THIS IS THE CORRECT PRODUCTION-READY VERSION
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SUPABASE_DB_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Initialize Extensions ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'danger'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.Text, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    payments = db.relationship('Payment', backref='user', lazy=True)
    customers = db.relationship('Customer', backref='operator', lazy=True)

    @property
    def username(self):
        return self.email

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone_number = db.Column(db.String(15))
    plan_details = db.Column(db.String(100))
    monthly_charge = db.Column(db.Float, nullable=False)
    set_top_box_number = db.Column(db.String(50), unique=True, nullable=False)
    connection_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default='Active')
    notes = db.Column(db.Text)
    payments = db.relationship('Payment', backref='customer', lazy=True, cascade="all, delete-orphan")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    payment_date = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    billing_period_month = db.Column(db.Integer, nullable=False)
    billing_period_year = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default='Cash')
    transaction_reference = db.Column(db.String(100))
    received_by = db.Column(db.String(100)) 

    @property
    def billing_period_display(self):
        return f"{month_name[self.billing_period_month]} {self.billing_period_year}"

# --- Utility Functions & Decorators ---
def get_billing_periods():
    current_year = datetime.now().year
    billing_months = [{'value': i, 'name': month_name[i]} for i in range(1, 13)]
    billing_years = list(range(current_year - 5, current_year + 2))
    return billing_months, billing_years

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('This page is accessible by administrators only.', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Database Initialization Command ---
@app.cli.command("init-db")
def initialize_database():
    """Create database tables and the default admin user."""
    db.create_all()
    print("Database tables created.")
    
    if User.query.filter_by(email='admin@cablepro.com').first():
        print("Admin user already exists.")
    else:
        admin_user = User()
        admin_user.name = 'Default Admin'
        admin_user.email = 'admin@cablepro.com'
        admin_user.address = 'Main Office'
        admin_user.is_admin = True
        admin_user.set_password('admin')
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin created with email 'admin@cablepro.com' and password 'admin'")

# --- Authentication & User Management Routes ---
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            flash(f'Login successful. Welcome, {user.name}!', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_exists = User.query.filter_by(email=request.form.get('email')).first()
        if user_exists:
            flash('An account with this email address already exists.', 'danger')
            return redirect(url_for('register'))
        new_user = User()
        new_user.email = request.form.get('email')
        new_user.name = request.form.get('name')
        new_user.address = request.form.get('address')
        new_user.is_admin = False
        new_user.set_password(request.form.get('password'))
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in with your credentials.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/forgot-password")
def forgot_password():
    return render_template('forgot_password.html')

@app.route("/users")
@login_required
@admin_required
def manage_users():
    users = User.query.order_by(User.name).all()
    return render_template('manage_users.html', users=users)

@app.route("/users/toggle_admin/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user_to_modify = User.query.get_or_404(user_id)
    if user_to_modify.id == current_user.id:
        flash("You cannot change your own admin status.", "danger")
    else:
        user_to_modify.is_admin = not user_to_modify.is_admin
        db.session.commit()
        new_status = "Admin" if user_to_modify.is_admin else "Operator"
        flash(f"User '{user_to_modify.name}' updated to {new_status}.", "success")
    return redirect(url_for('manage_users'))

@app.route("/users/delete/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.id == current_user.id:
        flash("You cannot delete your own account.", 'danger')
    else:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f"User '{user_to_delete.name}' has been deleted.", 'success')
    return redirect(url_for('manage_users'))

# --- Main Application Routes ---
@app.route("/")
@app.route("/index")
@login_required
def index():
    current_month = datetime.now().month
    current_year = datetime.now().year
    search_term_home = request.args.get('search_home', '')
    operator_stats = []
    
    if current_user.is_admin:
        customer_query = Customer.query
        total_customers_count = customer_query.count()
        active_customers_count = customer_query.filter(Customer.status == 'Active').count()
        
        # Admin's "Collections Today" only shows their own collections
        collections_today = db.session.query(db.func.sum(Payment.amount_paid)).filter(
            Payment.payment_date == date.today(),
            Payment.user_id == current_user.id
        ).scalar() or 0.0
        
        paid_customer_ids_this_month = {p.customer_id for p in Payment.query.filter(Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
        outstanding_payments_count = customer_query.filter(Customer.status == 'Active', Customer.id.notin_(paid_customer_ids_this_month)).count()
        
        operators = User.query.order_by(User.name).all()
        for op in operators:
            op_paid_ids = {p.customer_id for p in Payment.query.join(Customer).filter(Customer.operator_id == op.id, Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
            operator_stats.append({
                'name': op.name,
                'total_customers': Customer.query.filter_by(operator_id=op.id).count(),
                'active_customers': Customer.query.filter_by(operator_id=op.id, status='Active').count(),
                'collections_today': db.session.query(db.func.sum(Payment.amount_paid)).join(Customer).filter(Customer.operator_id == op.id, Payment.payment_date == date.today()).scalar() or 0.0,
                'outstanding': Customer.query.filter(Customer.operator_id == op.id, Customer.status == 'Active', Customer.id.notin_(op_paid_ids)).count()
            })
    else: # Operator View
        customer_query = Customer.query.filter_by(operator_id=current_user.id)
        
        # === FIXED: The SAWarning was here ===
        payment_subquery = Payment.query.join(Customer).filter(Customer.operator_id == current_user.id).subquery()
        collections_today = db.session.query(db.func.sum(payment_subquery.c.amount_paid)).filter(payment_subquery.c.payment_date == date.today()).scalar() or 0.0

        total_customers_count = customer_query.count()
        active_customers_count = customer_query.filter(Customer.status == 'Active').count()
        paid_customer_ids_this_month = {p.customer_id for p in Payment.query.join(Customer).filter(Customer.operator_id == current_user.id, Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
        outstanding_payments_count = customer_query.filter(Customer.status == 'Active', Customer.id.notin_(paid_customer_ids_this_month)).count()

    if search_term_home:
        search_pattern = f"%{search_term_home}%"
        customer_query = customer_query.filter(or_(Customer.name.ilike(search_pattern), Customer.set_top_box_number.ilike(search_pattern)))
    
    customers_for_list = customer_query.order_by(Customer.name).all()
    paid_ids_for_list = {p.customer_id for p in Payment.query.filter(Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
    customers_list_on_home = [{'id': c.id, 'name': c.name, 'set_top_box_number': c.set_top_box_number, 'monthly_charge': c.monthly_charge, 'status': c.status, 'paid_current_month': c.id in paid_ids_for_list} for c in customers_for_list]
    
    return render_template('index.html', total_customers_count=total_customers_count, active_customers_count=active_customers_count, outstanding_payments_count=outstanding_payments_count, collections_today=collections_today, current_billing_period_display=f"{month_name[current_month]} {current_year}", customers_list_on_home=customers_list_on_home, search_term_home=search_term_home, operator_stats=operator_stats)

# --- Customer Management Routes (with new Import/Export) ---
@app.route('/customers')
@login_required
def customers_list():
    query = Customer.query
    if not current_user.is_admin:
        query = query.filter_by(operator_id=current_user.id)
    search_query_customers = request.args.get('search_customers', '')
    if search_query_customers:
        search_pattern = f"%{search_query_customers}%"
        query = query.filter(or_(Customer.name.ilike(search_pattern), Customer.set_top_box_number.ilike(search_pattern), Customer.address.ilike(search_pattern), Customer.phone_number.ilike(search_pattern)))
    customers = query.order_by(Customer.name).all()
    return render_template('customers.html', customers=customers, search_query_customers=search_query_customers)

@app.route('/customers/export_csv')
@login_required
def export_customers():
    query = Customer.query
    if not current_user.is_admin:
        query = query.filter_by(operator_id=current_user.id)
    customers = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    header = ['name', 'address', 'phone_number', 'plan_details', 'monthly_charge', 'set_top_box_number', 'connection_date', 'status', 'notes']
    writer.writerow(header)
    for customer in customers:
        row_data = [
            customer.name, customer.address, customer.phone_number, customer.plan_details,
            customer.monthly_charge, customer.set_top_box_number,
            customer.connection_date.isoformat() if customer.connection_date else '',
            customer.status, customer.notes
        ]
        writer.writerow(row_data)
    
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=customers_export.csv"})

@app.route('/customers/import_csv', methods=['POST'])
@login_required
def import_customers():
    file = request.files.get('file')
    if not file or not getattr(file, 'filename', '').endswith('.csv'):
        flash('Please upload a valid .csv file.', 'danger')
        return redirect(url_for('customers_list'))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF-8"), newline=None)
        csv_reader = csv.DictReader(stream)
        imported_count = 0
        for row in csv_reader:
            stb = row.get('set_top_box_number')
            if not stb or Customer.query.filter_by(set_top_box_number=stb).first():
                continue
            new_customer = Customer()
            new_customer.operator_id = current_user.id
            new_customer.name = row['name']
            new_customer.address = row['address']
            new_customer.phone_number = row.get('phone_number')
            new_customer.plan_details = row.get('plan_details')
            new_customer.monthly_charge = float(row['monthly_charge'])
            new_customer.set_top_box_number = stb
            new_customer.connection_date = datetime.strptime(row['connection_date'], '%Y-%m-%d').date() if row.get('connection_date') else None
            new_customer.status = row.get('status', 'Active')
            new_customer.notes = row.get('notes')
            db.session.add(new_customer)
            imported_count += 1
        db.session.commit()
        flash(f'{imported_count} new customers imported successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during import: {str(e)}', 'danger')
    return redirect(url_for('customers_list'))

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        if Customer.query.filter_by(set_top_box_number=request.form['set_top_box_number']).first():
            flash('A customer with this Set-Top Box number already exists.', 'danger')
            return render_template('add_customer.html', is_edit=False, customer=request.form, today_date=date.today().isoformat())
        new_customer = Customer()
        new_customer.operator_id = current_user.id
        new_customer.name = request.form['name']
        new_customer.address = request.form['address']
        new_customer.phone_number = request.form.get('phone_number')
        new_customer.plan_details = request.form.get('plan_details')
        new_customer.monthly_charge = float(request.form['monthly_charge'])
        new_customer.set_top_box_number = request.form['set_top_box_number']
        new_customer.connection_date = datetime.strptime(request.form['connection_date'], '%Y-%m-%d').date() if request.form.get('connection_date') else None
        new_customer.status = request.form['status']
        new_customer.notes = request.form.get('notes')
        db.session.add(new_customer)
        db.session.commit()
        flash(f'Customer {new_customer.name} added successfully!', 'success')
        return redirect(url_for('customers_list'))
    return render_template('add_customer.html', is_edit=False, customer=None, today_date=date.today().isoformat())

# === FIXED: Replaced .get_or_404 with .filter_by(...).first_or_404() ===
@app.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    query = Customer.query
    if not current_user.is_admin:
        query = query.filter_by(operator_id=current_user.id)
    
    customer = query.filter_by(id=customer_id).first_or_404()

    if request.method == 'POST':
        customer.name = request.form['name']
        customer.address = request.form['address']
        customer.phone_number = request.form.get('phone_number')
        customer.plan_details = request.form.get('plan_details')
        customer.monthly_charge = float(request.form['monthly_charge'])
        customer.connection_date = datetime.strptime(request.form['connection_date'], '%Y-%m-%d').date() if request.form.get('connection_date') else None
        customer.status = request.form['status']
        customer.notes = request.form.get('notes')
        db.session.commit()
        flash(f'Customer {customer.name} updated successfully!', 'success')
        return redirect(url_for('customers_list'))
    return render_template('add_customer.html', is_edit=True, customer=customer, today_date=date.today().isoformat())

# === FIXED: Replaced .get_or_404 with .filter_by(...).first_or_404() ===
@app.route('/customers/delete/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    query = Customer.query
    if not current_user.is_admin:
        query = query.filter_by(operator_id=current_user.id)
    
    customer = query.filter_by(id=customer_id).first_or_404()
    
    db.session.delete(customer)
    db.session.commit()
    flash(f'Customer {customer.name} has been deleted.', 'success')
    return redirect(url_for('customers_list'))

# --- Payment and Report Routes ---
@app.route('/payments/record', methods=['GET', 'POST'])
@login_required
def record_payment():
    customers_query = Customer.query.filter_by(status='Active')
    if not current_user.is_admin:
        customers_query = customers_query.filter_by(operator_id=current_user.id)
    customers = customers_query.order_by(Customer.name).all()
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        customer = Customer.query.get(customer_id)
        if not customer or (not current_user.is_admin and customer.operator_id != current_user.id):
            flash('Invalid customer selected.', 'danger')
        else:
            amount_paid_val = request.form.get('amount_paid')
            amount_paid = float(amount_paid_val) if amount_paid_val is not None and amount_paid_val != '' else customer.monthly_charge
            new_payment = Payment()
            new_payment.customer_id = customer_id
            new_payment.user_id = current_user.id
            new_payment.payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
            new_payment.amount_paid = amount_paid
            new_payment.billing_period_month = int(request.form['billing_period_month'])
            new_payment.billing_period_year = int(request.form['billing_period_year'])
            new_payment.payment_method = request.form['payment_method']
            new_payment.transaction_reference = request.form.get('transaction_reference')
            new_payment.received_by = current_user.name
            db.session.add(new_payment)
            db.session.commit()
            flash(f'Payment for {customer.name} recorded successfully!', 'success')
            return redirect(url_for('index'))
    customer_id_prefill = request.args.get('customer_id_prefill', type=int)
    prefill_customer = Customer.query.get(customer_id_prefill)
    default_amount = prefill_customer.monthly_charge if prefill_customer and (current_user.is_admin or prefill_customer.operator_id == current_user.id) else None
    return render_template('record_payment.html', customers=customers, today_date=date.today().isoformat(), billing_months=get_billing_periods()[0], billing_years=get_billing_periods()[1], current_month=datetime.now().month, current_year=datetime.now().year, customer_id_prefill=customer_id_prefill, default_amount=default_amount, form_values=request.form if request.method == 'POST' else None)

@app.route('/payments/log')
@login_required
def payments_log():
    query = Payment.query.join(Customer)
    if not current_user.is_admin:
        query = query.filter(Customer.operator_id == current_user.id)
    if request.args.get('customer_name'):
        query = query.filter(Customer.name.ilike(f"%{request.args.get('customer_name')}%"))
    payments = query.order_by(Payment.payment_date.desc(), Payment.id.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=15)
    return render_template('payments_log.html', payments=payments, search_customer_name=request.args.get('customer_name', ''))

@app.route('/payments/export_pdf')
@login_required
def export_payments_pdf():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        flash("Please provide both a start and end date for the PDF export.", "danger")
        return redirect(url_for('payments_log'))
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    query = Payment.query.join(Customer).filter(Payment.payment_date.between(start_date, end_date))
    if not current_user.is_admin:
        query = query.filter(Customer.operator_id == current_user.id)
    
    payments = query.order_by(Payment.payment_date.asc()).all()
    total_collection = sum(p.amount_paid for p in payments)

    html = render_template('report_pdf_template.html', payments=payments, start_date=start_date, end_date=end_date, operator_name=current_user.name, total_collection=total_collection)
    pdf = HTML(string=html).write_pdf()
    
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=payments_report.pdf'})

@app.route('/reports')
@login_required
def reports_page():
    return render_template('reports.html', report_type=None)

@app.route('/reports/outstanding')
@login_required 
def outstanding_payments_report():
    billing_months, billing_years = get_billing_periods()
    report_month = request.args.get('month', datetime.now().month, type=int)
    report_year = request.args.get('year', datetime.now().year, type=int)
    
    paid_customer_ids = {p.customer_id for p in Payment.query.filter_by(billing_period_month=report_month, billing_period_year=report_year)}
    
    customer_query = Customer.query.filter(Customer.status == 'Active', Customer.id.notin_(paid_customer_ids))
    if not current_user.is_admin:
        customer_query = customer_query.filter(Customer.operator_id == current_user.id)
    
    outstanding_customers = customer_query.order_by(Customer.name).all()
    
    return render_template('reports.html', report_type='outstanding', outstanding_customers=outstanding_customers, billing_months=billing_months, billing_years=billing_years, report_month=report_month, report_year=report_year, selected_month_name=month_name[report_month])

@app.route('/reports/collections')
@login_required
def collections_report():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    collections, total_cash, total_online, grand_total = [], 0, 0, 0
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        query = Payment.query.filter(Payment.payment_date.between(start_date, end_date))
        if not current_user.is_admin:
            query = query.join(Customer).filter(Customer.operator_id == current_user.id)
        
        collections = query.order_by(Payment.payment_date.desc()).all()
        total_cash = sum(p.amount_paid for p in collections if p.payment_method == 'Cash')
        total_online = sum(p.amount_paid for p in collections if p.payment_method == 'Online')
        grand_total = total_cash + total_online

    return render_template('reports.html', report_type='collections', collections=collections, total_cash=total_cash, total_online=total_online, grand_total=grand_total, start_date=start_date_str, end_date=end_date_str, today_date=date.today().isoformat(), _form_submitted_and_valid=(start_date_str and end_date_str))

if __name__ == '__main__':
    app.run(debug=True)