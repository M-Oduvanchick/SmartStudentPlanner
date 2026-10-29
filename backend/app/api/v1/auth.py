from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DatabaseSession
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth import (
    AuthService,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: RegisterRequest, session: DatabaseSession) -> UserResponse:
    try:
        user = await AuthService(session).register(data)
    except UserAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists",
        ) from error
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: DatabaseSession) -> TokenResponse:
    try:
        return await AuthService(session).login(data)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
