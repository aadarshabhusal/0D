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


# Complete list of 77 districts in Nepal
NEPAL_DISTRICTS = [
    # Provinces
    # Province 1
    "Bhojpur", "Dhankuta", "Ilam", "Jhapa", "Khotang", "Morang", "Okhaldunga", 
    "Panchthar", "Sankhuwasabha", "Solukhumbu", "Sunsari", "Taplejung", "Tehrathum", "Udayapur",
    
    # Province 2
    "Bara", "Dhanusa", "Mahottari", "Parsa", "Rautahat", "Sarlahi", "Saptari", "Siraha",
    
    # Province 3 (Bagmati)
    "Bhaktapur", "Dhading", "Kathmandu", "Kavrepalanchok", "Lalitpur", "Nuwakot", 
    "Rasuwa", "Sindhuli", "Sindhupalchok",
    
    # Province 4 (Gandaki)
    "Gorkha", "Kaski", "Lamjung", "Manang", "Mustang", "Myagdi", "Nawalpur", "Parbat", "Syangja", "Tanahun",
    
    # Province 5
    "Arghakhanchi", "Banke", "Bardiya", "Dang", "Gulmi", "Kapilvastu", "Parasi", 
    "Palpa", "Pyuthan", "Rolpa", "Rukum", "Rupandehi",
    
    # Province 6 (Karnali)
    "Dailekh", "Dolpa", "Humla", "Jajarkot", "Jumla", "Kalikot", "Mugu", "Rukum East", "Salyan", "Surkhet",
    
    # Province 7
    "Achham", "Baitadi", "Bajhang", "Bajura", "Dadeldhura", "Darchula", "Doti", 
    "Kailali", "Kanchanpur"
]

