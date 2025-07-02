import os
from datetime import datetime, date
from calendar import month_name
from functools import wraps
from collections import defaultdict
import io
import csv
import sys

from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, DDL
from weasyprint import HTML, CSS

# --- Initialize Extensions ---
db = SQLAlchemy()
login_manager = LoginManager()

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.Text, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    payments = db.relationship('Payment', backref='user', lazy=True)
    customers = db.relationship('Customer', backref='operator', lazy=True, cascade="all, delete-orphan")

    @property
    def username(self): return self.email
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone_number = db.Column(db.String(15), unique=True)
    plan_details = db.Column(db.String(100))
    monthly_charge = db.Column(db.Float, nullable=False)
    set_top_box_number = db.Column(db.String(50), unique=True, nullable=False)
    connection_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default='Active')
    notes = db.Column(db.Text)
    payments = db.relationship('Payment', backref='customer', lazy=True, cascade="all, delete-orphan")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    payment_date = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    billing_period_month = db.Column(db.Integer, nullable=False)
    billing_period_year = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default='Cash')
    transaction_reference = db.Column(db.String(100))
    received_by = db.Column(db.String(100)) 

    @property
    def billing_period_display(self): return f"{month_name[self.billing_period_month]} {self.billing_period_year}"

# --- THE APPLICATION FACTORY ---
def create_app():
    app = Flask(__name__)
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("WARNING: DATABASE_URL is not set. Using local development database.", file=sys.stderr)
        database_url = "postgresql://cablepro_user:apple@localhost/cablepro_db"
    
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_dev_only')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login' 
    login_manager.login_message_category = 'danger' 

    @login_manager.user_loader
    def load_user(user_id):
        with app.app_context():
            return User.query.get(int(user_id))
    
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
                return redirect(url_for('root'))
            return f(*args, **kwargs)
        return decorated_function

    @app.route("/")
    @login_required
    def root():
        return dashboard()

    @app.route("/login", methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('root'))
        
        if request.method == 'POST':
            user = User.query.filter_by(email=request.form.get('email')).first()
            if user and user.check_password(request.form.get('password')):
                login_user(user)
                flash(f'Login successful. Welcome, {user.name}!', 'success')
                return redirect(request.args.get('next') or url_for('root'))
            else:
                flash('Login failed. Please check your email and password.', 'danger')
                return render_template('auth.html', is_register=False)
                
        return render_template('auth.html', is_register=False)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))
        
    @app.route("/register", methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated and not current_user.is_admin:
            flash("You are already logged in.", "info")
            return redirect(url_for('root'))
        
        if request.method == 'POST':
            user_exists = User.query.filter_by(email=request.form.get('email')).first()
            if user_exists:
                flash('An account with this email address already exists.', 'danger')
                return render_template('auth.html', is_register=True)
                
            new_user = User(
                email=request.form.get('email'), 
                name=request.form.get('name'), 
                address=request.form.get('address'), 
                is_admin=False
            )
            new_user.set_password(request.form.get('password'))
            db.session.add(new_user)
            db.session.commit()
            
            if current_user.is_authenticated and current_user.is_admin:
                flash(f'New operator account for {new_user.name} created successfully!', 'success')
                return redirect(url_for('manage_users'))
            else:
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            
        return render_template('auth.html', is_register=True)

    @app.route("/forgot-password")
    def forgot_password():
        return render_template('forgot_password.html')

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name')
            address = request.form.get('address')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            # Update the user object's attributes in memory
            current_user.name = name
            current_user.address = address

            # Handle password change if a new password was provided
            if new_password:
                if new_password != confirm_password:
                    flash('New passwords do not match.', 'danger')
                    return redirect(url_for('profile'))
                current_user.set_password(new_password)

            try:
                # Explicitly add the modified user object to the session to mark for saving.
                db.session.add(current_user)
                # Commit the changes to the database.
                db.session.commit()
                flash('Your profile has been updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred while updating your profile: {e}', 'danger')

            return redirect(url_for('profile'))

        return render_template('profile.html')

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
            flash(f"User '{user_to_delete.name}' and their assigned data have been deleted.", 'success')
        return redirect(url_for('manage_users'))
    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        current_month, current_year = datetime.now().month, datetime.now().year
        search_term_home = request.args.get('search_home', '')
        operator_stats = []
        if current_user.is_admin:
            customer_query = Customer.query
            collections_today = db.session.query(db.func.sum(Payment.amount_paid)).filter(Payment.payment_date == date.today(), Payment.user_id == current_user.id).scalar() or 0.0
            paid_ids = {p.customer_id for p in Payment.query.filter(Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
            outstanding_payments_count = customer_query.filter(Customer.status == 'Active', Customer.id.notin_(paid_ids)).count()
            operators = User.query.order_by(User.name).all()
            for op in operators:
                op_paid_ids = {p.customer_id for p in Payment.query.join(Customer).filter(Customer.operator_id == op.id, Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
                operator_stats.append({'name': op.name, 'total_customers': Customer.query.filter_by(operator_id=op.id).count(), 'active_customers': Customer.query.filter_by(operator_id=op.id, status='Active').count(), 'collections_today': db.session.query(db.func.sum(Payment.amount_paid)).join(Customer).filter(Customer.operator_id == op.id, Payment.payment_date == date.today()).scalar() or 0.0, 'outstanding': Customer.query.filter(Customer.operator_id == op.id, Customer.status == 'Active', Customer.id.notin_(op_paid_ids)).count()})
        else: # Operator View
            customer_query = Customer.query.filter_by(operator_id=current_user.id)
            payment_subquery = Payment.query.join(Customer).filter(Customer.operator_id == current_user.id).subquery()
            collections_today = db.session.query(db.func.sum(payment_subquery.c.amount_paid)).filter(payment_subquery.c.payment_date == date.today()).scalar() or 0.0
            paid_ids = {p.customer_id for p in Payment.query.join(Customer).filter(Customer.operator_id == current_user.id, Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
            outstanding_payments_count = customer_query.filter(Customer.status == 'Active', Customer.id.notin_(paid_ids)).count()

        if search_term_home:
            customer_query = customer_query.filter(or_(Customer.name.ilike(f"%{search_term_home}%"), Customer.set_top_box_number.ilike(f"%{search_term_home}%")))
        customers_for_list = customer_query.order_by(Customer.name).all()
        paid_ids_for_list = {p.customer_id for p in Payment.query.filter(Payment.billing_period_month == current_month, Payment.billing_period_year == current_year)}
        customers_list_on_home = [{'id': c.id, 'name': c.name, 'set_top_box_number': c.set_top_box_number, 'monthly_charge': c.monthly_charge, 'status': c.status, 'paid_current_month': c.id in paid_ids_for_list} for c in customers_for_list]
        return render_template('index.html', total_customers_count=Customer.query.filter_by(operator_id=current_user.id).count() if not current_user.is_admin else Customer.query.count(), active_customers_count=Customer.query.filter_by(operator_id=current_user.id, status='Active').count() if not current_user.is_admin else Customer.query.filter_by(status='Active').count(), outstanding_payments_count=outstanding_payments_count, collections_today=collections_today, current_billing_period_display=f"{month_name[current_month]} {current_year}", customers_list_on_home=customers_list_on_home, search_term_home=search_term_home, operator_stats=operator_stats)
    
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
            row_data = [getattr(customer, col) if col != 'connection_date' else (customer.connection_date.isoformat() if customer.connection_date else '') for col in header]
            writer.writerow(row_data)
        output.seek(0)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=customers_export.csv"})

    @app.route('/customers/import_csv', methods=['POST'])
    @login_required
    def import_customers():
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'):
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
                new_customer = Customer(operator_id=current_user.id, name=row['name'], address=row['address'], phone_number=row.get('phone_number'), plan_details=row.get('plan_details'), monthly_charge=float(row['monthly_charge']), set_top_box_number=stb, connection_date=datetime.strptime(row['connection_date'], '%Y-%m-%d').date() if row.get('connection_date') else None, status=row.get('status', 'Active'), notes=row.get('notes'))
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
            stb_number = request.form.get('set_top_box_number')
            phone_number = request.form.get('phone_number')
            stb_exists = Customer.query.filter_by(set_top_box_number=stb_number).first()
            if stb_exists:
                flash(f'Error: A customer with Set-Top Box number "{stb_number}" already exists.', 'danger')
                return render_template('add_customer.html', is_edit=False, customer_form=request.form, date=date)
            if phone_number:
                phone_exists = Customer.query.filter_by(phone_number=phone_number).first()
                if phone_exists:
                    flash(f'Error: A customer with phone number "{phone_number}" already exists.', 'danger')
                    return render_template('add_customer.html', is_edit=False, customer_form=request.form, date=date)
            new_customer = Customer(operator_id=current_user.id, name=request.form['name'], address=request.form['address'], phone_number=phone_number, plan_details=request.form.get('plan_details'), monthly_charge=float(request.form['monthly_charge']), set_top_box_number=stb_number, connection_date=datetime.strptime(request.form['connection_date'], '%Y-%m-%d').date() if request.form.get('connection_date') else None, status=request.form['status'], notes=request.form.get('notes'))
            db.session.add(new_customer)
            db.session.commit()
            flash(f'Customer {new_customer.name} added successfully!', 'success')
            return redirect(url_for('customers_list'))
        return render_template('add_customer.html', is_edit=False, customer_form={}, date=date)

    @app.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
    @login_required
    def edit_customer(customer_id):
        query = Customer.query
        if not current_user.is_admin:
            query = query.filter_by(operator_id=current_user.id)
        customer = query.filter_by(id=customer_id).first_or_404()
        if request.method == 'POST':
            customer.name, customer.address, customer.phone_number, customer.plan_details, customer.monthly_charge, customer.connection_date, customer.status, customer.notes = request.form['name'], request.form['address'], request.form.get('phone_number'), request.form.get('plan_details'), float(request.form['monthly_charge']), datetime.strptime(request.form['connection_date'], '%Y-%m-%d').date() if request.form.get('connection_date') else None, request.form['status'], request.form.get('notes')
            db.session.commit()
            flash(f'Customer {customer.name} updated successfully!', 'success')
            return redirect(url_for('customers_list'))
        return render_template('add_customer.html', is_edit=True, customer=customer, customer_form={}, date=date)
    
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
    
    @app.route('/payments/record', methods=['GET', 'POST'])
    @login_required
    def record_payment():
        customers_query = Customer.query.filter_by(status='Active')
        if not current_user.is_admin:
            customers_query = customers_query.filter_by(operator_id=current_user.id)
        customers = customers_query.order_by(Customer.name).all()
        if request.method == 'POST':
            customer = Customer.query.get(request.form.get('customer_id'))
            if not customer or (not current_user.is_admin and customer.operator_id != current_user.id):
                flash('Invalid customer selected.', 'danger')
            else:
                amount = float(request.form.get('amount_paid')) if request.form.get('amount_paid') else customer.monthly_charge
                payment = Payment(customer_id=customer.id, user_id=current_user.id, payment_date=datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date(), amount_paid=amount, billing_period_month=int(request.form['billing_period_month']), billing_period_year=int(request.form['billing_period_year']), payment_method=request.form['payment_method'], transaction_reference=request.form.get('transaction_reference'), received_by=current_user.name)
                db.session.add(payment)
                db.session.commit()
                flash(f'Payment for {customer.name} recorded!', 'success')
                return redirect(url_for('root'))
        prefill_customer = None
        customer_id_prefill = request.args.get('customer_id_prefill', type=int)
        if customer_id_prefill:
            prefill_customer = Customer.query.get(customer_id_prefill)
        default_amount = prefill_customer.monthly_charge if prefill_customer and (current_user.is_admin or prefill_customer.operator_id == current_user.id) else None
        return render_template('record_payment.html', customers=customers, today_date=date.today().isoformat(), billing_months=get_billing_periods()[0], billing_years=get_billing_periods()[1], current_month=datetime.now().month, current_year=datetime.now().year, customer_id_prefill=customer_id_prefill, default_amount=default_amount)

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
        start_date_str, end_date_str = request.args.get('start_date'), request.args.get('end_date')
        if not start_date_str or not end_date_str:
            flash("Please provide both a start and end date for the PDF export.", "danger")
            return redirect(url_for('payments_log'))
        start_date, end_date = datetime.strptime(start_date_str, '%Y-%m-%d').date(), datetime.strptime(end_date_str, '%Y-%m-%d').date()
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
        start_date_str, end_date_str = request.args.get('start_date'), request.args.get('end_date')
        collections, total_cash, total_online, grand_total = [], 0, 0, 0
        if start_date_str and end_date_str:
            start_date, end_date = datetime.strptime(start_date_str, '%Y-%m-%d').date(), datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = Payment.query.filter(Payment.payment_date.between(start_date, end_date))
            if not current_user.is_admin:
                query = query.join(Customer).filter(Customer.operator_id == current_user.id)
            collections = query.order_by(Payment.payment_date.desc()).all()
            total_cash = sum(p.amount_paid for p in collections if p.payment_method == 'Cash')
            total_online = sum(p.amount_paid for p in collections if p.payment_method == 'Online')
            grand_total = total_cash + total_online
        return render_template('reports.html', report_type='collections', collections=collections, total_cash=total_cash, total_online=total_online, grand_total=grand_total, start_date=start_date_str, end_date=end_date_str, today_date=date.today().isoformat(), _form_submitted_and_valid=(start_date_str and end_date_str))

    @app.cli.command("generate-sql")
    def generate_sql():
        from sqlalchemy.schema import CreateTable
        print("-- SQL Statements for Vercel/Supabase Database Setup --")
        for table in db.metadata.tables.values():
            print(str(CreateTable(table).compile(db.engine)).strip() + ";")
        print("\n-- Remember to also run the INSERT for the admin user --")
        print("-- NOTE: You must generate the admin password hash locally first.")
        print("INSERT INTO \"user\" (name, email, address, password_hash, is_admin) VALUES ('Default Admin', 'admin@cablepro.com', 'Main Office', 'PASTE_YOUR_HASH_HERE', true);")

    @app.cli.command("init-db")
    def initialize_database():
        db.create_all()
        if not User.query.filter_by(email='admin@cablepro.com').first():
            admin_user = User(name='Default Admin', email='admin@cablepro.com', address='Main Office', is_admin=True)
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin created.")
        else:
            print("Admin user already exists.")
            
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
