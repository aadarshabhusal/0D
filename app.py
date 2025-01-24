from flask import Flask, render_template, session, redirect, url_for

app = Flask(__name__)
app.config['SECRET_KEY'] = '99875e40247d4d65b01363aa3db01cc2'

@app.route('/')
def home():
    return render_template('home.html', title="Home")

@app.route('/warehouses')
def warehouses():
    return render_template('warehouses.html', title="Warehouses")

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
    # Placeholder logic for login
    if 'user' in session:
        return redirect(url_for('home'))
    return render_template('login.html', title="Login")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Placeholder logic for signup
    return render_template('signup.html', title="Sign Up")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', title="Dashboard")

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)
