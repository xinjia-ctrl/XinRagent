from app.models import Conversation, ConversationSummary, Message, MessageFeedback, User


def test_user_model_maps_to_existing_table_name() -> None:
    assert User.__tablename__ == "t_user"
    assert "username" in User.__table__.columns
    assert User.__table__.columns["username"].unique is True


def test_conversation_model_maps_core_columns() -> None:
    assert Conversation.__tablename__ == "t_conversation"
    assert {"id", "conversation_id", "user_id", "title", "last_time", "deleted"}.issubset(
        Conversation.__table__.columns.keys(),
    )


def test_message_model_maps_postgres_schema_columns() -> None:
    assert Message.__tablename__ == "t_message"
    assert {
        "id",
        "conversation_id",
        "user_id",
        "role",
        "content",
        "thinking_content",
        "thinking_duration",
        "deleted",
    }.issubset(Message.__table__.columns.keys())


def test_conversation_summary_model_maps_postgres_schema_columns() -> None:
    assert ConversationSummary.__tablename__ == "t_conversation_summary"
    assert {"id", "conversation_id", "user_id", "last_message_id", "content", "deleted"}.issubset(
        ConversationSummary.__table__.columns.keys(),
    )


def test_message_feedback_model_maps_postgres_schema_columns() -> None:
    assert MessageFeedback.__tablename__ == "t_message_feedback"
    assert {"id", "message_id", "conversation_id", "user_id", "vote", "deleted"}.issubset(
        MessageFeedback.__table__.columns.keys(),
    )
