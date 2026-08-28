from .pgdb import DB
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel 
import uuid
from fastapi import HTTPException
from fastapi import status
import os
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level = logging.INFO, 
    format="[%(asctime)s:%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creating file storing location 
storage_location = os.getenv('storage')
if not os.path.exists(storage_location)
    os.mkdir(storage_location)
# Storage will exist


db = DB()
db_status = db.connect() 
if db_status: 
    logging.info("Connected to db")

db.check_db_health()

result = db.users.select(user_name="THIS_USER_DOES_NOT_EXIST")
print(result)
print(type(result))

class UserDB(BaseModel):
    user_name: str
    user_password: str

class BucketDB(BaseModel):
    user_name : str
    user_password :str
    bucket_name : str
    bucket_password : str 


class UserPass(BaseModel):
    user_name : str
    user_password : str


class ObjectDB(BaseModel):
    user_name : str 
    user_password : str

    object_name : str 
    object_size :  int
    object_extension : str
    object_file_type : str
    is_public  : bool



# For patches
class BucketUpdate(BaseModel):
    user_name : str 
    user_password : str
    bucket_name : str | None = None
    bucket_password_old : str  | None = None
    bucket_password : str | None = None 

class ObjectUpdate(BaseModel):
    user_name : str 
    user_password : str

    object_name : str  | None = None
    is_public  : bool | None = None

class UserUpdate(BaseModel): 
    user_name_old : str
    user_name : str | None = None
    user_password_old : str 
    user_password : str | None = None



def format_output(func, *args, **kwargs):
    data = func.select(*args, **kwargs)

    return [
        dict(zip(args, row))
        for row in data
    ]
"""
    create_user : to create a new user
    delete_user : to delete a user
"""
@app.post("/", status_code=status.HTTP_201_CREATED)
def create_user(user:UserDB):
    stats = db.users.insert(user_name=user.user_name, user_password=user.user_password)
    if not stats:
        raise HTTPException(
            status_code=400,
            detail="Error creating user, user already exists"
        )
@app.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(userpass:UserPass):
    user_id = db.users.select("user_id", user_name=userpass.user_name, user_password=userpass.user_password)
    if not user_id:
        raise HTTPException(
            status_code=404, 
            detail='User not found'
        )
    db.users.delete(user_id=user_id[0][0])

@app.patch("/")
def patch_user(user_update : UserUpdate):
    user_id = db.users.select("user_id", user_name=user_update.user_name_old, user_password=user_update.user_password_old)
    if not user_id:
        raise HTTPException(
            status_code=404, 
            detail='User not found'
        )
    output_json = {"message" : "Patch succesfull", "patches":[]}
    if user_update.user_name:
        db.users.update({"user_id" : user_id[0][0]}, user_name=user_update.user_name)
        output_json.get("patches").append("user_name")
    if user_update.user_password:
        db.users.update({"user_id" : user_id[0][0]}, user_password=user_update.user_password)
        output_json.get("patches").append("user_password")
    return output_json


"""
create_bucket : to create a new bucket
list_buckets : to get all the created buckets
patch_bucket : to patch bucket settings ( bucket_name, bucket_password )
delete_bucket : to delete a bucket
"""
@app.post('/create-bucket', status_code=status.HTTP_201_CREATED)
def create_bucket(bucket:BucketDB):
    bucket_id = uuid.uuid4()
    user_id = db.users.select('user_id', user_name=bucket.user_name, user_password=bucket.user_password)
    if not user_id:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    db.buckets.insert(bucket_id = bucket_id,
                      user_id=user_id[0][0],
                    bucket_name=bucket.bucket_name,
                    bucket_password=bucket.bucket_password)

@app.post("/buckets")
def list_buckets(userpass:UserPass):
    user_id = db.users.select('user_id', user_name=userpass.user_name, user_password=userpass.user_password)
    if not user_id:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
            "buckets" : format_output(db.buckets, 
                                      'bucket_name',
                                      'bucket_id',
                                        user_id = user_id[0][0]),
           }

@app.patch('/buckets/{bucket_id}')
def patch_bucket(bucket_id, bucket_update : BucketUpdate):
    user_id = db.users.select('user_id', user_name=bucket_update.user_name, user_password=bucket_update.user_password)
    if not user_id:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        )
    useridb = db.buckets.select('user_id','bucket_password', bucket_id=bucket_id)
    if not useridb:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        ) 
    if useridb[0][0] != user_id[0][0]:
        raise HTTPException(
            status_code=400,
            detail="You don't have access to this bucket"
        ) 
    bp  = useridb[0][1]
    if not bp:
        raise HTTPException(
                status_code=404,
                detail="No such bucket found"
            )
    output_json = {"message" : "Patch successful", "patches": []}
    if bucket_update.bucket_name:
        db.buckets.update({ "bucket_id" : bucket_id}, bucket_name=bucket_update.bucket_name)
        output_json.get("patches").append("bucket_name")
    if bucket_update.bucket_password_old:
        if bucket_update.bucket_password:
            if bp == bucket_update.bucket_password_old:
                db.buckets.update({"bucket_id" : bucket_id}, bucket_password=bucket_update.bucket_password)
                output_json.get('patches').append('bucket_password')
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Passwords don't match"
                )
            

    return output_json   

