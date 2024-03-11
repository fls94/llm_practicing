from abc import ABC, abstractmethod
from prompts import *
from models import *
from parsers import *
from constants import *
from instructions import *


class AbstractFactory(ABC):
    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
    @abstractmethod
    def create_prompt(self):
        pass

    def create_model(self):
        if self.config.model == BASE_CHAT_MODEL:
            return CoreChatModel.create_model()
        else:
            raise ValueError("Model is not supported")
    
    @abstractmethod
    def create_output_parser(self, parser):
        pass


class BookmarkClassifierFactory(AbstractFactory):
    def create_prompt(self):
        classifier_prompt = BookmarkClassifierPrompt(BOOKMARK_CLASSIFY_INSTRUCTION, self.parser)
        return classifier_prompt.create_prompt()
    
    def create_output_parser(self):
        parser = BookmarkClassifierParser()
        self.parser = parser.create_parser()
        return self.parser