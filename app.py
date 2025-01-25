from flask import Flask, render_template, redirect, flash, jsonify, request, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField,IntegerField,FloatField,TextAreaField
from wtforms.validators import DataRequired,NumberRange
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import os
import pandas as pd
import pickle
from haversine import haversine, Unit

app = Flask(__name__)
app.config['SECRET_KEY'] = '99875e40247d4d65b01363aa3db01cc2'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///business.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

db = SQLAlchemy(app)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    business_name = db.Column(db.String(100), nullable=False)
    business_type = db.Column(db.String(50), nullable=False)
    registration_number = db.Column(db.String(50), unique=True, nullable=False)
    tax_id = db.Column(db.String(50), unique=True, nullable=False)
    business_address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    contact_person = db.Column(db.String(100), nullable=False)
    contact_email = db.Column(db.String(120), unique=True, nullable=False)
    business_description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Business {self.business_name}>'
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Admin {self.username}>'
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_price = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)

    def calculate_total_value(self):
        """Calculate total value of inventory item"""
        self.total_value = self.quantity * self.unit_price
        return self.total_value

    def __repr__(self):
        return f'<Inventory {self.product_name} - {self.product_code}>'
# Make sure to call create_default_admin during the application startup
has_run_before = False

@app.before_request
def initialize_database():
    global has_run_before
    if not has_run_before:
        db.create_all()
        create_default_admin()  # Ensure that default admin is created
        has_run_before = True

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/warehouses', methods=['GET', 'POST'])
def warehouses():
    # Load prediction resources
    with open('warehouse_model.pkl', 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model']
        scaler = model_data['scaler']
        warehouses = model_data['warehouses']
    
    fixed_warehouse = pd.read_csv('fixed_warehouse.csv')
    show_prediction = False
    result_warehouses = []

    if request.method == 'POST':
        if 'inventory_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        file = request.files['inventory_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process prediction
            new_data = pd.read_csv(filepath)
            merged_data = pd.merge(
                new_data,
                fixed_warehouse[['District', 'Latitude', 'Longitude']],
                on='District',
                how='left'
            )
            clean_data = merged_data.dropna(subset=['Latitude', 'Longitude']).copy()

            def calculate_distances(row):
                return [
                    haversine((row['Latitude'], row['Longitude']), 
                              (wh['Latitude'], wh['Longitude']), unit=Unit.KILOMETERS)
                    for _, wh in warehouses.iterrows()
                ]

            new_distances = clean_data.apply(calculate_distances, axis=1)
            distance_df = pd.DataFrame(
                new_distances.tolist(),
                columns=warehouses['District']
            )
            scaled_data = scaler.transform(distance_df)
            clean_data['Optimal Warehouse'] = [
                warehouses.iloc[cluster]['District'] 
                for cluster in model.predict(scaled_data)
            ]

            warehouse_counts = clean_data['Optimal Warehouse'].value_counts()
            threshold = warehouse_counts.quantile(0.75)
            significant_warehouses = warehouse_counts[warehouse_counts >= threshold].index.tolist()

            result_warehouses = []
            for warehouse_name in significant_warehouses:
                warehouse_info = fixed_warehouse[fixed_warehouse['District'] == warehouse_name].iloc[0]
                result_warehouses.append({
                    'district': warehouse_name,
                    'latitude': warehouse_info['Latitude'],
                    'longitude': warehouse_info['Longitude'],
                })

            show_prediction = True
            flash('Warehouse prediction completed successfully!', 'success')

    return render_template(
        'warehouses.html', 
        title="Warehouses", 
        warehouses=result_warehouses, 
        show_prediction=show_prediction,
        map_key='AIzaSyBUembZbrAbmni90Rqwbd3drj5xBkRsF50'  # Replace with your actual Google Maps API key
    )

def create_default_admin():
    # Check if there are no admin records
    if not Admin.query.first():
        admin = Admin(username='admin')  # Admin username
        admin.set_password('admin123')  # Set a secure password
        db.session.add(admin)
        db.session.commit()
        print('Default admin user created: admin/admin123')



@app.route('/')
def home():
    return render_template('home.html', title="Home")


@app.route('/item_tracking')
def item_tracking():
    return render_template('item_tracking.html', title="Item Tracking")


@app.route('/waste_management')
def waste_management():
    return render_template('waste_management.html', title="Waste Management")


@app.route('/aboutUs')
def about_page():
    return render_template('about_page.html', title="About Us")



@app.route('/contact')
def contact():
    return render_template('contact.html', title="Contact")

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()  # Instantiate the form
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if form.validate_on_submit():  # Ensures the form fields are validated
        username = form.username.data
        password = form.password.data

        # Check if the username exists in the database
        business = Business.query.filter_by(username=username).first()

        # Validate password
        if business and business.check_password(password):
            session['user'] = business.id  # Store the business ID in session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html', title="Login", form=form)




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = [
                'username', 'password', 'business_name', 'business_type',
                'registration_number', 'tax_id', 'business_address',
                'city', 'state', 'postal_code', 'contact_person', 'contact_email'
            ]
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'Missing required field: {field}', 'danger')
                    return redirect(url_for('register'))

            # Check for existing business
            existing_business = Business.query.filter(
                (Business.registration_number == request.form['registration_number']) |
                (Business.contact_email == request.form['contact_email']) |
                (Business.username == request.form['username'])
            ).first()

            if existing_business:
                flash('Business with this registration number, email, or username already exists.', 'danger')
                return redirect(url_for('register'))

            # Create a new business
            new_business = Business(
                username=request.form['username'],
                business_name=request.form['business_name'],
                business_type=request.form['business_type'],
                registration_number=request.form['registration_number'],
                tax_id=request.form['tax_id'],
                business_address=request.form['business_address'],
                city=request.form['city'],
                state=request.form['state'],
                postal_code=request.form['postal_code'],
                contact_person=request.form['contact_person'],
                contact_email=request.form['contact_email'],
                business_description=request.form.get('business_description', '')
            )
            new_business.set_password(request.form['password'])

            db.session.add(new_business)
            db.session.commit()

            flash('Business registered successfully! Please log in.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error occurred during registration: {e}', 'danger')

    return render_template('register.html', title="Sign Up")
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Please log in to access your dashboard.', 'warning')
        return redirect(url_for('login'))
    
    # Fetch the logged-in business using the ID stored in the session
    business = Business.query.get(session['user'])
    
    # Example of additional dashboard data
    dashboard_data = {
        "business_name": business.business_name,
        "business_type": business.business_type,
        "registration_number": business.registration_number,
        "tax_id": business.tax_id,
        "contact_email": business.contact_email,
        "business_address": f"{business.business_address}, {business.city}, {business.state}, {business.postal_code}",
        "created_at": business.created_at.strftime('%Y-%m-%d'),
    }

    return render_template('dashboard.html', title="Dashboard", business=business, data=dashboard_data)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    print(f"Form submitted: {request.method}")
    print(f"Form valid: {form.validate_on_submit()}")

    if request.method == 'POST':
        username = form.username.data
        password = form.password.data
        print(f"Attempted login - Username: {username}")

        admin = Admin.query.filter_by(username=username).first()
        print(f"Admin found: {admin}")

        if admin and admin.check_password(password):
            session['admin'] = admin.id
            print("Admin login successful")
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            print("Login failed")
            flash('Invalid admin credentials. Please try again.', 'danger')

    return render_template('admin_login.html', title="Admin Login", form=form)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        flash('Please log in as an admin to access the dashboard.', 'warning')
        return redirect(url_for('admin_login'))

    # Fetch admin details
    admin = Admin.query.get(session['admin'])

    # Example: List all businesses for admin management
    businesses = Business.query.all()

    return render_template('admin_dashboard.html', title="Admin Dashboard", admin=admin, businesses=businesses)
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('admin_login'))