@app.route('/logistics', methods=['GET', 'POST'])
def item_tracking():
    # Comprehensive district coordinates (more accurate representation)
    DISTRICT_COORDINATES = {
        # Province 1
        "Bhojpur": (26.9302, 87.0372), "Dhankuta": (26.9862, 87.0919), 
        "Ilam": (26.9092, 88.0841), "Jhapa": (26.7271, 88.0845), 
        "Khotang": (27.1838, 86.7819), "Morang": (26.5333, 87.2667), 
        "Okhaldunga": (27.3175, 86.5314), "Panchthar": (27.0769, 87.9183), 
        "Sankhuwasabha": (27.2667, 87.2333), "Solukhumbu": (27.7900, 86.5400), 
        "Sunsari": (26.6276, 87.1822), "Taplejung": (27.3552, 87.6689), 
        "Tehrathum": (27.1831, 87.4269), "Udayapur": (26.8406, 86.8406),
        
        # Province 2
        "Bara": (26.7272, 85.9300), "Dhanusa": (26.8350, 86.0122), 
        "Mahottari": (26.7333, 86.0667), "Parsa": (27.0667, 84.8833), 
        "Rautahat": (26.6667, 86.1667), "Sarlahi": (26.7333, 85.8333), 
        "Saptari": (26.5667, 86.7333), "Siraha": (26.6667, 86.2167),
        
        # Province 3 (Bagmati)
        "Bhaktapur": (27.6712, 85.4298), "Dhading": (28.0833, 84.8833), 
        "Kathmandu": (27.7103, 85.3222), "Kavrepalanchok": (27.5333, 85.5333), 
        "Lalitpur": (27.6589, 85.3378), "Nuwakot": (28.1667, 85.2667), 
        "Rasuwa": (28.1667, 85.4167), "Sindhuli": (27.3333, 86.0333), 
        "Sindhupalchok": (27.8333, 85.7500),
        
        # Province 4 (Gandaki)
        "Gorkha": (27.9842, 84.6270), "Kaski": (28.2622, 84.0167), 
        "Lamjung": (28.2333, 84.3667), "Manang": (28.6667, 84.0333), 
        "Mustang": (28.8333, 83.7667), "Myagdi": (28.3667, 83.7667), 
        "Nawalpur": (27.7000, 84.4333), "Parbat": (28.2333, 83.9667), 
        "Syangja": (28.1167, 83.9000), "Tanahun": (28.0333, 84.3333),
        
        # Province 5
        "Arghakhanchi": (27.7500, 83.3833), "Banke": (28.1500, 81.7500), 
        "Bardiya": (28.2000, 81.4333), "Dang": (28.0833, 82.3000), 
        "Gulmi": (28.0833, 83.3000), "Kapilvastu": (27.5667, 83.0000), 
        "Parasi": (27.5333, 83.3789), "Palpa": (28.1500, 83.5167), 
        "Pyuthan": (28.1000, 82.8667), "Rolpa": (28.3816, 82.6483), 
        "Rukum": (28.3500, 82.2000), "Rupandehi": (27.5330, 83.3789),
        
        # Province 6 (Karnali)
        "Dailekh": (28.8500, 81.7000), "Dolpa": (29.0333, 82.8333), 
        "Humla": (29.9667, 81.8167), "Jajarkot": (28.6167, 81.6833), 
        "Jumla": (29.2889, 82.3018), "Kalikot": (28.8667, 81.6167), 
        "Mugu": (29.2500, 81.9833), "Rukum East": (28.3816, 82.6483), 
        "Salyan": (28.3500, 81.9667), "Surkhet": (28.6167, 81.6500),
        
        # Province 7
        "Achham": (29.0396, 81.2519), "Baitadi": (29.3333, 80.5833), 
        "Bajhang": (29.5167, 81.3000), "Bajura": (29.4833, 81.5167), 
        "Dadeldhura": (29.2188, 80.4994), "Darchula": (29.8667, 80.5667), 
        "Doti": (29.0000, 81.4000), "Kailali": (28.7000, 80.9667), 
        "Kanchanpur": (28.9333, 80.5667)
    }

    # Convert dictionary to list of district names
    districts = sorted(list(DISTRICT_COORDINATES.keys()))

    if request.method == 'POST':
        try:
            # Extract form data
            delivery_district = request.form.get('delivery_district')
            product_quantity = float(request.form.get('product_quantity', 0))
            product_weight = float(request.form.get('product_weight', 0))

            # Find nearest warehouse using comprehensive district coordinates
            def find_nearest_warehouse(target_district):
                target_lat, target_lng = DISTRICT_COORDINATES.get(
                    target_district, 
                    (27.7103, 85.3222)  # Default to Kathmandu if not found
                )

                # Calculate distances to all districts
                distances = {
                    district: haversine(
                        (target_lat, target_lng), 
                        DISTRICT_COORDINATES.get(district, (27.7103, 85.3222)), 
                        unit=Unit.KILOMETERS
                    )
                    for district in DISTRICT_COORDINATES.keys() 
                    if district != target_district
                }

                # Find nearest district
                nearest_district = min(distances, key=distances.get)
                nearest_lat, nearest_lng = DISTRICT_COORDINATES[nearest_district]

                return {
                    'District': nearest_district,
                    'Latitude': nearest_lat,
                    'Longitude': nearest_lng
                }, {
                    'District': target_district,
                    'Latitude': target_lat,
                    'Longitude': target_lng
                }

            # Get warehouse details
            nearest_warehouse, delivery_location = find_nearest_warehouse(delivery_district)

            # Comprehensive logistics calculations
            estimated_distance = haversine(
                (nearest_warehouse['Latitude'], nearest_warehouse['Longitude']), 
                (delivery_location['Latitude'], delivery_location['Longitude']), 
                unit=Unit.KILOMETERS
            )
            
            # Detailed cost calculations
            base_delivery_rate = 50  # NPR per km base rate
            weight_rate = 10  # Additional NPR per kg
            quantity_rate = 5  # Additional NPR per unit

            distance_cost = estimated_distance * base_delivery_rate
            weight_cost = product_weight * weight_rate
            quantity_cost = product_quantity * quantity_rate

            total_delivery_cost = distance_cost + weight_cost + quantity_cost

            # Estimated delivery time
            avg_speed = 40  # km/h considering Nepalese terrain
            estimated_time = estimated_distance / avg_speed

            # Prepare route visualization data
            route_details = {
                'origin': {
                    'lat': nearest_warehouse['Latitude'], 
                    'lng': nearest_warehouse['Longitude'],
                    'district': nearest_warehouse['District']
                },
                'destination': {
                    'lat': delivery_location['Latitude'], 
                    'lng': delivery_location['Longitude'],
                    'district': delivery_district
                }
            }

            return render_template('logistics.html', 
                districts=districts,
                map_key='AIzaSyBUembZbrAbmni90Rqwbd3drj5xBkRsF50',  # Your Google Maps API key
                result={
                    'nearest_warehouse': nearest_warehouse['District'],
                    'delivery_district': delivery_district,
                    'estimated_distance': round(estimated_distance, 2),
                    'estimated_time': round(estimated_time, 2),
                    'route_details': route_details,
                    'cost_breakdown': {
                        'distance_cost': round(distance_cost, 2),
                        'weight_cost': round(weight_cost, 2),
                        'quantity_cost': round(quantity_cost, 2),
                        'total_cost': round(total_delivery_cost, 2)
                    }
                })

        except Exception as e:
            flash(f'Error processing logistics: {str(e)}', 'danger')
            return render_template('logistics.html', districts=districts)

    return render_template('logistics.html', districts=districts)


@app.route('/')
def home():
    return render_template('home.html', title="Home")


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
