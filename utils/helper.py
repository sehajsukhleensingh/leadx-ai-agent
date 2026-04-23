import uuid # library to generate a new random thread ID 
import sqlite3 # lib to connect to sqlite database 
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langsmith import traceable
import json
from dotenv import load_dotenv
import os 

load_dotenv()

class Utility:
    
    @staticmethod
    @traceable(name="helper : fetch_prompts")
    def fetch_prompt(path: str):
        """Load prompt template from markdown file for LLM chain usage.
        
        Input: File path to prompt template (e.g., 'prompts/intent_classification.md').
        Output: Complete prompt text ready for template variable substitution.
        """
        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    @staticmethod
    @traceable(name="helper : flatten_json_kb")
    def flatten_autostream_json(data):
        """Transform knowledge base JSON into readable text for embedding.
        
        Input: Parsed JSON data from knowledge_base.json containing pricing and features.
        Output: Formatted plaintext with structured pricing tiers and feature lists for vector embedding.
        """
        text_parts = []

        text_parts.append("AUTOSTREAM KNOWLEDGE BASE\n")

        text_parts.append("PRICING:")
        for plan in data.get("pricing", {}).get("plans", []):
            text_parts.append(f"- {plan['name']} Plan: ${plan['price']}/{plan['billing']}")
            for feature in plan.get("features", []):
                text_parts.append(f"  • {feature}")

        return "\n".join(text_parts)

    @staticmethod
    @traceable(name="helper : vectordb_setup")
    def create_vector_store():
        """Build FAISS vector store from knowledge base and cache to disk.
        
        Loads knowledge base JSON, formats it, chunks text, generates embeddings via HuggingFace,
        and saves the FAISS index locally for fast retrieval on subsequent calls.
        Output: FAISS vector store ready for similarity search.
        """
        with open("database/knowledge_base.json", "r", encoding="utf-8") as file:
            data = json.load(file)

        text = Utility.flatten_autostream_json(data)

        splitter = RecursiveCharacterTextSplitter(chunk_size = 250 , chunk_overlap = 50)
        docs = splitter.create_documents([text])

        embedder =  HuggingFaceEndpointEmbeddings(
                model = "BAAI/bge-base-en-v1.5" , 
                huggingfacehub_api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
            )
         
        vector_store = FAISS.from_documents(docs , embedder )
        os.makedirs("database/vectordb" , exist_ok=True)
        vector_store.save_local("database/vectordb")
        return vector_store
    
    @staticmethod
    @traceable(name="helper : lead_cap_tool")
    def mock_lead_capture(name, email, platform):
        """Log captured lead information to console.
        
        Input: name (string), email (validated email string), platform (social media platform name).
        In production, this would save to a database or CRM system.
        """
        print(f"Lead captured successfully: {name}, {email}, {platform}")