class InventoryForm(FlaskForm):
    product_name = StringField('Product Name', validators=[DataRequired()])
    product_code = StringField('Product Code', validators=[DataRequired()])
    category = StringField('Category', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    unit_price = FloatField('Unit Price', validators=[DataRequired(), NumberRange(min=0)])
    description = TextAreaField('Description')

@app.route('/admin/inventory', methods=['GET'])
def admin_inventory():
    if 'admin' not in session:
        flash('Please log in as an admin to access inventory.', 'warning')
        return redirect(url_for('admin_login'))

    inventories = Inventory.query.all()
    return render_template('admin_inventory.html', title="Inventory Management", inventories=inventories)
@app.route('/admin/inventory/add', methods=['GET', 'POST'])
def admin_add_inventory():
    if 'admin' not in session:
        flash('Please log in as an admin to access inventory.', 'warning')
        return redirect(url_for('admin_login'))

    form = InventoryForm()
    if form.validate_on_submit():
        try:
            # Get the first business for demo purposes (you might want to adjust this)
            business = Business.query.first()
            
            new_inventory = Inventory(
                product_name=form.product_name.data,
                product_code=form.product_code.data,
                category=form.category.data,
                quantity=form.quantity.data,
                unit_price=form.unit_price.data,
                description=form.description.data,
                business_id=business.id
            )
            
            # Calculate total value
            new_inventory.calculate_total_value()
            
            db.session.add(new_inventory)
            db.session.commit()
            
            flash('Inventory item added successfully!', 'success')
            return redirect(url_for('admin_inventory'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding inventory item: {str(e)}', 'danger')

    return render_template('admin_add_inventory.html', title="Add Inventory", form=form)

@app.route('/admin/inventory/edit/<int:inventory_id>', methods=['GET', 'POST'])
def admin_edit_inventory(inventory_id):
    if 'admin' not in session:
        flash('Please log in as an admin to access inventory.', 'warning')
        return redirect(url_for('admin_login'))

    inventory_item = Inventory.query.get_or_404(inventory_id)
    form = InventoryForm(obj=inventory_item)
    
    if form.validate_on_submit():
        try:
            form.populate_obj(inventory_item)
            inventory_item.calculate_total_value()
            
            db.session.commit()
            flash('Inventory item updated successfully!', 'success')
            return redirect(url_for('admin_inventory'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating inventory item: {str(e)}', 'danger')

    return render_template('admin_edit_inventory.html', title="Edit Inventory", form=form, inventory=inventory_item)

@app.route('/admin/inventory/delete/<int:inventory_id>', methods=['POST'])
def admin_delete_inventory(inventory_id):
    if 'admin' not in session:
        flash('Please log in as an admin to access inventory.', 'warning')
        return redirect(url_for('admin_login'))

    inventory_item = Inventory.query.get_or_404(inventory_id)
    
    try:
        db.session.delete(inventory_item)
        db.session.commit()
        flash('Inventory item deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting inventory item: {str(e)}', 'danger')
    
    return redirect(url_for('admin_inventory'))
@app.route('/admin/warehouse_inventory')
def warehouse_inventory():
    if 'admin' not in session:
        flash('Please log in as an admin to access this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    # Fetch warehouse inventory data
    inventory_items = Inventory.query.all()
    return render_template('warehouse_inventory.html', title="Warehouse Inventory", inventory=inventory_items)

@app.route('/admin/stock_tracking')
def stock_tracking():
    if 'admin' not in session:
        flash('Please log in as an admin to access this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    # Stock tracking logic
    stock_data = Inventory.query.all()
    return render_template('stock_tracking.html', title="Stock Tracking", stock=stock_data)

@app.route('/admin/waste_management_logs')
def waste_management_logs():
    if 'admin' not in session:
        flash('Please log in as an admin to access this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    # Waste management logs logic
    waste_logs = []  # Replace with actual data fetching logic
    return render_template('waste_management_logs.html', title="Waste Management Logs", logs=waste_logs)

@app.route('/admin/business_insights')
def business_insights():
    if 'admin' not in session:
        flash('Please log in as an admin to access this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    # Fetch analytical data
    insights = {}  # Replace with actual data fetching logic
    return render_template('business_insights.html', title="Business Insights", insights=insights)

@app.route('/admin/reports')
def reports():
    if 'admin' not in session:
        flash('Please log in as an admin to access this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    # Generate and display reports
    reports_data = []  # Replace with actual data fetching logic
    return render_template('reports.html', title="Reports", reports=reports_data)
@app.route('/business/<int:business_id>')
def view_business(business_id):
    if 'admin' not in session:
        flash('Please log in as an admin to access this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    # Fetch business details based on business_id
    business = Business.query.get(business_id)
    if not business:
        flash('Business not found.', 'danger')
        return redirect(url_for('business_insights'))
    
    return render_template('view_business.html', business=business)
@app.route('/business/edit/<int:business_id>', methods=['GET', 'POST'])
def edit_business(business_id):
    # Logic for editing a business
    business = Business.query.get_or_404(business_id)
    if request.method == 'POST':
        business.name = request.form['name']
        business.description = request.form['description']
        db.session.commit()
        flash('Business updated successfully!', 'success')
        return redirect(url_for('view_business', business_id=business_id))
    return render_template('edit_business.html', business=business)

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    form = InventoryForm()

    if form.validate_on_submit():
        # Handle form submission, save data, etc.
        pass

    return render_template('inventory_management.html', form=form)




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
