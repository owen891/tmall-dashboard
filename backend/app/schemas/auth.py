from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime


UserRole = Literal["admin", "manager", "viewer"]


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    email: Optional[str] = None
    is_active: bool = True
    role: UserRole = "viewer"


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if v and v.strip() != v:
            raise ValueError('密码不能包含前后空格')
        return v


class UserUpdate(BaseModel):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)
