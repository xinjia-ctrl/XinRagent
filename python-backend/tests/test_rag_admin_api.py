from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.intent_tree import get_intent_tree_service
from app.api.v1.query_term_mappings import get_query_term_mapping_service
from app.api.v1.sample_questions import get_sample_question_service
from app.main import create_app
from app.models import User
from app.schemas.intent_tree import IntentNodeTreeResponse
from app.schemas.query_term_mapping import QueryTermMappingPageResponse, QueryTermMappingResponse
from app.schemas.sample_question import SampleQuestionPageResponse, SampleQuestionResponse


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_rag_admin_client(
    intent_service: object | None = None,
    mapping_service: object | None = None,
    sample_service: object | None = None,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    if intent_service is not None:
        app.dependency_overrides[get_intent_tree_service] = lambda: intent_service
    if mapping_service is not None:
        app.dependency_overrides[get_query_term_mapping_service] = lambda: mapping_service
    if sample_service is not None:
        app.dependency_overrides[get_sample_question_service] = lambda: sample_service
    return TestClient(app)


def test_intent_tree_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    service.list_tree.return_value = [
        IntentNodeTreeResponse(
            id="intent-1",
            intentCode="root",
            name="根意图",
            level=0,
            enabled=1,
            children=[
                IntentNodeTreeResponse(
                    id="intent-2",
                    intentCode="qa",
                    name="问答",
                    level=1,
                    parentCode="root",
                    examples="如何使用？",
                    topK=5,
                    enabled=1,
                ),
            ],
        ),
    ]
    service.create_node.return_value = "intent-new"
    client = create_rag_admin_client(intent_service=service)

    tree_response = client.get("/api/ragent/intent-tree/trees")
    create_response = client.post(
        "/api/ragent/intent-tree",
        json={
            "kbId": "kb-1",
            "intentCode": "qa",
            "name": "问答",
            "level": 1,
            "parentCode": "root",
            "examples": ["如何使用？"],
            "topK": 5,
        },
    )
    update_response = client.put(
        "/api/ragent/intent-tree/intent-2",
        json={"name": "问答更新", "enabled": 0, "collectionName": "kb_default"},
    )
    delete_response = client.delete("/api/ragent/intent-tree/intent-2")
    enable_response = client.post("/api/ragent/intent-tree/batch/enable", json={"ids": ["intent-1"]})
    disable_response = client.post("/api/ragent/intent-tree/batch/disable", json={"ids": ["intent-2"]})
    batch_delete_response = client.post("/api/ragent/intent-tree/batch/delete", json={"ids": ["intent-2"]})

    assert tree_response.status_code == 200
    assert tree_response.json()["data"][0]["children"][0]["parentCode"] == "root"
    assert create_response.json()["data"] == "intent-new"
    assert update_response.json()["data"] is None
    assert delete_response.json()["data"] is None
    assert enable_response.json()["data"] is None
    assert disable_response.json()["data"] is None
    assert batch_delete_response.json()["data"] is None
    create_request = service.create_node.await_args.args[0]
    update_request = service.update_node.await_args.args[1]
    assert create_request.intent_code == "qa"
    assert create_request.examples == ["如何使用？"]
    assert update_request.collection_name == "kb_default"
    service.batch_enable.assert_any_await(service.batch_enable.await_args_list[0].args[0], enabled=1, user_id="1")
    service.batch_enable.assert_any_await(service.batch_enable.await_args_list[1].args[0], enabled=0, user_id="1")
    service.batch_delete.assert_awaited_once()


def test_query_term_mapping_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    service.list_mappings.return_value = QueryTermMappingPageResponse(
        records=[
            QueryTermMappingResponse(
                id="map-1",
                sourceTerm="LLM",
                targetTerm="大语言模型",
                matchType=1,
                priority=10,
                enabled=True,
                remark="同义词",
            ),
        ],
        total=1,
        size=5,
        current=2,
        pages=1,
    )
    service.create_mapping.return_value = "map-new"
    service.get_mapping.return_value = QueryTermMappingResponse(
        id="map-1",
        sourceTerm="LLM",
        targetTerm="大语言模型",
        matchType=1,
        priority=10,
        enabled=True,
        remark="同义词",
    )
    client = create_rag_admin_client(mapping_service=service)

    page_response = client.get("/api/ragent/mappings?current=2&size=5&keyword=LLM")
    detail_response = client.get("/api/ragent/mappings/map-1")
    create_response = client.post(
        "/api/ragent/mappings",
        json={"sourceTerm": "LLM", "targetTerm": "大语言模型", "matchType": 1, "priority": 10},
    )
    update_response = client.put("/api/ragent/mappings/map-1", json={"enabled": False, "remark": "停用"})
    delete_response = client.delete("/api/ragent/mappings/map-1")

    assert page_response.json()["data"]["records"][0]["targetTerm"] == "大语言模型"
    assert detail_response.json()["data"]["id"] == "map-1"
    assert create_response.json()["data"] == "map-new"
    assert update_response.json()["data"] is None
    assert delete_response.json()["data"] is None
    service.list_mappings.assert_awaited_once_with(current=2, size=5, keyword="LLM")
    service.get_mapping.assert_awaited_once_with("map-1")
    create_request = service.create_mapping.await_args.args[0]
    update_request = service.update_mapping.await_args.args[1]
    assert create_request.source_term == "LLM"
    assert update_request.enabled is False
    service.delete_mapping.assert_awaited_once_with("map-1", "1")


def test_sample_question_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    sample = SampleQuestionResponse(
        id="question-1",
        title="入门",
        description="常见问题",
        question="Ragent 如何接入知识库？",
    )
    service.list_public_questions.return_value = [sample]
    service.list_questions.return_value = SampleQuestionPageResponse(
        records=[sample],
        total=1,
        size=10,
        current=1,
        pages=1,
    )
    service.get_question.return_value = sample
    service.create_question.return_value = "question-new"
    client = create_rag_admin_client(sample_service=service)

    public_response = client.get("/api/ragent/rag/sample-questions")
    page_response = client.get("/api/ragent/sample-questions?current=1&size=10&keyword=知识库")
    detail_response = client.get("/api/ragent/sample-questions/question-1")
    create_response = client.post(
        "/api/ragent/sample-questions",
        json={"title": "入门", "description": "常见问题", "question": "Ragent 如何接入知识库？"},
    )
    update_response = client.put("/api/ragent/sample-questions/question-1", json={"question": "如何接入？"})
    delete_response = client.delete("/api/ragent/sample-questions/question-1")

    assert public_response.json()["data"][0]["question"] == "Ragent 如何接入知识库？"
    assert page_response.json()["data"]["records"][0]["title"] == "入门"
    assert detail_response.json()["data"]["id"] == "question-1"
    assert create_response.json()["data"] == "question-new"
    assert update_response.json()["data"] is None
    assert delete_response.json()["data"] is None
    service.list_questions.assert_awaited_once_with(current=1, size=10, keyword="知识库")
    service.get_question.assert_awaited_once_with("question-1")
    create_request = service.create_question.await_args.args[0]
    update_request = service.update_question.await_args.args[1]
    assert create_request.question == "Ragent 如何接入知识库？"
    assert update_request.question == "如何接入？"
