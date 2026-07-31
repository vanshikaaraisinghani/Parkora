"""JSON API resources used by Parkora and available for integrations."""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, ParkingLot, ParkingSpot, Reservation, User
from datetime import datetime

api_bp = Blueprint('api', __name__)

# API Helper Functions
def check_admin():
    """Check if current user is admin"""
    if not current_user.is_authenticated or not current_user.is_admin:
        return False
    return True

# Parking Lots API
@api_bp.route('/parking-lots', methods=['GET'])
def get_parking_lots():
    """Get all parking lots with availability info"""
    parking_lots = ParkingLot.query.all()
    result = []
    
    for lot in parking_lots:
        available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        result.append({
            'id': lot.id,
            'name': lot.prime_location_name,
            'address': lot.address,
            'pin_code': lot.pin_code,
            'price_per_hour': lot.price,
            'total_spots': lot.maximum_number_of_spots,
            'available_spots': available_spots,
            'occupied_spots': lot.maximum_number_of_spots - available_spots
        })
    
    return jsonify({'parking_lots': result}), 200

@api_bp.route('/parking-lots/<int:lot_id>', methods=['GET'])
def get_parking_lot(lot_id):
    """Get specific parking lot details"""
    lot = db.get_or_404(ParkingLot, lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    
    spots_data = []
    for spot in spots:
        spot_info = {
            'id': spot.id,
            'spot_number': spot.spot_number,
            'status': 'Available' if spot.status == 'A' else 'Occupied'
        }
        
        if spot.status == 'O':
            reservation = Reservation.query.filter_by(spot_id=spot.id, leaving_timestamp=None).first()
            if reservation:
                spot_info['parked_since'] = reservation.parking_timestamp.isoformat()
        
        spots_data.append(spot_info)
    
    return jsonify({
        'id': lot.id,
        'name': lot.prime_location_name,
        'address': lot.address,
        'pin_code': lot.pin_code,
        'price_per_hour': lot.price,
        'spots': spots_data
    }), 200

@api_bp.route('/parking-lots', methods=['POST'])
@login_required
def create_parking_lot_api():
    """Create a new parking lot (Admin only)"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json(silent=True) or {}
    
    # Validate required fields
    required_fields = ['prime_location_name', 'price', 'address', 'pin_code', 'maximum_number_of_spots']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Create parking lot
    parking_lot = ParkingLot(
        prime_location_name=data['prime_location_name'],
        price=float(data['price']),
        address=data['address'],
        pin_code=data['pin_code'],
        maximum_number_of_spots=int(data['maximum_number_of_spots'])
    )
    db.session.add(parking_lot)
    db.session.commit()
    
    # Create parking spots
    for i in range(parking_lot.maximum_number_of_spots):
        spot = ParkingSpot(
            lot_id=parking_lot.id,
            spot_number=f"SPOT-{i+1}",
            status='A'
        )
        db.session.add(spot)
    db.session.commit()
    
    return jsonify({
        'message': 'Parking lot created successfully',
        'id': parking_lot.id
    }), 201

# User Reservations API
@api_bp.route('/reservations/current', methods=['GET'])
@login_required
def get_current_reservation():
    """Get current user's active reservation"""
    reservation = Reservation.query.filter_by(
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()
    
    if not reservation:
        return jsonify({'message': 'No active reservation'}), 200
    
    duration = datetime.now() - reservation.parking_timestamp
    hours = int(duration.total_seconds() / 3600)
    minutes = int((duration.total_seconds() % 3600) / 60)
    
    return jsonify({
        'id': reservation.id,
        'parking_lot': reservation.spot.lot.prime_location_name,
        'spot_number': reservation.spot.spot_number,
        'parked_since': reservation.parking_timestamp.isoformat(),
        'duration': f'{hours}h {minutes}m',
        'hourly_rate': reservation.parking_cost,
        'estimated_cost': (hours + 1) * reservation.parking_cost  # Round up to next hour
    }), 200

@api_bp.route('/reservations/book/<int:lot_id>', methods=['POST'])
@login_required
def book_parking_api(lot_id):
    """Book a parking spot in specified lot"""
    if current_user.is_admin:
        return jsonify({'error': 'Administrator accounts cannot book parking'}), 403

    # Check for existing reservation
    existing = Reservation.query.filter_by(
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()
    
    if existing:
        return jsonify({'error': 'You already have an active reservation'}), 400
    
    # Find available spot
    available_spot = ParkingSpot.query.filter_by(
        lot_id=lot_id,
        status='A'
    ).first()
    
    if not available_spot:
        return jsonify({'error': 'No available spots in this parking lot'}), 400
    
    # Create reservation
    reservation = Reservation(
        spot_id=available_spot.id,
        user_id=current_user.id,
        parking_timestamp=datetime.now(),
        parking_cost=available_spot.lot.price
    )
    
    available_spot.status = 'O'
    
    db.session.add(reservation)
    db.session.commit()
    
    return jsonify({
        'message': 'Parking spot booked successfully',
        'reservation_id': reservation.id,
        'spot_number': available_spot.spot_number,
        'parking_lot': available_spot.lot.prime_location_name
    }), 201

@api_bp.route('/reservations/release', methods=['POST'])
@login_required
def release_parking_api():
    """Release current parking reservation"""
    reservation = Reservation.query.filter_by(
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()
    
    if not reservation:
        return jsonify({'error': 'No active reservation found'}), 400
    
    # Update reservation
    reservation.leaving_timestamp = datetime.now()
    
    # Calculate total cost
    duration = reservation.leaving_timestamp - reservation.parking_timestamp
    hours = duration.total_seconds() / 3600
    hours = int(hours) + (1 if hours % 1 > 0 else 0)  # Round up
    reservation.total_cost = hours * reservation.parking_cost
    
    # Update spot status
    spot = db.session.get(ParkingSpot, reservation.spot_id)
    spot.status = 'A'
    
    db.session.commit()
    
    return jsonify({
        'message': 'Parking released successfully',
        'duration_hours': hours,
        'total_cost': reservation.total_cost
    }), 200

# Statistics API
@api_bp.route('/stats/overview', methods=['GET'])
@login_required
def get_stats():
    """Get parking statistics (Admin only)"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    total_users = User.query.filter_by(is_admin=False).count()
    
    # Get today's revenue
    today = datetime.now().date()
    today_revenue = db.session.query(db.func.sum(Reservation.total_cost)).filter(
        db.func.date(Reservation.leaving_timestamp) == today
    ).scalar() or 0
    
    return jsonify({
        'total_parking_lots': total_lots,
        'total_spots': total_spots,
        'occupied_spots': occupied_spots,
        'available_spots': total_spots - occupied_spots,
        'total_users': total_users,
        'today_revenue': float(today_revenue)
    }), 200

@api_bp.route('/stats/user', methods=['GET'])
@login_required
def get_user_stats():
    """Get current user's parking statistics"""
    total_parkings = Reservation.query.filter_by(user_id=current_user.id).count()
    
    total_spent = db.session.query(db.func.sum(Reservation.total_cost)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    
    # Get favorite parking lot
    favorite_lot = db.session.query(
        ParkingLot.prime_location_name,
        db.func.count(Reservation.id).label('count')
    ).join(
        ParkingSpot, ParkingSpot.lot_id == ParkingLot.id
    ).join(
        Reservation, Reservation.spot_id == ParkingSpot.id
    ).filter(
        Reservation.user_id == current_user.id
    ).group_by(
        ParkingLot.id
    ).order_by(
        db.desc('count')
    ).first()
    
    return jsonify({
        'total_parkings': total_parkings,
        'total_spent': float(total_spent),
        'favorite_location': favorite_lot[0] if favorite_lot else None
    }), 200
