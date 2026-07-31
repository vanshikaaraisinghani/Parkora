from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, User, ParkingLot, ParkingSpot, Reservation
from forms import LoginForm, RegistrationForm, ParkingLotForm
from sqlalchemy import func
from config import Config


app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

from api import api_bp
app.register_blueprint(api_bp, url_prefix='/api')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Create tables and admin user
def init_db():
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        admin = User.query.filter_by(username=app.config['ADMIN_USERNAME']).first()
        if not admin:
            admin = User(
                username=app.config['ADMIN_USERNAME'],
                email=app.config['ADMIN_EMAIL'],
                password=generate_password_hash(app.config['ADMIN_PASSWORD']),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.context_processor
def inject_now():
    return {'now': datetime.now()}

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data),
            is_admin=False
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))
    
    parking_lots = ParkingLot.query.all()
    users = User.query.filter_by(is_admin=False).all()
    
    # overall stats
    total_lots     = len(parking_lots)
    total_spots    = db.session.query(ParkingSpot).count()
    occupied_spots = db.session.query(ParkingSpot).filter_by(status='O').count()
    available_spots= total_spots - occupied_spots
    total_revenue = db.session.query(func.coalesce(func.sum(Reservation.total_cost), 0)).scalar()
    occupancy_rate = round((occupied_spots / total_spots * 100), 1) if total_spots else 0
    
    stats = {
        'total_lots':     total_lots,
        'total_spots':    total_spots,
        'occupied_spots': occupied_spots,
        'available_spots':available_spots,
        'occupancy_rate': occupancy_rate,
        'total_revenue': float(total_revenue),
        'total_users': len(users)
    }
    
    # per-lot revenue
    lot_revenues = []
    for lot in parking_lots:
        revenue = db.session.query(
            func.coalesce(func.sum(Reservation.total_cost), 0)
        ).join(ParkingSpot, ParkingSpot.id == Reservation.spot_id
        ).filter(
            ParkingSpot.lot_id == lot.id,
            Reservation.leaving_timestamp.isnot(None)
        ).scalar()
        
        available = sum(1 for spot in lot.spots if spot.status == 'A')
        occupied = len(lot.spots) - available
        lot_revenues.append({
            'lot': lot,
            'revenue': float(revenue),
            'available': available,
            'occupied': occupied,
            'occupancy_rate': round((occupied / len(lot.spots) * 100), 1) if lot.spots else 0
        })

    busiest_lot = max(lot_revenues, key=lambda item: item['occupied'], default=None)
    
    return render_template(
        'admin_dashboard.html',
        parking_lots=parking_lots,
        users=users,
        stats=stats,
        lot_revenues=lot_revenues,
        busiest_lot=busiest_lot
    )

