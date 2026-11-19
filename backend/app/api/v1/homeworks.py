from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.homework import HomeworkCreate, HomeworkResponse, HomeworkUpdate
from app.services.homeworks import HomeworkNotFoundError, HomeworkService

router = APIRouter(prefix="/homeworks", tags=["homeworks"])


def homework_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Homework not found",
    )


@router.post("", response_model=HomeworkResponse, status_code=status.HTTP_201_CREATED)
async def create_homework(
    data: HomeworkCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> HomeworkResponse:
    homework = await HomeworkService(session).create(current_user.id, data)
    return HomeworkResponse.model_validate(homework)


@router.get("", response_model=list[HomeworkResponse])
async def list_homeworks(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[HomeworkResponse]:
    homeworks = await HomeworkService(session).list(current_user.id)
    return [HomeworkResponse.model_validate(homework) for homework in homeworks]


@router.get("/{homework_id}", response_model=HomeworkResponse)
async def get_homework(
    homework_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> HomeworkResponse:
    try:
        homework = await HomeworkService(session).get(homework_id, current_user.id)
    except HomeworkNotFoundError as error:
        raise homework_not_found() from error
    return HomeworkResponse.model_validate(homework)


@router.patch("/{homework_id}", response_model=HomeworkResponse)
async def update_homework(
    homework_id: UUID,
    data: HomeworkUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> HomeworkResponse:
    try:
        homework = await HomeworkService(session).update(homework_id, current_user.id, data)
    except HomeworkNotFoundError as error:
        raise homework_not_found() from error
    return HomeworkResponse.model_validate(homework)


@router.delete("/{homework_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_homework(
    homework_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    try:
        await HomeworkService(session).delete(homework_id, current_user.id)
    except HomeworkNotFoundError as error:
        raise homework_not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
