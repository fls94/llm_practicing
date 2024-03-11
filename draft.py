# import os

# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_API_KEY"] = "ls__6a1fecee135f47b1af0b893a22af2a1e"






# # Write prompt to classify (url, title) of bookmark into a specific category

# from langchain_openai import ChatOpenAI
# # from dotenv import load_dotenv
# # load_dotenv()

# llm = ChatOpenAI(api_key="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")


# bookmark_description, bookmark_url = "How To Become A Hacke", "http://www.catb.org/esr/faqs/hacker-howto.html"

# from langchain.prompts import PromptTemplate

# # Implementation of output parser
# from langchain.output_parsers import PydanticOutputParser
# from langchain_core.pydantic_v1 import BaseModel, Field, validator

# class BookmarkCategory(BaseModel):
#     category: str = Field(description="category of the bookmark")
#     description: str = Field(description="user's input description")
#     url: str = Field(description="user's input url")

# parser = PydanticOutputParser(pydantic_object=BookmarkCategory)

# template = """### Instruction ###
#         You are given a bookmark description and its url. Classify it into a suitable category.
#         {format_instructions}\n {bookmark_description} {bookmark_url} \n
# """
# prompt = PromptTemplate(
#     template=template,
#     input_variables=["bookmark_description", "bookmark_url"],
#     partial_variables={"format_instructions": parser.get_format_instructions()},
# )
# # print(prompt_template.format(bookmark_description=bookmark_description, bookmark_url=bookmark_url))
# chat = prompt | llm | parser

# response = chat.invoke({'bookmark_description': bookmark_description, 'bookmark_url': bookmark_url})
# print(type(response))
# print(response)




# # from langchain.output_parsers import PydanticOutputParser
# # from langchain.prompts import PromptTemplate
# # from langchain_core.pydantic_v1 import BaseModel, Field, validator
# # from langchain_openai import OpenAI
# # # Define your desired data structure.
# # class Joke(BaseModel):
# #     setup: str = Field(description="question to set up a joke")
# #     punchline: str = Field(description="answer to resolve the joke")

# #     # You can add custom validation logic easily with Pydantic.
# #     @validator("setup")
# #     def question_ends_with_question_mark(cls, field):
# #         if field[-1] != "?":
# #             raise ValueError("Badly formed question!")
# #         return field
# #     @validator("punchline")
# #     def validate_punchline(cls, field):
# #         return field
    
# # # Set up a parser + inject instructions into the prompt template.
# # parser = PydanticOutputParser(pydantic_object=Joke)
# # # print(parser.get_format_instructions())

# # prompt = PromptTemplate(
# #     template="Answer the user query.\n{format_instructions}\n{query}\n",
# #     input_variables=["query"],
# #     partial_variables={"format_instructions": parser.get_format_instructions()},
# # )

# # print(prompt)





from langchain.utilities import SQLDatabase
from langchain.llms import OpenAI
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts import PromptTemplate
from langchain.prompts.chat import HumanMessagePromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

host = 'localhost'
port = '3306'
username = 'root'
password = 'admin123'
database_schema = 'agency_db'
mysql_uri = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_schema}"

db = SQLDatabase.from_uri(mysql_uri, include_tables=['bookmark_category'],sample_rows_in_table_info=2)

# db_chain = SQLDatabaseChain.from_llm(llm, db, verbose=True)