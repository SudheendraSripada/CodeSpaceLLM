from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, create_access_token, verify_password
from app.config import Settings
from app.dependencies import get_current_user, get_db, get_settings
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.services.user_service import create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    if settings.auth_provider == "supabase":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use Supabase Auth for registration")
    if not settings.allow_signups:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signups are disabled")
    user = create_user(db, payload.email, payload.password, role="user")
    return _auth_response(user, settings)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    if settings.auth_provider == "supabase":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use Supabase Auth for login")
    row = get_user_by_email(db, payload.email)
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user = CurrentUser(id=row["id"], email=row["email"], role=row["role"])
    return _auth_response(user, settings)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


def _auth_response(user: CurrentUser, settings: Settings) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user, settings),
        user=UserOut(id=user.id, email=user.email, role=user.role),
    )
