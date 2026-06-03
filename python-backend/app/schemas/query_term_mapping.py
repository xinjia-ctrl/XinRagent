from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class QueryTermMappingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sourceTerm: str = Field(validation_alias=AliasChoices("source_term", "sourceTerm"))
    targetTerm: str = Field(validation_alias=AliasChoices("target_term", "targetTerm"))
    matchType: int = Field(validation_alias=AliasChoices("match_type", "matchType"))
    priority: int
    enabled: bool
    remark: str | None = None
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class QueryTermMappingPageResponse(BaseModel):
    records: list[QueryTermMappingResponse]
    total: int
    size: int
    current: int
    pages: int


class QueryTermMappingPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_term: str | None = Field(default=None, validation_alias=AliasChoices("source_term", "sourceTerm"))
    target_term: str | None = Field(default=None, validation_alias=AliasChoices("target_term", "targetTerm"))
    match_type: int | None = Field(default=None, validation_alias=AliasChoices("match_type", "matchType"))
    priority: int | None = None
    enabled: bool | None = None
    remark: str | None = None
