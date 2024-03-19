from langchain_openai import ChatOpenAI


class CoreChatModel:
    temperature: float = 0.7
    model_name: str = "gpt-3.5-turbo"
    @classmethod
    def create_model(cls):
        return ChatOpenAI(temperature=cls.temperature, model=cls.model_name)

