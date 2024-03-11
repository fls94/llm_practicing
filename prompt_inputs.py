from langchain_core.pydantic_v1 import BaseModel, Field, validator


class BookmarkCategory(BaseModel):
    category: str = Field(description="category of the bookmark")
    description: str = Field(description="user's input description")
    url: str = Field(description="user's input url")