@app.route('/admin/parking-lot/create', methods=['GET', 'POST'])
@login_required
def create_parking_lot():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))
    
    form = ParkingLotForm()
    if form.validate_on_submit():
        parking_lot = ParkingLot(
            prime_location_name=form.prime_location_name.data,
            price=form.price.data,
            address=form.address.data,
            pin_code=form.pin_code.data,
            maximum_number_of_spots=form.maximum_number_of_spots.data
        )
        db.session.add(parking_lot)
        db.session.commit()
        
        # Create parking spots for this lot
        for i in range(form.maximum_number_of_spots.data):
            spot = ParkingSpot(
                lot_id=parking_lot.id,
                spot_number=f"SPOT-{i+1}",
                status='A'
            )
            db.session.add(spot)
        db.session.commit()
        
        flash('Parking lot created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('create_parking_lot.html', form=form)

@app.route('/admin/parking-lot/<int:lot_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_parking_lot(lot_id):
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))
    
    parking_lot = db.get_or_404(ParkingLot, lot_id)
    form = ParkingLotForm(obj=parking_lot)
    
    if form.validate_on_submit():
        old_spots = parking_lot.maximum_number_of_spots
        
        parking_lot.prime_location_name = form.prime_location_name.data
        parking_lot.price = form.price.data
        parking_lot.address = form.address.data
        parking_lot.pin_code = form.pin_code.data
        parking_lot.maximum_number_of_spots = form.maximum_number_of_spots.data
        
        # Handle spot number changes
        if form.maximum_number_of_spots.data > old_spots:
            # Add new spots
            for i in range(old_spots, form.maximum_number_of_spots.data):
                spot = ParkingSpot(
                    lot_id=parking_lot.id,
                    spot_number=f"SPOT-{i+1}",
                    status='A'
                )
                db.session.add(spot)
        elif form.maximum_number_of_spots.data < old_spots:
            # Remove extra spots (only if they are available)
            spots_to_remove = ParkingSpot.query.filter_by(
                lot_id=parking_lot.id, 
                status='A'
            ).order_by(ParkingSpot.id.desc()).limit(old_spots - form.maximum_number_of_spots.data).all()
            
            if len(spots_to_remove) < (old_spots - form.maximum_number_of_spots.data):
                flash('Cannot reduce spots. Some spots are occupied.', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            for spot in spots_to_remove:
                db.session.delete(spot)
        
        db.session.commit()
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_parking_lot.html', form=form, parking_lot=parking_lot)

@app.route('/admin/parking-lot/<int:lot_id>/delete', methods=['POST'])
@login_required
def delete_parking_lot(lot_id):
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))
    
    parking_lot = db.get_or_404(ParkingLot, lot_id)
    
    # Check if all spots are available
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
    if occupied_spots > 0:
        flash('Cannot delete parking lot. Some spots are occupied.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Delete all spots and the lot
    ParkingSpot.query.filter_by(lot_id=lot_id).delete()
    db.session.delete(parking_lot)
    db.session.commit()
    
    flash('Parking lot deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/parking-lot/<int:lot_id>/spots')
@login_required
def view_parking_spots(lot_id):
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))
    
    parking_lot = db.get_or_404(ParkingLot, lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    
    # Get reservation details for occupied spots
    spot_details = []
    for spot in spots:
        if spot.status == 'O':
            reservation = Reservation.query.filter_by(
                spot_id=spot.id,
                leaving_timestamp=None
            ).first()
            spot_details.append({
                'spot': spot,
                'reservation': reservation,
                'user': reservation.user if reservation else None
            })
        else:
            spot_details.append({
                'spot': spot,
                'reservation': None,
                'user': None
            })
    
    return render_template('view_parking_spots.html', 
                         parking_lot=parking_lot, 
                         spot_details=spot_details)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get user's current reservation
    current_reservation = Reservation.query.filter_by(
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()
    
    # Get user's parking history
    parking_history = Reservation.query.filter_by(
        user_id=current_user.id
    ).filter(Reservation.leaving_timestamp.isnot(None)).order_by(
        Reservation.parking_timestamp.desc()
    ).all()

    total_spent = sum(reservation.total_cost or 0 for reservation in parking_history)
    total_minutes = sum(
        (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 60
        for reservation in parking_history
    )
    average_duration_minutes = round(total_minutes / len(parking_history)) if parking_history else 0

    location_visits = {}
    for reservation in parking_history:
        location_name = reservation.spot.lot.prime_location_name
        location_visits[location_name] = location_visits.get(location_name, 0) + 1
    favorite_location = max(location_visits, key=location_visits.get) if location_visits else None

    user_stats = {
        'total_visits': len(parking_history),
        'total_spent': total_spent,
        'average_duration_minutes': average_duration_minutes,
        'favorite_location': favorite_location
    }
    
    return render_template('user_dashboard.html', 
                         current_reservation=current_reservation,
                         parking_history=parking_history,
                         user_stats=user_stats)

@app.route('/user/book-parking')
@login_required
def book_parking():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Check if user already has an active reservation
    active_reservation = Reservation.query.filter_by(
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()
    
    if active_reservation:
        flash('You already have an active parking reservation.', 'warning')
        return redirect(url_for('user_dashboard'))
    
    # Get all parking lots with available spots
    parking_lots = []
    all_lots = ParkingLot.query.all()
    search_query = request.args.get('q', '').strip()
    
    for lot in all_lots:
        if search_query and search_query.lower() not in ' '.join([
            lot.prime_location_name,
            lot.address,
            lot.pin_code
        ]).lower():
            continue

        available_spots = ParkingSpot.query.filter_by(
            lot_id=lot.id,
            status='A'
        ).count()
        if available_spots > 0:
            total_spots = len(lot.spots)
            availability_rate = (available_spots / total_spots) if total_spots else 0
            parking_lots.append({
                'lot': lot,
                'available_spots': available_spots,
                'occupied_spots': total_spots - available_spots,
                'availability_rate': availability_rate,
                'is_recommended': False
            })

    # Smart recommendation: prioritize availability, then lower hourly price.
    parking_lots.sort(key=lambda item: (-item['availability_rate'], item['lot'].price))
    if parking_lots:
        parking_lots[0]['is_recommended'] = True
    
    return render_template('book_parking.html', parking_lots=parking_lots, search_query=search_query)

@app.route('/user/book-parking/<int:lot_id>', methods=['POST'])
@login_required
def confirm_booking(lot_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get first available spot in the lot
    available_spot = ParkingSpot.query.filter_by(
        lot_id=lot_id,
        status='A'
    ).first()
    
    if not available_spot:
        flash('No available spots in this parking lot.', 'danger')
        return redirect(url_for('book_parking'))
    
    # Create reservation
    reservation = Reservation(
        spot_id=available_spot.id,
        user_id=current_user.id,
        parking_timestamp=datetime.now(),
        parking_cost=available_spot.lot.price
    )
    
    # Update spot status
    available_spot.status = 'O'
    
    db.session.add(reservation)
    db.session.commit()
    
    flash('Parking spot booked successfully!', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/admin/parking-lot/<int:lot_id>/spot/<int:spot_id>/delete', methods=['POST'])
@login_required
def delete_parking_spot(lot_id, spot_id):
    # admin-only
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))

    spot = ParkingSpot.query.filter_by(id=spot_id, lot_id=lot_id).first_or_404()
    if spot.status != 'A':
        flash('Cannot delete an occupied spot.', 'danger')
    else:
        db.session.delete(spot)
        db.session.flush()

        parking_lot = db.get_or_404(ParkingLot, lot_id)
        remaining_spots = ParkingSpot.query.filter_by(lot_id=lot_id).order_by(ParkingSpot.id).all()
        for index, remaining_spot in enumerate(remaining_spots, start=1):
            remaining_spot.spot_number = f'SPOT-{index}'
        parking_lot.maximum_number_of_spots = len(remaining_spots)

        db.session.commit()
        flash(f'Spot {spot.spot_number} deleted.', 'success')
    return redirect(url_for('view_parking_spots', lot_id=lot_id))

@app.route('/admin/parking-lot/<int:lot_id>/spot/<int:spot_id>')
@login_required
def view_parking_spot_detail(lot_id, spot_id):
    # admin-only
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))

    spot = ParkingSpot.query.filter_by(id=spot_id, lot_id=lot_id).first_or_404()
    if spot.status != 'O':
        flash('Spot is not occupied.', 'warning')
        return redirect(url_for('view_parking_spots', lot_id=lot_id))

    # fetch the active reservation
    reservation = Reservation.query.filter_by(
        spot_id=spot.id,
        leaving_timestamp=None
    ).first()
    if not reservation:
        flash('No active reservation found for this spot.', 'warning')
        return redirect(url_for('view_parking_spots', lot_id=lot_id))

    user = reservation.user
    return render_template(
        'spot_detail.html',
        spot=spot,
        reservation=reservation,
        user=user
    )



@app.route('/user/release-parking', methods=['POST'])
@login_required
def release_parking():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get active reservation
    reservation = Reservation.query.filter_by(
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()
    
    if not reservation:
        flash('No active parking reservation found.', 'warning')
        return redirect(url_for('user_dashboard'))
    
    # Update reservation
    reservation.leaving_timestamp = datetime.now()
    
    # Calculate total cost
    duration = reservation.leaving_timestamp - reservation.parking_timestamp
    hours = duration.total_seconds() / 3600
    # Round up to nearest hour
    hours = int(hours) + (1 if hours % 1 > 0 else 0)
    reservation.total_cost = hours * reservation.parking_cost
    
    # Update spot status
    spot = db.session.get(ParkingSpot, reservation.spot_id)
    spot.status = 'A'
    
    db.session.commit()
    
    flash(f'Parking released successfully! Total cost: ₹{reservation.total_cost}', 'success')
    return redirect(url_for('user_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=app.config['DEBUG'])
