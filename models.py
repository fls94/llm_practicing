from langchain_openai import ChatOpenAI


class CoreChatModel:
    temperature: float = 0.7
    model_name: str = "gpt-3.5-turbo"
    @classmethod
    def create_model(cls):
        return ChatOpenAI(api_key= "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", temperature=cls.temperature, model=cls.model_name)

