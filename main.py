import os

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls__6a1fecee135f47b1af0b893a22af2a1e"



from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bs4 import BeautifulSoup
from utils import load_config, init_factory, parse_html

config = load_config("config.json")
factory = init_factory(config)
import pymysql
 
 
# establish connection to MySQL
connection = pymysql.connect(
    # specify host name
   
    host="localhost",
     
    # specify username
    user="root",
     
    # enter password for above user
    password="admin123",
     
    # default port number for MySQL is 3306
    port=3306,
     
    # specify database name
    db="agency_db"
)

table_name = "bookmark_category"

# make cursor for establish connection
mycursor = connection.cursor()

app = FastAPI()

origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserInput(BaseModel):
    human_msg: str

def ask_llm(input_variables):
    model = factory.create_model()
    output_parser = factory.create_output_parser()
    prompt = factory.create_prompt()
    chain = prompt | model | output_parser
    response = chain.invoke(input_variables)
    return response

def save_category(category, created_date, updated_date, cursor):
    cursor.execute(f"""Insert into {table_name} (category,created_date,updated_date) values ('{category}', '{created_date}', '{updated_date}') on duplicate key update updated_date='{updated_date}'""")


@app.post("/run_bookmark_classify")
async def main(file: UploadFile):
    
    soup = BeautifulSoup(file.file, 'html.parser')
    html_data = parse_html(soup)
    for link in html_data:
        url, description = link["url"], link["description"]
        response = ask_llm({'bookmark_description': description, 'bookmark_url': url})
        with connection:
            with connection.cursor() as cursor:
                save_category(response.category, "a", "b", cursor)
            connection.commit()

    return {"filename": file.filename}



# @app.post("/")
# print(ask_llm({"bookmark_description": "How To Become A Hacke", "bookmark_url": "http://www.catb.org/esr/faqs/hacker-howto.html"}))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
