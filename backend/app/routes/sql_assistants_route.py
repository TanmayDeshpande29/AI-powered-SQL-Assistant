from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from groq import Groq


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key = GROQ_API_KEY)


class SqlAssist(BaseModel):
    mode:str
    query:str
    dialect: str


router  = APIRouter()

@router.post("/sql-assistants")
def sql_assistant(request:SqlAssist):

    prompt = {
        "debug-sql" : f"providing a SQL query , plz act like a professional SQL developer and debug the following SQl query and fix and find the errors in the query and only return the SQL code, do not return the text or paragraph:\n{request.query}",
        "explain-sql" : f"providing a SQL query , plz act like a professional SQL developer and explain the following SQl query with short and simple explaination like what is the query suppose to do. The query is:\n{request.query}",
        "optimize-sql" : f"providing a SQL query , plz act like a professional SQL developer and optimize the following SQl query and fix and find the query and write the query which gives more optimized solution. and only return the SQL code, do not return the text or paragraph. The query is:\n{request.query}",       
    }

    if request.mode not in prompt:
        return {"error": "Invalid mode. Choose from 'debug-sql', 'explain-sql', or 'optimize-sql'."}
    
    prompt_text = prompt[request.mode]

    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages = [
                {"role":"system", "content": "You are a helpful and professional SQL assistant and developer. Output only SQL code."},
                {"role":"user", "content":prompt_text}
            ],
            temperature=0.2
        )
        ouput_sql = completion.choices[0].message.content.strip()
        if not ouput_sql:
            return {"error": "Something went wrong, no SQL returned"}
        else:
            return {"output": ouput_sql}
        
    except Exception as e:
        print("Error in Groq request:", str(e))
        return {"error": str(e)}
       
        