@app.delete('/buckets/{bucket_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_bucket(bucket_id, userpass:UserPass):
    user_id_b = db.buckets.select('user_id', bucket_id=bucket_id)
    if not user_id_b:
        raise HTTPException(
            status_code= 404, 
            detail="User not found"
        )
    user_id = db.users.select("user_id", user_name=userpass.user_name, user_password=userpass.user_password)
    if not user_id:
        raise HTTPException(
            status_code= 404, 
            detail="User not found"
        ) 

    if user_id[0][0] != user_id_b[0][0]:
        raise HTTPException(
            status_code= 400, 
            detail="You don't have access to this bucket"
        ) 
    db.buckets.delete(bucket_id=bucket_id)





"""
create_object : to create a new object inside a bucket
list_objects  : to list all the objects inside the bucket
patch_object : to change the object settings  ( object_name, is_public )
delete_object : to delete the object 
""" 
@app.post("/buckets/{bucket_id}/create-object", status_code=status.HTTP_201_CREATED)
def create_object(bucket_id:str, object_db:ObjectDB):
    user_id = db.users.select('user_id', user_name=object_db.user_name, user_password=object_db.user_password)
    if not user_id:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    object_uuid = uuid.uuid4()

    db.objects.insert(user_id=user_id[0][0], 
                      bucket_id = bucket_id, 
                      object_uuid = object_uuid,
                      object_name = object_db.object_name, 
                      object_size = object_db.object_size, 
                      object_extension = object_db.object_extension, 
                      object_file_type = object_db.object_file_type, 
                      is_public = object_db.is_public)


@app.post('/buckets/{bucket_id}') 
def list_objects(bucket_id, userpass:UserPass):
    user_id = db.users.select('user_id', user_name=userpass.user_name, user_password=userpass.user_password)
    if  len(user_id) == 0:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        )
    useridb = db.buckets.select('user_id', bucket_id=bucket_id)
    if len(useridb) == 0:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        ) 
    if useridb[0][0] != user_id[0][0]:
        raise HTTPException(
            status_code=400,
            detail="You don't have access to this bucket"
        ) 
    return {
        "objects"  : format_output(db.objects, 'object_name', 'object_size', "object_extension", "object_file_type", "object_uuid", "is_public", bucket_id=bucket_id, )
    } 

 
@app.patch('/buckets/{bucket_id}/{object_uuid}')
def patch_object(bucket_id, object_uuid ,object_update : ObjectUpdate):
    user_id = db.users.select('user_id', user_name=object_update.user_name, user_password=object_update.user_password)
    if  len(user_id) == 0:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        )

    bp = db.objects.select('bucket_id', "user_id", object_uuid=object_uuid, bucket_id=bucket_id)
    if not bp:
        raise HTTPException(
                status_code=404,
                detail="No such object found"
            )
    if bp[0][1] != user_id[0][0]:
        raise HTTPException(
                status_code=400,
                detail="You don't have access to this object"
            )
 
    output_json = {"message": "Patch successful" ,"patches" : []}
    if object_update.object_name:
        db.objects.update({ "object_uuid" : object_uuid}, object_name=object_update.object_name)
        output_json.get("patches").append("object_name")
    if object_update.is_public!=None:
        db.objects.update({"object_uuid" : object_uuid}, is_public=object_update.is_public)
        output_json.get("patches").append("is_public")

    return output_json

@app.delete('/buckets/{bucket_id}/{object_uuid}', status_code=status.HTTP_204_NO_CONTENT)
def delete_object(bucket_id,object_uuid ,userpass:UserPass):
    user_id_b = db.objects.select('user_id', object_uuid=object_uuid, bucket_id = bucket_id)
    if not user_id_b:
        raise HTTPException(
            status_code= 404, 
            detail="User not found"
        )

    user_id = db.users.select("user_id", user_name=userpass.user_name, user_password=userpass.user_password)
    if not user_id:
        raise HTTPException(
            status_code= 404, 
            detail="User not found"
        ) 

    if user_id[0][0] != user_id_b[0][0]:
        raise HTTPException(
            status_code= 400, 
            detail="You don't have access to this bucket"
        ) 
    db.objects.delete(object_uuid=object_uuid)
