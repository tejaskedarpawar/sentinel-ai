from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="sentinel123")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = None
    role: Optional[str] = "analyst"


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with username and password, returning an access token and user profile."""
    username = payload.username.strip()
    user = db.query(User).filter(User.username.ilike(username)).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    token_data = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "name": user.full_name,
    }
    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently logged in user."""
    return current_user


@router.post("/logout")
def logout():
    """Client-side token invalidation confirmation."""
    return {"status": "ok", "message": "Successfully logged out"}


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin-only: list all SOC system users."""
    return db.query(User).order_by(User.id.asc()).all()


@router.post("/register", response_model=UserResponse)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin-only: register a new analyst or operator."""
    username = payload.username.strip().lower()
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' already taken.",
        )

    role = payload.role if payload.role in ("admin", "analyst", "viewer") else "analyst"
    new_user = User(
        username=username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        email=payload.email.strip() if payload.email else None,
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
