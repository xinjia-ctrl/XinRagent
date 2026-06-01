from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.conversation import (
    ConversationMessageResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageFeedbackRequest,
)
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["conversation"])


@router.get("/conversations", response_model=ApiResponse[list[ConversationResponse]])
async def list_conversations_api(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[ConversationResponse]]:
    service = ConversationService(session)
    return success(await service.list_conversations(str(user.id)))


@router.put("/conversations/{conversation_id}", response_model=ApiResponse[None])
async def rename_conversation_api(
    conversation_id: str,
    request: ConversationUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[None]:
    service = ConversationService(session)
    await service.rename_conversation(conversation_id, str(user.id), request.title)
    return success()


@router.delete("/conversations/{conversation_id}", response_model=ApiResponse[None])
async def delete_conversation_api(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[None]:
    service = ConversationService(session)
    await service.delete_conversation(conversation_id, str(user.id))
    return success()


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[list[ConversationMessageResponse]],
)
async def list_conversation_messages_api(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[ConversationMessageResponse]]:
    service = ConversationService(session)
    return success(await service.list_messages(conversation_id, str(user.id)))


@router.post("/conversations/messages/{message_id}/feedback", response_model=ApiResponse[None])
async def save_message_feedback_api(
    message_id: str,
    request: MessageFeedbackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[None]:
    service = ConversationService(session)
    await service.save_message_feedback(message_id, str(user.id), request.vote)
    return success()
