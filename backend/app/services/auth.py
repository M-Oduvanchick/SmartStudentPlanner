from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, data: RegisterRequest) -> User:
        username_exists = await self.users.get_by_username(data.username)
        email_exists = await self.users.get_by_email(str(data.email))
        if username_exists or email_exists:
            raise UserAlreadyExistsError

        try:
            user = await self.users.create(
                username=data.username,
                email=str(data.email),
                password_hash=hash_password(data.password),
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise UserAlreadyExistsError from error

        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_identifier(data.identifier)
        if user is None or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError

        return TokenResponse(access_token=create_access_token(user.id))
