from langchain.prompts import PromptTemplate
from abc import ABC, abstractmethod

class BasePrompt(ABC):
    def __init__(self, instruction, parser) -> None:
        super().__init__()
        self.instruction = instruction
        self.parser = parser
    @abstractmethod
    def create_prompt(self):
        pass


class BookmarkClassifierPrompt(BasePrompt):
    def __init__(self, instruction, parser) -> None:
        super().__init__(instruction, parser)
    def create_prompt(self):
        prompt = PromptTemplate(
        template=self.instruction,
        input_variables=["bookmark_description", "bookmark_url"],
        partial_variables={"format_instructions": self.parser.get_format_instructions()},
    )
        return prompt
