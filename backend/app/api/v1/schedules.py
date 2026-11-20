from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, PnrpuClient
from app.integrations.pnrpu import PnrpuScheduleError
from app.schemas.schedule import (
    ScheduleDocumentResponse,
    ScheduleImportRequest,
    ScheduleResponse,
)
from app.services.schedules import (
    ScheduleDocumentNotFoundError,
    ScheduleNotSelectedError,
    ScheduleService,
)

router = APIRouter(prefix="/schedule", tags=["schedule"])


def schedule_not_selected() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Schedule is not selected",
    )


def schedule_source_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="PNRPU schedule source is unavailable or returned invalid data",
    )


@router.get("/documents", response_model=list[ScheduleDocumentResponse])
async def search_schedule_documents(
    group_name: Annotated[str, Query(min_length=2, max_length=100)],
    current_user: CurrentUser,
    session: DatabaseSession,
    source: PnrpuClient,
) -> list[ScheduleDocumentResponse]:
    del current_user
    try:
        documents = await ScheduleService(session).search_documents(group_name, source)
    except PnrpuScheduleError as error:
        raise schedule_source_error() from error
    return [
        ScheduleDocumentResponse(
            title=document.title,
            url=document.url,
            filename=document.filename,
        )
        for document in documents
    ]


@router.post(
    "/import",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_schedule(
    data: ScheduleImportRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    source: PnrpuClient,
) -> ScheduleResponse:
    try:
        schedule = await ScheduleService(session).import_for_user(current_user, data, source)
    except ScheduleDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule document was not found for this group",
        ) from error
    except PnrpuScheduleError as error:
        raise schedule_source_error() from error
    return ScheduleResponse.model_validate(schedule)


@router.get("", response_model=ScheduleResponse)
async def get_schedule(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ScheduleResponse:
    try:
        schedule = await ScheduleService(session).get_current(current_user)
    except ScheduleNotSelectedError as error:
        raise schedule_not_selected() from error
    return ScheduleResponse.model_validate(schedule)


@router.post("/refresh", response_model=ScheduleResponse)
async def refresh_schedule(
    current_user: CurrentUser,
    session: DatabaseSession,
    source: PnrpuClient,
) -> ScheduleResponse:
    try:
        schedule = await ScheduleService(session).refresh_current(current_user, source)
    except ScheduleNotSelectedError as error:
        raise schedule_not_selected() from error
    except PnrpuScheduleError as error:
        raise schedule_source_error() from error
    return ScheduleResponse.model_validate(schedule)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_schedule(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    await ScheduleService(session).clear_current(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
