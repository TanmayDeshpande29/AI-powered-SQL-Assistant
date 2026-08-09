from fastapi import APIRouter
from pydantic import BaseModel
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

class SQLRequest(BaseModel):
    query: str
    dialect: str

@router.post("/generate-sql")
async def generate_sql(request: SQLRequest):
    prompt = f"Write a {request.dialect} SQL query for: {request.query}"

    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",  # change if needed
            messages=[
                {"role": "system", "content": "You are a helpful SQL query generator. Output only SQL code."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        # Log full Groq response for debugging
        print("Groq response:", completion)

        sql_output = completion.choices[0].message.content.strip()

        if not sql_output:
            return {"error": "No SQL returned from Groq"}

        return {"sql": sql_output}

    except Exception as e:
        print("Error in Groq request:", str(e))
        return {"error": str(e)}
