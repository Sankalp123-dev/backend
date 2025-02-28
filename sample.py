from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
import os
import uuid  # For generating unique session IDs
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain.prompts import PromptTemplate
from groq import Groq
from datetime import datetime
from db_utils import insert_application_logs, get_chat_history
from google.cloud import storage
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Groq client
client = Groq(api_key="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")
folder_path = "db"

# GCP Storage configuration
BUCKET_NAME = os.environ.get('GCP_BUCKET_NAME', 'org_certificates')
GCP_CREDENTIALS_PATH = os.environ.get('GCP_CREDENTIALS_PATH', './plenary-plane-451914-q4-e51c16074922.json')

# Set GCP credentials environment variable
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GCP_CREDENTIALS_PATH

# Initialize GCP storage client
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

embedding = FastEmbedEmbeddings()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1024, chunk_overlap=80, length_function=len, is_separator_regex=False
)

complaint_prompt = PromptTemplate.from_template(
    """ 
    You are an AI assistant specializing in answering questions about various government schemes.  
Use the provided context to answer the user's query.  

If the context contains the relevant information, respond concisely and accurately based on the context.  
If the context does not include the necessary information to answer the query, reply with:  
"Sorry, the required information is not available in the provided context."  

Here is your task:  

**Query:** {input}  
**Context:** {context}  

"""
)

sample = Blueprint('sample', __name__)
CORS(sample)

def upload_to_gcs(file_obj, folder="pdfs"):
    """Upload a file to Google Cloud Storage and return its GCS path."""
    file_name = file_obj.filename
    unique_filename = f"{uuid.uuid4()}_{file_name}"
    blob_path = f"{folder}/{unique_filename}"
    
    blob = bucket.blob(blob_path)
    blob.upload_from_file(file_obj)
    
    return f"gs://{BUCKET_NAME}/{blob_path}"

def download_from_gcs(gcs_path):
    """Download a file from Google Cloud Storage to a temporary file and return the path."""
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_path = temp_file.name
    temp_file.close()
    
    # Extract blob path from gs:// URL
    if gcs_path.startswith('gs://'):
        path_parts = gcs_path[5:].split('/', 1)
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GCS path: {gcs_path}")
        bucket_name, blob_path = path_parts
        
        # Get the blob
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Download to temp file
        blob.download_to_filename(temp_path)
        return temp_path
    else:
        raise ValueError(f"Invalid GCS path: {gcs_path}")

@sample.route("/ask_pdf", methods=["POST"])
def askPDFPost():
    try:
        print("Post /ask_pdf called")
        json_content = request.json
        query = json_content.get("query")

        if not query:
            return {"error": "Query cannot be empty."}, 400

        print(f"Query received: {query}")

        # Load the vector store to retrieve relevant documents
        print("Loading vector store")
        vector_store = Chroma(persist_directory=folder_path, embedding_function=embedding)

        # Retrieve relevant documents based on the query
        print("Retrieving relevant documents")
        retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 5,  # Number of documents to retrieve
                "score_threshold": 0.1,
            }
        )
        docs = retriever.get_relevant_documents(query)
        print(f"Found {len(docs)} relevant documents")

        # Use Groq to process the query with retrieved context
        context = "\n".join(doc.page_content for doc in docs)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{query}\nContext: {context}",
                }
            ],
            model="llama-3.3-70b-versatile",
        )

        groq_response = chat_completion.choices[0].message.content
        print(f"Groq response: {groq_response}")

        sources = [{"source": doc.metadata.get("source"), "page_content": doc.page_content} for doc in docs]

        return jsonify({"answer": groq_response, "sources": sources}), 200

    except Exception as e:
        print(f"Error in askPDFPost: {e}")
        return {"error": f"An error occurred: {e}"}, 500

@sample.route("/pdf", methods=["POST"])
def pdfPost():
    try:
        # Get the uploaded file
        file = request.files["file"]
        file_name = file.filename

        print(f"Received file: {file_name}")

        # Upload to Google Cloud Storage
        gcs_path = upload_to_gcs(file)
        print(f"File uploaded to GCS: {gcs_path}")
        
        # Download to a temporary location for processing
        temp_file_path = download_from_gcs(gcs_path)
        print(f"File downloaded to temporary location: {temp_file_path}")

        # Load and split the PDF
        loader = PDFPlumberLoader(temp_file_path)
        docs = loader.load_and_split()
        print(f"Number of documents: {len(docs)}")

        # Add GCS source to document metadata
        for doc in docs:
            doc.metadata["source"] = gcs_path

        # Split documents into chunks
        chunks = text_splitter.split_documents(docs)
        print(f"Number of chunks: {len(chunks)}")

        # Store chunks in Chroma vector store
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embedding,
            persist_directory=folder_path
        )
        vector_store.persist()
        print("Vector store persisted successfully.")

        # Clean up temporary file
        os.remove(temp_file_path)
        print(f"Temporary file removed: {temp_file_path}")

        response = {
            "status": "Successfully Uploaded",
            "filename": file_name,
            "gcs_path": gcs_path,
            "doc_len": len(docs),
            "chunks": len(chunks),
        }
        return response, 200

    except Exception as e:
        print(f"Error in pdfPost: {e}")
        return {"error": str(e)}, 500