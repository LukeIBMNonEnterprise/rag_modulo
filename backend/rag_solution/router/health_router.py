import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from genai.client import Client
from genai.credentials import Credentials

from backend.rag_solution.file_management.database import get_db
from backend.vectordbs.factory import get_datastore
from backend.core.config import settings

router = APIRouter(prefix="/api")  # Add a prefix to avoid conflicts

def check_vectordb():
    try:
        get_datastore(settings.vector_db)
        return {"status": "healthy", "message": "Vector DB is connected and operational"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vector DB health check failed: {str(e)}")

def check_datastore(db: Session = Depends(get_db)):
    try:
        # Execute a simple query
        db.execute("SELECT 1")
        return {"status": "healthy", "message": "Relational is connected and operational"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Relational DB health check failed: {str(e)}")

def check_watsonx():
    try:
        Client(credentials=Credentials.from_env())
        return {"status": "healthy", "message": "WatsonX is connected and operational"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"WatsonX health check failed: {str(e)}")

def check_file_system():
    try:
        # Check if the upload directory exists and is writable
        upload_dir = settings.file_storage_path
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        test_file = os.path.join(upload_dir, 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return {"status": "healthy", "message": "File system is accessible and writable"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"File system health check failed: {str(e)}")

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    milvus_health = check_vectordb()
    postgres_health = check_datastore(db)
    watsonx_health = check_watsonx()
    file_system_health = check_file_system()

    return {
        "status": "healthy",
        "components": {
            "vectordb": milvus_health,
            "datastore": postgres_health,
            "watsonx": watsonx_health,
            "file_system": file_system_health
        }
    }
