import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .db import Base, engine, get_db
from .models import User, Slot, Booking
from .schemas import (
    UserRegister,
    Token,
    DeviceSlotsPayload,
    SlotOut,
    BookingCreate,
    BookingOut
)
from .auth import (
    hash_pw,
    verify_pw,
    create_token,
    get_user_id_from_token
)

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

DEVICE_KEY = os.getenv("DEVICE_KEY", "esp32_secret_key")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# -------------------------------------------------
# FASTAPI APP
# -------------------------------------------------

app = FastAPI(title="Smart Parking System")

# -------------------------------------------------
# SERVE WEBSITE
# -------------------------------------------------

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


@app.get("/")
def homepage():
    return FileResponse(str(WEB_DIR / "index.html"))


# -------------------------------------------------
# STARTUP: CREATE TABLES + SLOTS
# -------------------------------------------------

@app.on_event("startup")
def startup():

    Base.metadata.create_all(bind=engine)

    db = next(get_db())

    try:

        # create slots if not exist
        for i in range(1, 5):

            slot = db.query(Slot).filter(Slot.id == i).first()

            if not slot:
                db.add(
                    Slot(
                        id=i,
                        name=f"S{i}",
                        sensor_occupied=False,
                        updated_at=datetime.utcnow()
                    )
                )

        db.commit()

    finally:
        db.close()


# -------------------------------------------------
# SLOT STATE LOGIC
# -------------------------------------------------

def compute_effective_state(db: Session, slot_id: int):

    now = datetime.utcnow()

    # expire finished bookings
    expired = db.query(Booking).filter(
        Booking.status == "APPROVED",
        Booking.end_time <= now
    ).all()

    for b in expired:
        b.status = "EXPIRED"

    if expired:
        db.commit()

    # check active booking
    active = db.query(Booking).filter(
        Booking.slot_id == slot_id,
        Booking.status == "APPROVED",
        Booking.start_time <= now,
        Booking.end_time >= now
    ).first()

    if active:
        return "RESERVED"

    # check pending booking
    pending = db.query(Booking).filter(
        Booking.slot_id == slot_id,
        Booking.status == "PENDING"
    ).first()

    if pending:
        return "PENDING"

    return "FREE"


# -------------------------------------------------
# AUTH
# -------------------------------------------------

@app.post("/api/auth/register", response_model=Token)
def register(user: UserRegister, db: Session = Depends(get_db)):

    existing = db.query(User).filter(User.username == user.username).first()

    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    u = User(
        username=user.username,
        password_hash=hash_pw(user.password)
    )

    db.add(u)
    db.commit()
    db.refresh(u)

    token = create_token(u.id)

    return {"access_token": token}


@app.post("/api/auth/login", response_model=Token)
def login(user: UserRegister, db: Session = Depends(get_db)):

    u = db.query(User).filter(User.username == user.username).first()

    if not u:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_pw(user.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(u.id)

    return {"access_token": token}


# -------------------------------------------------
# DEVICE (ESP32)
# -------------------------------------------------

@app.post("/api/device/slots")
def update_slots(
    payload: DeviceSlotsPayload,
    x_device_key: str = Header(default=""),
    db: Session = Depends(get_db)
):

    if x_device_key != DEVICE_KEY:
        raise HTTPException(status_code=401, detail="Invalid device key")

    for s in payload.slots:

        if s.slot_id not in (1, 2, 3, 4):
            continue

        slot = db.query(Slot).filter(Slot.id == s.slot_id).first()

        if slot:
            slot.sensor_occupied = s.occupied
            slot.updated_at = datetime.utcnow()

    db.commit()

    return {"ok": True}


# -------------------------------------------------
# GET SLOT STATUS
# -------------------------------------------------

@app.get("/api/slots", response_model=list[SlotOut])
def get_slots(db: Session = Depends(get_db)):

    slots = db.query(Slot).order_by(Slot.id).all()

    result = []

    for s in slots:

        state = compute_effective_state(db, s.id)

        if s.sensor_occupied:
            state = "OCCUPIED"

        result.append(
            SlotOut(
                id=s.id,
                name=s.name,
                sensor_occupied=s.sensor_occupied,
                effective_state=state,
                updated_at=s.updated_at
            )
        )

    return result


# -------------------------------------------------
# CREATE BOOKING
# -------------------------------------------------

@app.post("/api/bookings", response_model=BookingOut)
def create_booking(
    data: BookingCreate,
    user_id: int = Depends(get_user_id_from_token),
    db: Session = Depends(get_db)
):

    if data.slot_id not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Invalid slot")

    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="Invalid time range")

    # prevent overlap with approved booking
    overlap = db.query(Booking).filter(
        Booking.slot_id == data.slot_id,
        Booking.status == "APPROVED",
        and_(
            Booking.start_time < data.end_time,
            Booking.end_time > data.start_time
        )
    ).first()

    if overlap:
        raise HTTPException(status_code=409, detail="Slot already reserved")

    booking = Booking(
        slot_id=data.slot_id,
        user_id=user_id,
        start_time=data.start_time,
        end_time=data.end_time,
        status="PENDING"
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return booking


# -------------------------------------------------
# USER BOOKINGS
# -------------------------------------------------

@app.get("/api/bookings/me", response_model=list[BookingOut])
def my_bookings(
    user_id: int = Depends(get_user_id_from_token),
    db: Session = Depends(get_db)
):

    bookings = db.query(Booking).filter(
        Booking.user_id == user_id
    ).order_by(Booking.created_at.desc()).all()

    return bookings


# -------------------------------------------------
# ADMIN SECURITY
# -------------------------------------------------

def admin_guard(
    x_admin_user: str = Header(default=""),
    x_admin_pass: str = Header(default="")
):

    if x_admin_user != ADMIN_USERNAME or x_admin_pass != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Admin authentication failed")


# -------------------------------------------------
# ADMIN GET BOOKINGS
# -------------------------------------------------

@app.get("/api/admin/bookings", response_model=list[BookingOut])
def admin_list(
    status: str = "PENDING",
    db: Session = Depends(get_db),
    _=Depends(admin_guard)
):

    bookings = db.query(Booking).filter(
        Booking.status == status
    ).order_by(Booking.created_at.desc()).all()

    return bookings


# -------------------------------------------------
# ADMIN APPROVE
# -------------------------------------------------

@app.post("/api/admin/bookings/{booking_id}/approve")
def approve_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _=Depends(admin_guard)
):

    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "PENDING":
        raise HTTPException(status_code=400, detail="Booking not pending")

    booking.status = "APPROVED"

    db.commit()

    return {"ok": True}


# -------------------------------------------------
# ADMIN REJECT
# -------------------------------------------------

@app.post("/api/admin/bookings/{booking_id}/reject")
def reject_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _=Depends(admin_guard)
):

    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "PENDING":
        raise HTTPException(status_code=400, detail="Booking not pending")

    booking.status = "REJECTED"

    db.commit()

    return {"ok": True}