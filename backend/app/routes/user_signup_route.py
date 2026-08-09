from fastapi import APIRouter
from app.database.mongodb import user_collection
from pydantic import BaseModel


class User_signup(BaseModel):
    name:str
    email:str
    password:str


router = APIRouter()

@router.post("/signup")

async def user_singup(user:User_signup):
    user_details = await user_collection.find_one({
        "email": user.email,       
    })

    if user_details: 
        return {"message": "user already exists"}

    else:
        user_data = {
            "name": user.name,
            "email": user.email,
            "password": user.password

        }
        await user_collection.insert_one(user_data)
        return {"message": "user created successfully"}