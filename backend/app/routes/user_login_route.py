from fastapi import APIRouter
from app.database.mongodb import user_collection
from pydantic import BaseModel
from app.auth import create_access_token

class User_login(BaseModel):
    email : str
    password: str


router = APIRouter()

@router.post("/login")
async def user_login(user:User_login):
    user_details =  await user_collection.find_one({ "email" : user.email}) #user_details is an array of values stored in db.

    if not user_details:
        return{"message": "login failed. Invalid email entered"}
    
    if user.password != user_details['password']:
        return {"message": "login failed, incorrect Password entered"}
    
    if user_details['email'] == user.email and user_details['password'] == user.password: 
        access_token = create_access_token(data={"user_id": str(user_details['_id'])})
        return {
            "message":"login successful",
            "access_token": access_token,
            "token_type":"bearer"
            }
    
    else:
        return {"message":"login failed, user not found" }
    
