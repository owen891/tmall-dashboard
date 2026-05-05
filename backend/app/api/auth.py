from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_current_user,
    require_role,
)
from app.core.config import settings
from app.models import User
from app.schemas.auth import (
    UserCreate,
    UserResponse,
    UserUpdate,
    Token,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        is_active=user_data.is_active,
        role=user_data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.email is not None:
        user.email = user_data.email
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.role is not None:
        user.role = user_data.role
    if user_data.password is not None:
        user.hashed_password = get_password_hash(user_data.password)

    db.commit()
    db.refresh(user)
    return user


@router.post("/init-admin")
def init_admin(db: Session = Depends(get_db)):
    """Initialize default admin account - only for first setup"""
    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin already exists")

    admin_user = User(
        username="admin",
        email="admin@haibeihai.com",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        role="admin",
    )
    db.add(admin_user)

    manager_user = User(
        username="manager",
        email="manager@haibeihai.com",
        hashed_password=get_password_hash("manager123"),
        is_active=True,
        role="manager",
    )
    db.add(manager_user)

    viewer_user = User(
        username="viewer",
        email="viewer@haibeihai.com",
        hashed_password=get_password_hash("viewer123"),
        is_active=True,
        role="viewer",
    )
    db.add(viewer_user)

    db.commit()
    return {
        "message": "Default users created. Please change default passwords immediately.",
        "users": [
            {"username": "admin", "role": "admin"},
            {"username": "manager", "role": "manager"},
            {"username": "viewer", "role": "viewer"},
        ],
    }
