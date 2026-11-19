from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.services.notes import NoteNotFoundError, NoteService, NoteTargetNotFoundError

router = APIRouter(prefix="/notes", tags=["notes"])


def note_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Note not found",
    )


def note_target_not_found(error: NoteTargetNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    data: NoteCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> NoteResponse:
    try:
        note = await NoteService(session).create(current_user.id, data)
    except NoteTargetNotFoundError as error:
        raise note_target_not_found(error) from error
    return NoteResponse.model_validate(note)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[NoteResponse]:
    notes = await NoteService(session).list(current_user.id)
    return [NoteResponse.model_validate(note) for note in notes]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> NoteResponse:
    try:
        note = await NoteService(session).get(note_id, current_user.id)
    except NoteNotFoundError as error:
        raise note_not_found() from error
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    data: NoteUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> NoteResponse:
    try:
        note = await NoteService(session).update(note_id, current_user.id, data)
    except NoteNotFoundError as error:
        raise note_not_found() from error
    except NoteTargetNotFoundError as error:
        raise note_target_not_found(error) from error
    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    try:
        await NoteService(session).delete(note_id, current_user.id)
    except NoteNotFoundError as error:
        raise note_not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
