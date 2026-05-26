from app.models import Conversation, Message, User


def test_user_model_maps_to_existing_table_name() -> None:
    assert User.__tablename__ == "t_user"
    assert "username" in User.__table__.columns
    assert User.__table__.columns["username"].unique is True


def test_conversation_model_maps_core_columns() -> None:
    assert Conversation.__tablename__ == "t_conversation"
    assert {"id", "user_id", "title", "summary", "status"}.issubset(
        Conversation.__table__.columns.keys(),
    )


def test_message_model_maps_conversation_foreign_key() -> None:
    foreign_keys = Message.__table__.columns["conversation_id"].foreign_keys

    assert Message.__tablename__ == "t_message"
    assert any(key.target_fullname == "t_conversation.id" for key in foreign_keys)
