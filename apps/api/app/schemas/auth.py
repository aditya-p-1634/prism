from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.enums import RoleEnum

class LoginRequestDTO(BaseModel):
    email: EmailStr
    password: str

class TokenDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum
    full_name: str

class UserDTO(BaseModel):
    id: str
    email: str
    full_name: str
    role: RoleEnum
    is_active: bool
