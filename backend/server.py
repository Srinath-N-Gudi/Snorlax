from .pgdb import DB
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel 
from datetime import datetime, timedelta
import uuid
from fastapi import HTTPException
from fastapi import status
import os
from dotenv import load_dotenv
from .encrypter import crypt
load_dotenv()


logging.basicConfig(
    level = logging.INFO, 
    format="[%(asctime)s:%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creating file storing location 
storage_location = os.getenv('storage', default="storage")
os.makedirs(storage_location,exist_ok=True)
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
    bucket_name : str
    bucket_password : str 


class UserPass(BaseModel):
    user_name : str
    user_password : str


class ObjectDB(BaseModel):
    object_name : str 
    object_size :  int
    object_extension : str
    object_file_type : str
    is_public  : bool



# For patches
class BucketUpdate(BaseModel):
    bucket_name : str | None = None
    bucket_password_old : str  | None = None
    bucket_password : str | None = None 

class ObjectUpdate(BaseModel):
    object_name : str | None = None
    object_size :  int| None = None
    object_extension : str| None = None
    object_file_type : str| None = None
    is_public  : bool| None = None

class UserUpdate(BaseModel): 
    user_name : str | None = None
    user_password : str | None = None



def format_output(func, *args, **kwargs):
    data = func.select(*args, **kwargs)

    return [
        dict(zip(args, row))
        for row in data
    ]

def file_generator(object_location, bucket_pass):

    offset = 0

    with open(object_location, "rb") as file:

        while chunk := file.read(1024 * 1024):

            decrypted = crypt(
                chunk,
                bucket_pass,
                offset
            )

            offset += len(chunk)

            yield decrypted

def get_user_id(request: Request):

    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Not logged in"
        )

    session = db.sessions.select(
        "user_id",
        "expires_at",
        session_id=session_id
    )

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid session"
        )

    if session[0][1] < datetime.now():
        db.sessions.delete(user_id=session[0][0])
        raise HTTPException(
            status_code=401,
            detail="Session expired"
        )

    return session[0][0]

"""
    create_user : to create a new user
    delete_user : to delete a user
    login : to get the login cookie
"""
@app.post("/", status_code=status.HTTP_201_CREATED)
def create_user(user:UserDB):
    stats = db.users.insert(user_name=user.user_name, user_password=user.user_password)
    if not stats:
        raise HTTPException(
            status_code=403,
            detail="Error creating user, user already exists"
        )
@app.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(request: Request):
    user_id = get_user_id(request)
    db.users.delete(user_id=user_id)

@app.post("/login", status_code=status.HTTP_200_OK)
def login(userpass: UserPass, response: Response):

    user_id = db.users.select(
        "user_id",
        user_name=userpass.user_name,
        user_password=userpass.user_password
    )

    if not user_id:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user_id = user_id[0][0]

    # Check existing session
    session = db.sessions.select(
        "session_id",
        "expires_at",
        user_id=user_id
    )

    session_id = uuid.uuid4()
    expires_at = datetime.now() + timedelta(days=1)

    if session:
        # Existing session → update it
        db.sessions.update(
            {"user_id": user_id},
            session_id=session_id,
            expires_at=expires_at
        )
    else:
        # No session → create one
        db.sessions.insert(
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at
        )

    response.set_cookie(
        key="session_id",
        value=str(session_id),
        httponly=True,
        max_age=86400
    )

    return {"message": "Login successful"}

@app.patch("/")
def patch_user(user_update : UserUpdate, request:Request):
    user_id = get_user_id(request)
    output_json = {"message" : "Patch succesfull", "patches":[]}
    if user_update.user_name:
        db.users.update({"user_id" : user_id}, user_name=user_update.user_name)
        output_json.get("patches", []).append("user_name")
    if user_update.user_password:
        db.users.update({"user_id" : user_id}, user_password=user_update.user_password)
        output_json.get("patches", []).append("user_password")
    return output_json


"""
create_bucket : to create a new bucket
list_buckets : to get all the created buckets
patch_bucket : to patch bucket settings ( bucket_name, bucket_password )
delete_bucket : to delete a bucket
"""
@app.post('/create-bucket', status_code=status.HTTP_201_CREATED)
def create_bucket(bucket:BucketDB, request : Request):
    bucket_id = uuid.uuid4()
    user_id = get_user_id(request)
    db.buckets.insert(bucket_id = bucket_id,
                      user_id=user_id,
                    bucket_name=bucket.bucket_name,
                    bucket_password=bucket.bucket_password)
    return { "bucket_id" : bucket_id  } 
