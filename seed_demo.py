"""Create idempotent demo data for Parkora portfolio previews."""

from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import app, init_db
from models import db, ParkingLot, ParkingSpot, Reservation, User


DEMO_ACCOUNTS = [
    ("driver", "driver@parkora.local", "driver123"),
    ("visitor", "visitor@parkora.local", "visitor123"),
    ("commuter", "commuter@parkora.local", "commuter123"),
]


def ensure_user(username, email, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            is_admin=False,
        )
        db.session.add(user)
        db.session.flush()
    return user


def ensure_lot(name, address, pin_code, price, spot_count):
    lot = ParkingLot.query.filter_by(prime_location_name=name).first()
    if not lot:
        lot = ParkingLot(
            prime_location_name=name,
            address=address,
            pin_code=pin_code,
            price=price,
            maximum_number_of_spots=spot_count,
        )
        db.session.add(lot)
        db.session.flush()
        for number in range(1, spot_count + 1):
            db.session.add(ParkingSpot(lot_id=lot.id, spot_number=f"SPOT-{number}", status="A"))
        db.session.flush()
    return lot


def add_completed_visit(user, lot, days_ago, hours, cost):
    started_at = datetime.now() - timedelta(days=days_ago, hours=hours)
    finished_at = started_at + timedelta(hours=hours)
    spot = next(spot for spot in lot.spots if spot.status == "A")
    db.session.add(Reservation(
        spot_id=spot.id,
        user_id=user.id,
        parking_timestamp=started_at,
        leaving_timestamp=finished_at,
        parking_cost=lot.price,
        total_cost=cost,
    ))


def add_active_visit(user, lot, hours_ago):
    existing = Reservation.query.filter_by(user_id=user.id, leaving_timestamp=None).first()
    if existing:
        return

    spot = next((candidate for candidate in lot.spots if candidate.status == "A"), None)
    if not spot:
        return

    spot.status = "O"
    db.session.add(Reservation(
        spot_id=spot.id,
        user_id=user.id,
        parking_timestamp=datetime.now() - timedelta(hours=hours_ago),
        parking_cost=lot.price,
    ))


def seed_demo_data():
    init_db()

    with app.app_context():
        driver, visitor, commuter = [ensure_user(*account) for account in DEMO_ACCOUNTS]

        central = ensure_lot(
            "Central Square Garage",
            "12 MG Road, Bengaluru",
            "560001",
            80,
            12,
        )
        riverside = ensure_lot(
            "Riverside Parking Deck",
            "Marine Drive, Mumbai",
            "400020",
            110,
            10,
        )
        tech_park = ensure_lot(
            "Tech Park East",
            "Whitefield Main Road, Bengaluru",
            "560066",
            60,
            16,
        )
        db.session.commit()

        if not Reservation.query.filter_by(user_id=driver.id).first():
            add_completed_visit(driver, central, 95, 2, 160)
            add_completed_visit(driver, tech_park, 68, 4, 240)
            add_completed_visit(driver, central, 36, 3, 240)
            add_completed_visit(driver, riverside, 18, 2, 220)
            add_completed_visit(driver, tech_park, 6, 5, 300)

        add_active_visit(driver, central, 1)
        add_active_visit(commuter, riverside, 2)
        db.session.commit()

        print("Parkora demo data is ready.")
        print("Driver account: driver / driver123")
        print("Visitor account: visitor / visitor123")


if __name__ == "__main__":
    seed_demo_data()

