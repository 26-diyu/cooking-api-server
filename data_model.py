from typing import Annotated, Literal, Union, Optional
from sqlmodel import Field, SQLModel, Column, JSON

class RecipeStep(SQLModel):
    timestamp: float = Field(default=0.0)
    description: str = Field(default="")
    image_url: str | None = None  # Optional image URL for the step

class RecipeContent(SQLModel):
    description: str | None = None
    steps: list[RecipeStep] = Field(default=[])

class IngredientContent(SQLModel):
    ingredients: list[str] = Field(default=[])

class RecipeMessage(SQLModel):
    frm: str = Field(default="")
    mtype: Literal["recipe"] = "recipe"
    content: RecipeContent = Field(default=None)

class IngredientMessage(SQLModel):
    frm: str = Field(default="")
    mtype: Literal["ingredient"] = "ingredient"
    content: IngredientContent = Field(default=None)

class StringMessage(SQLModel):
    frm: str = Field(default="")
    mtype: Literal["string"] = "string"
    content: str = Field(default="")

Message = Annotated[
    Union[RecipeMessage, IngredientMessage, StringMessage],
    Field(discriminator="mtype")
]

class Messages(SQLModel):
    messages: list[Message]

class TimestampText(SQLModel):
    timestamp: Optional[float] = Field(default=0.0)
    text: Optional[str] = Field(default="")

class Transcript(SQLModel):
    video_id: Optional[str] = Field(default="")
    language: Optional[str] = Field(default="")
    timestamp_texts: list[TimestampText] = Field(default=[], sa_column=Column(JSON))