from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True)  # 1..4
    name = Column(String(10), unique=True, nullable=False)  # S1..S4
    sensor_occupied = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")  
    # PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    slot = relationship("Slot")
    user = relationship("User")