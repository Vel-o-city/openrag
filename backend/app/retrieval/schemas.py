from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    id: str
    text: str
    page_number: int
    document_id: str
    filename: str


class RetrievedEntity(BaseModel):
    id: str
    name: str
    entity_type: str
    description: str


class RetrievedRelationship(BaseModel):
    id: str
    source_id: str
    target_id: str
    predicate: str
    description: str


class RetrievalResult(BaseModel):
    chunks: list[RetrievedChunk]
    entities: list[RetrievedEntity]
    relationships: list[RetrievedRelationship]
