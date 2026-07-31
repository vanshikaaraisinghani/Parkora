# Parkora

> **Find space. Save time.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-4%20passing-22C55E)](#testing)

Parkora is a multi-user parking management platform that connects drivers with available parking and gives administrators a live view of their parking network. Drivers can discover the best lot, reserve an automatically allocated spot, monitor time and estimated cost, and review their parking history. Administrators can manage locations and capacity while tracking occupancy, users, and completed revenue.

## Preview

| Landing page | Smart lot finder |
| --- | --- |
| ![Parkora landing page](docs/screenshots/landing-page.png) | ![Parkora smart lot finder](docs/screenshots/smart-lot-finder.png) |

| Driver dashboard | Operations dashboard |
| --- | --- |
| ![Parkora driver dashboard](docs/screenshots/driver-dashboard.png) | ![Parkora administrator dashboard](docs/screenshots/admin-dashboard.png) |

> Keep the `docs/screenshots` folder in the repository. GitHub uses these relative paths to display the preview images.

## About Parkora 

- **Smart recommendations:** matching lots are ranked by availability percentage and then by hourly price, with the strongest option marked as the best match.
- **Live parking meter:** an active reservation shows its continuously updating duration and estimated cost.
- **Personal driver insights:** completed visits, total spend, average parking duration, and favorite location are calculated from real usage history.
- **Operations-focused analytics:** administrators see network occupancy, completed revenue, registered drivers, the busiest location, and per-lot performance.
- **Search that reflects real decisions:** drivers can search by location, address, or PIN code; administrators can quickly filter their lot table.
- **Integration-ready API:** the Flask blueprint exposes availability, reservations, and role-aware statistics as JSON.
- **Portfolio-ready engineering:** environment variables, reproducible demo data, privacy-conscious API responses, POST-based state changes, and automated workflow tests are included.


## Application flow

```mermaid
flowchart LR
    V[Visitor] --> A{Account type}
    A -->|Driver| S[Search and compare lots]
    S --> B[Book first available spot]
    B --> M[Monitor live time and cost]
    M --> R[Release spot and save bill]
    R --> H[Review history and insights]
    A -->|Administrator| L[Manage lots and spots]
    L --> O[Monitor occupancy and users]
    O --> P[Review revenue and performance]
```

## Data model

```mermaid
erDiagram
    USER ||--o{ RESERVATION : makes
    PARKING_LOT ||--|{ PARKING_SPOT : contains
    PARKING_SPOT ||--o{ RESERVATION : receives

    USER {
        int id PK
        string username UK
        string email UK
        string password
        boolean is_admin
    }
    PARKING_LOT {
        int id PK
        string prime_location_name
        float price
        string address
        string pin_code
        int maximum_number_of_spots
    }
    PARKING_SPOT {
        int id PK
        int lot_id FK
        string spot_number
        string status
    }
    RESERVATION {
        int id PK
        int spot_id FK
        int user_id FK
        datetime parking_timestamp
        datetime leaving_timestamp
        float parking_cost
        float total_cost
    }
```

## Technology stack

- **Backend:** Python, Flask, Flask-Login, Flask-WTF
- **Data layer:** SQLite, Flask-SQLAlchemy
- **Frontend:** Jinja, Bootstrap 5, custom CSS, Chart.js
- **Validation and security:** WTForms, Werkzeug password hashing, CSRF tokens
- **Quality:** Python `unittest`, isolated in-memory test database



## Project note

Parkora was developed from a multi-user parking-management brief and then expanded into a portfolio-ready product with a distinct brand, recommendation logic, live session tracking, personalized insights, operational analytics, a connected API, reproducible demo data, and automated tests.