@app.get("/buckets")
def list_buckets(request:Request):
    user_id = get_user_id(request) 
    return {
            "buckets" : format_output(db.buckets, 
                                      'bucket_name',
                                      'bucket_id',
                                        user_id = user_id),
           }

@app.patch('/buckets/{bucket_id}')
def patch_bucket(bucket_id, bucket_update : BucketUpdate, request : Request):
    user_id = get_user_id(request)
    useridb = db.buckets.select('user_id','bucket_password', bucket_id=bucket_id)
    if not useridb:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        ) 
    if useridb[0][0] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this bucket"
        ) 
    bp  = useridb[0][1]
    if bp is None:
        raise HTTPException(
                status_code=404,
                detail="No such bucket found"
            )
    output_json = {"message" : "Patch successful", "patches": []}
    if bucket_update.bucket_name is not None and bucket_update.bucket_name.strip() != "":
        db.buckets.update({ "bucket_id" : bucket_id}, bucket_name=bucket_update.bucket_name.strip())
        output_json.get("patches", []).append("bucket_name")
    if bucket_update.bucket_password_old is not None and bucket_update.bucket_password is not None:
        if bucket_update.bucket_password_old.strip() == "" or bucket_update.bucket_password.strip() == "":
            raise HTTPException(status_code=400, detail="Password cannot be empty")
        if bp == bucket_update.bucket_password_old:
            db.buckets.update({"bucket_id" : bucket_id}, bucket_password=bucket_update.bucket_password)
            output_json.get('patches', []).append('bucket_password')
        else:
            raise HTTPException(
                status_code=403,
                detail="Passwords don't match"
            )
            

    return output_json   

@app.delete('/buckets/{bucket_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_bucket(bucket_id, request: Request):
    user_id = get_user_id(request)
    user_id_b = db.buckets.select('user_id', bucket_id=bucket_id)
    if not user_id_b:
        raise HTTPException(
            status_code= 404, 
            detail="User not found"
        )
    if user_id != user_id_b[0][0]:
        raise HTTPException(
            status_code= 403, 
            detail="You don't have access to this bucket"
        ) 
    db.buckets.delete(bucket_id=bucket_id)


"""
create_object : to create a new object inside a bucket  ( Will return the object_uuid )
list_objects  : to list all the objects inside the bucket
patch_object : to change the object settings  ( object_name, is_public )
delete_object : to delete the object 
upload_object : to upload that data 
""" 
@app.post("/buckets/{bucket_id}/create-object", status_code=status.HTTP_201_CREATED)
def create_object(bucket_id:str, object_db:ObjectDB, request: Request):
    user_id = get_user_id(request) 
    object_uuid = uuid.uuid4()
    useridb = db.buckets.select('user_id', bucket_id=bucket_id)
    if not useridb:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        ) 
    if useridb[0][0] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this bucket"
        ) 
    
    db.objects.insert(user_id=user_id, 
                      bucket_id = bucket_id, 
                      object_uuid = object_uuid,
                      object_name = object_db.object_name, 
                      object_size = object_db.object_size, 
                      object_extension = object_db.object_extension, 
                      object_file_type = object_db.object_file_type, 
                      is_public = object_db.is_public)
    return { "object_uuid" : object_uuid }


@app.get('/buckets/{bucket_id}') 
def list_objects(bucket_id, request: Request):
    user_id = get_user_id(request)
    useridb = db.buckets.select('user_id', bucket_id=bucket_id)
    if not useridb:
        raise HTTPException(
            status_code=404,
            detail="No such bucket found"
        ) 
    if useridb[0][0] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this bucket"
        ) 
    return {
        "objects"  : format_output(db.objects, 'object_name', 'object_size', "object_extension", "object_file_type", "object_uuid", "is_public", bucket_id=bucket_id, )
    } 

 
