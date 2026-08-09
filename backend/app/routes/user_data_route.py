from fastapi import APIRouter
from app.database.mongodb import user_collection
from bson import ObjectId

router = APIRouter()

@router.get("/user-data/{user_id}")
async def get_user_data(user_id:str):
    user  = await user_collection.find_one({"_id":ObjectId(user_id)})

    if not user:
        return{"error":"user Not Found"}
    return{
        "email":user.get('email'),
        "name":user.get('name'),
        
    }
