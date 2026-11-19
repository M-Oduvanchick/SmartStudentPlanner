from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.tasks import TaskNotFoundError, TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def task_not_found(error: TaskNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Task not found",
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TaskResponse:
    task = await TaskService(session).create(current_user.id, data)
    return TaskResponse.model_validate(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[TaskResponse]:
    tasks = await TaskService(session).list(current_user.id)
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TaskResponse:
    try:
        task = await TaskService(session).get(task_id, current_user.id)
    except TaskNotFoundError as error:
        raise task_not_found(error) from error
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TaskResponse:
    try:
        task = await TaskService(session).update(task_id, current_user.id, data)
    except TaskNotFoundError as error:
        raise task_not_found(error) from error
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    try:
        await TaskService(session).delete(task_id, current_user.id)
    except TaskNotFoundError as error:
        raise task_not_found(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
