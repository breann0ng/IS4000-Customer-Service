"""Configuration for the document ingestion pipeline."""

from pydantic_settings import BaseSettings


class PipelineSettings(BaseSettings):
    """Settings for document ingestion and vector store configuration."""

    docs_directory: str = "./docs"
    chroma_persist_directory: str = "./data/chroma"
    chroma_collection_name: str = "customer_service_docs"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    models_directory: str = "./models"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    similarity_metric: str = "cosine"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


pipeline_settings = PipelineSettings()
