from typing import Literal

from pydantic import BaseModel, Field

EntityType = Literal["Person", "Organization", "Location", "Event", "Concept", "Other"]


class ExtractedEntity(BaseModel):
    name: str
    entity_type: EntityType
    aliases_in_text: list[str] = Field(default_factory=list)
    description: str


class ExtractedRelationship(BaseModel):
    source_entity_name: str
    target_entity_name: str
    predicate: str
    description: str


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class VisionExtractionResult(ExtractionResult):
    transcribed_text: str