@app.patch('/buckets/{bucket_id}/{object_uuid}')
def patch_object(bucket_id, object_uuid ,object_update : ObjectUpdate, request: Request):
    user_id = get_user_id(request)
    bp = db.objects.select('bucket_id', "user_id", object_uuid=object_uuid, bucket_id=bucket_id)
    if not bp:
        raise HTTPException(
                status_code=404,
                detail="No such object found"
            )
    if bp[0][1] != user_id:
        raise HTTPException(
                status_code=403,
                detail="You don't have access to this object"
            )
 
    output_json = {"message": "Patch successful" ,"patches" : []}
    if object_update.object_name is not None and object_update.object_name.strip() != "":
        db.objects.update({ "object_uuid" : object_uuid}, object_name=object_update.object_name.strip())
        output_json.get("patches", []).append("object_name")

    if object_update.is_public is not None:
        db.objects.update({"object_uuid" : object_uuid}, is_public=object_update.is_public)
        output_json.get("patches", []).append("is_public")
        
    if object_update.object_extension is not None:
        db.objects.update({"object_uuid" : object_uuid}, object_extension=object_update.object_extension)
        output_json.get("patches", []).append("object_extension")
        
    if object_update.object_file_type is not None:
        db.objects.update({"object_uuid" : object_uuid}, object_file_type=object_update.object_file_type)
        output_json.get("patches", []).append("object_file_type")

    if object_update.object_size is not None:
        db.objects.update({"object_uuid" : object_uuid}, object_size=object_update.object_size)
        output_json.get("patches", []).append("object_size")





    return output_json

@app.delete('/buckets/{bucket_id}/{object_uuid}', status_code=status.HTTP_204_NO_CONTENT)
def delete_object(bucket_id,object_uuid ,request: Request):
    user_id_b = db.objects.select('user_id', object_uuid=object_uuid, bucket_id = bucket_id)
    if not user_id_b:
        raise HTTPException(
            status_code= 404, 
            detail="Object not found"
        )
    user_id = get_user_id(request)
    if user_id != user_id_b[0][0]:
        raise HTTPException(status_code=403, detail="You don't have access to this object")
    db.objects.delete(object_uuid=object_uuid)

@app.put("/buckets/{bucket_id}/{object_uuid}", status_code=status.HTTP_200_OK)
async def upload_object(
    bucket_id: str,
    object_uuid: str,
    request: Request,
):
    user_id = get_user_id(request)
    object_data = db.objects.select(
        "user_id",
        object_uuid=object_uuid,
        bucket_id=bucket_id
    )

    if not object_data:
        raise HTTPException(
            status_code=404,
            detail="Object not found"
        )

    if user_id != object_data[0][0]:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this object"
        )

    # Find bucket password using user_id and bucket_id
    bucket_pass = db.buckets.select("bucket_password", user_id=user_id, bucket_id=bucket_id)
    if not bucket_pass: 
        raise HTTPException(
                status_code=404, 
                detail="No bucket password found"
                )
    bucket_pass = bucket_pass[0][0]
    object_location = os.path.join(storage_location, object_uuid)

    file = open(object_location, 'wb')
    try:
        async for chunk in request.stream():
            encrypted_chunk = crypt(chunk, bucket_pass)
            file.write(encrypted_chunk)
    finally:
        file.close()

    return {"message": "Upload complete"}

@app.get("/buckets/{bucket_id}/{object_uuid}")
def download_object(
    bucket_id: str,
    object_uuid: str,
    request: Request
):

    object_data = db.objects.select(
        "user_id",
        "object_name",
        "object_extension",
        "object_file_type",
        "is_public",
        object_uuid=object_uuid
    )
    if not object_data:
                raise HTTPException(
                    status_code=404,
                    detail="Object not found"
                )
    if object_data[0][4] == False: # IT's private
        user_id = get_user_id(request)
        if user_id != object_data[0][0]:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this object"
            )

    bucket_data = db.buckets.select(
        "bucket_password",
        bucket_id=bucket_id
    )

    if not bucket_data:
        raise HTTPException(
            status_code=404,
            detail="Bucket not found"
        )

    bucket_pass = bucket_data[0][0]

    object_location = os.path.join(
        storage_location,
        str(object_uuid)
    )

    if not os.path.isfile(object_location):
        raise HTTPException(
            status_code=404,
            detail="Object file not found"
        )

    object_name = object_data[0][1]
    object_file_type = object_data[0][3]

    def file_generator():

        offset = 0

        with open(object_location, "rb") as file:

            while chunk := file.read(1024 * 1024):

                decrypted_chunk = crypt(
                    chunk,
                    bucket_pass,
                    offset
                )

                offset += len(chunk)

                yield decrypted_chunk

    return StreamingResponse(
        file_generator(),
        media_type=object_file_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="{object_name}"'
        }
    )
