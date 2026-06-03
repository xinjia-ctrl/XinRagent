from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class IntentNodeTreeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    intentCode: str = Field(validation_alias=AliasChoices("intent_code", "intentCode"))
    name: str
    level: int
    parentCode: str | None = Field(default=None, validation_alias=AliasChoices("parent_code", "parentCode"))
    description: str | None = None
    examples: str | None = None
    collectionName: str | None = Field(default=None, validation_alias=AliasChoices("collection_name", "collectionName"))
    mcpToolId: str | None = Field(default=None, validation_alias=AliasChoices("mcp_tool_id", "mcpToolId"))
    topK: int | None = Field(default=None, validation_alias=AliasChoices("top_k", "topK"))
    kind: int | None = None
    sortOrder: int | None = Field(default=None, validation_alias=AliasChoices("sort_order", "sortOrder"))
    enabled: int | None = None
    promptSnippet: str | None = Field(default=None, validation_alias=AliasChoices("prompt_snippet", "promptSnippet"))
    promptTemplate: str | None = Field(default=None, validation_alias=AliasChoices("prompt_template", "promptTemplate"))
    paramPromptTemplate: str | None = Field(
        default=None,
        validation_alias=AliasChoices("param_prompt_template", "paramPromptTemplate"),
    )
    children: list["IntentNodeTreeResponse"] = Field(default_factory=list)


class IntentNodeCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kb_id: str | None = Field(default=None, validation_alias=AliasChoices("kb_id", "kbId"))
    intent_code: str = Field(validation_alias=AliasChoices("intent_code", "intentCode"))
    name: str
    level: int
    parent_code: str | None = Field(default=None, validation_alias=AliasChoices("parent_code", "parentCode"))
    description: str | None = None
    examples: list[str] | None = None
    mcp_tool_id: str | None = Field(default=None, validation_alias=AliasChoices("mcp_tool_id", "mcpToolId"))
    top_k: int | None = Field(default=None, validation_alias=AliasChoices("top_k", "topK"))
    kind: int | None = None
    sort_order: int | None = Field(default=None, validation_alias=AliasChoices("sort_order", "sortOrder"))
    enabled: int | None = None
    prompt_snippet: str | None = Field(default=None, validation_alias=AliasChoices("prompt_snippet", "promptSnippet"))
    prompt_template: str | None = Field(default=None, validation_alias=AliasChoices("prompt_template", "promptTemplate"))
    param_prompt_template: str | None = Field(
        default=None,
        validation_alias=AliasChoices("param_prompt_template", "paramPromptTemplate"),
    )


class IntentNodeUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    level: int | None = None
    parent_code: str | None = Field(default=None, validation_alias=AliasChoices("parent_code", "parentCode"))
    description: str | None = None
    examples: list[str] | None = None
    collection_name: str | None = Field(default=None, validation_alias=AliasChoices("collection_name", "collectionName"))
    mcp_tool_id: str | None = Field(default=None, validation_alias=AliasChoices("mcp_tool_id", "mcpToolId"))
    top_k: int | None = Field(default=None, validation_alias=AliasChoices("top_k", "topK"))
    kind: int | None = None
    sort_order: int | None = Field(default=None, validation_alias=AliasChoices("sort_order", "sortOrder"))
    enabled: int | None = None
    prompt_snippet: str | None = Field(default=None, validation_alias=AliasChoices("prompt_snippet", "promptSnippet"))
    prompt_template: str | None = Field(default=None, validation_alias=AliasChoices("prompt_template", "promptTemplate"))
    param_prompt_template: str | None = Field(
        default=None,
        validation_alias=AliasChoices("param_prompt_template", "paramPromptTemplate"),
    )


class IntentNodeBatchRequest(BaseModel):
    ids: list[str | int]
