from fastapi import APIRouter
from pydantic import BaseModel
from app.database.mongodb import query_collection
from bson import ObjectId

router = APIRouter()

class QueryItem(BaseModel):
    id: str
    name:str
    size:str
    date:str
    type:str

class QueryRequest(BaseModel):
    user_id:str
    query: QueryItem


@router.post("/add-query")
def add_query(data:QueryRequest):
    existing  = query_collection.find_one({"user_id": ObjectId(data.user_id)})
    print("user inserted",data.user_id)
    query_collection.insert_one(            
            {
            "user_id":data.user_id,
            "queries":[data.query.dict()]
            }
        )
    return {"message":"Query information saved Successfully."}

    # if existing:
    #     print("user already exist",data.user_id)
    #     query_collection.update_one(
    #         {"user_id": data.user_id},
    #         {"$push": {"queries":data.query.dict()}}
    #     )

    # else:
    #     print("user inserted",data.user_id)
    #     query_collection.insert_one(            
    #         {
    #         "user_id":data.user_id,
    #         "queries":[data.query.dict()]
    #         }
    #     )
    # return {"message":"Query information saved Successfully."}

     