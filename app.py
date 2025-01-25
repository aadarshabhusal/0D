from flask import Flask, render_template, redirect, flash, jsonify, request, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_wtf import FlaskForm
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

has_run_before = False


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


@app.route('/marketplace')
def marketplace():
    return render_template('marketplace.html', title="Marketplace")


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





if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
