from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from vectordbs.factory import get_datastore
from vectordbs.vector_store import VectorStore
from vectordbs.data_types import Document, DocumentMetadataFilter, QueryWithEmbedding
from config import settings
from rag_solution.data_ingestion.document_processor import DocumentProcessor
from sqlalchemy.orm import Session
from uuid import uuid4
import logging
from rag_solution.file_management.file_management import save_file, get_files, get_file_path
from rag_solution.data_ingestion.ingestion import ingest_documents

logging.basicConfig(level=settings.log_level)

app = FastAPI(title="Vector Store API", description="API for interacting with the Vector Store")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get the vector store
async def get_vector_store():
    return get_datastore(settings.vector_db)

class CollectionCreate(BaseModel):
    collection_name: str = Field(..., description="The name of the collection to create")
    metadata: Optional[dict] = Field(None, description="Optional metadata for the collection")

class CollectionCreateWithDocuments(BaseModel):
    collection_name: str = Field(..., description="The name of the collection to create")
    is_private: bool
    files: List[UploadFile]

class DocumentAdd(BaseModel):
    collection_name: str = Field(..., description="The name of the collection to add documents to")
    documents: List[Document] = Field(..., description="List of documents to add")

class DocumentRetrieve(BaseModel):
    query: str = Field(..., description="The query string to search for")
    collection_name: Optional[str] = Field(None, description="Optional name of the collection to search in")
    limit: int = Field(10, description="Number of results to return")

class DocumentQuery(BaseModel):
    collection_name: str = Field(..., description="The name of the collection to query")
    query: QueryWithEmbedding = Field(..., description="The query with embedding")
    number_of_results: int = Field(10, description="Number of results to return")
    filter: Optional[DocumentMetadataFilter] = Field(None, description="Optional metadata filter")

class DocumentDelete(BaseModel):
    document_ids: List[str] = Field(..., description="List of document IDs to delete")
    collection_name: Optional[str] = Field(None, description="Optional name of the collection to delete from")

@app.post("/api/create_collection", summary="Create a new collection")
async def create_collection(collection: CollectionCreate, vector_store: VectorStore = Depends(get_vector_store)):
    try:
        await vector_store.create_collection_async(collection.collection_name, collection.metadata)
        return {"message": f"Collection '{collection.collection_name}' created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create_collection_with_documents", summary="Create a new collection with documents")
async def create_collection_with_documents(
        request: CollectionCreateWithDocuments,
        vector_store: VectorStore = Depends(get_vector_store)):
    user_id = 1  # Hardcoded for now
    try:
        await vector_store.create_collection_async(request.collection_name)

        for file in request.files:
            logging.info("Trying to process file: ", file.filename)
            file_path = save_file(file, user_id, request.collection_name)
            # Offload the document ingestion to a background task
            ingest_documents(file_path, vector_store, request.collection_name)

        return JSONResponse(
            status_code=202,
            content={
                "message": "Collection created successfully, and documents are being processed.",
                "collection_id": collection_id
            }
        )

        # await vector_store.add_documents_async(request.collection_name, documents)

        # return {"message": f"Collection '{request.collection_name}' created successfully with documents"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add_documents", summary="Add documents to a collection")
async def add_documents(doc_add: DocumentAdd, vector_store: VectorStore = Depends(get_vector_store)):
    try:
        await vector_store.add_documents_async(doc_add.collection_name, doc_add.documents)
        return {"message": f"Documents added to collection '{doc_add.collection_name}' successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/retrieve_documents", summary="Retrieve documents from a collection")
async def retrieve_documents(doc_retrieve: DocumentRetrieve, vector_store: VectorStore = Depends(get_vector_store)):
    try:
        results = await vector_store.retrieve_documents_async(doc_retrieve.query,
                                                              doc_retrieve.collection_name,
                                                              doc_retrieve.limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query", summary="Query a collection")
async def query(doc_query: DocumentQuery, vector_store: VectorStore = Depends(get_vector_store)):
    try:
        results = await vector_store.query_async(doc_query.collection_name,
                                                 doc_query.query,
                                                 doc_query.number_of_results,
                                                 doc_query.filter)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/delete_collection/{collection_name}", summary="Delete a collection")
async def delete_collection(collection_name: str, vector_store: VectorStore = Depends(get_vector_store)):
    try:
        await vector_store.delete_collection_async(collection_name)
        return {"message": f"Collection '{collection_name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/delete_documents", summary="Delete documents from a collection")
async def delete_documents(doc_delete: DocumentDelete, vector_store: VectorStore = Depends(get_vector_store)):
    try:
        await vector_store.delete_documents_async(doc_delete.document_ids, doc_delete.collection_name)
        return {"message": "Documents deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
