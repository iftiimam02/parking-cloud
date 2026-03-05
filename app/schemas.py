from pydantic import BaseModel
from datetime import datetime
from typing import List

class UserRegister(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class SlotUpdate(BaseModel):
    slot_id: int
    occupied: bool

class DeviceSlotsPayload(BaseModel):
    device_id: str
    slots: List[SlotUpdate]

class SlotOut(BaseModel):
    id: int
    name: str
    sensor_occupied: bool
    effective_state: str
    updated_at: datetime

class BookingCreate(BaseModel):
    slot_id: int
    start_time: datetime
    end_time: datetime

class BookingOut(BaseModel):
    id: int
    slot_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime