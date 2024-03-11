from abc import ABC, abstractmethod
from prompt_inputs import *
from langchain.output_parsers import PydanticOutputParser

class BaseParser(ABC):
    @abstractmethod
    def create_parser(self):
        pass


class BookmarkClassifierParser(BaseParser):
    def create_parser(self):
        return PydanticOutputParser(pydantic_object=BookmarkCategory)