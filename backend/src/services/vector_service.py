"""Vector database service using Milvus with BGE-M3 embeddings."""
import os
# Disable HuggingFace progress bars and multiprocessing before any imports
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from FlagEmbedding import BGEM3FlagModel

from ..config import settings
from ..utils.logger import logger
from .html_cleaner import html_cleaner


class VectorService:
    """Service for embedding and vector search with Milvus + BGE-M3."""

    def __init__(
        self,
        collection_name: str = "gym_sites",
        milvus_host: str = None,
        milvus_port: int = 19530,
    ):
        """Initialize the vector service.

        Args:
            collection_name: Name of the Milvus collection
            milvus_host: Milvus server host (defaults to env var or 'localhost')
            milvus_port: Milvus server port
        """
        import os

        self.collection_name = collection_name
        # Get host from environment or parameter or default to localhost
        self.milvus_host = milvus_host or os.getenv("MILVUS_HOST", "localhost")
        self.milvus_port = int(os.getenv("MILVUS_PORT", milvus_port))
        self.collection: Optional[Collection] = None
        self.connected = False

        # BGE-M3 model for hybrid dense + sparse embeddings
        self.model: Optional[BGEM3FlagModel] = None

    def _connect(self):
        """Connect to Milvus server (lazy initialization)."""
        if self.connected:
            return

        try:
            # Connect to standalone Milvus server
            connections.connect(
                alias="default",
                host=self.milvus_host,
                port=self.milvus_port,
            )
            self.connected = True
            logger.info(f"Connected to Milvus at {self.milvus_host}:{self.milvus_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus at {self.milvus_host}:{self.milvus_port}: {e}")
            raise

    def load_model(self):
        """Load BGE-M3 embedding model."""
        if self.model is None:
            # Set PyTorch threads to 1 to prevent segfaults in Docker
            import torch
            torch.set_num_threads(1)

            logger.info("Loading BGE-M3 embedding model...")
            self.model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
            logger.info("BGE-M3 model loaded successfully")

    def create_collection(self, dim: int = 1024):
        """Create Milvus collection with hybrid search support.

        Args:
            dim: Dimension of dense embeddings (BGE-M3 uses 1024)
        """
        # Ensure connected
        self._connect()

        if utility.has_collection(self.collection_name):
            logger.info(f"Collection '{self.collection_name}' already exists")
            self.collection = Collection(self.collection_name)
            return

        # Define collection schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="domain", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="gym_name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="page_name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="page_url", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            # Note: Milvus v2.4+ supports sparse vectors, but we'll use dense for now
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Gym website chunks with BGE-M3 embeddings"
        )

        self.collection = Collection(
            name=self.collection_name,
            schema=schema,
            using="default"
        )

        # Create index for dense vectors (HNSW for fast ANN search)
        index_params = {
            "metric_type": "IP",  # Inner product (cosine similarity for normalized vectors)
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200}
        }

        self.collection.create_index(
            field_name="dense_vector",
            index_params=index_params
        )

        logger.info(f"Created collection '{self.collection_name}' with HNSW index")

    def embed_text(self, text: str) -> Tuple[List[float], Dict[str, float]]:
        """Embed text using BGE-M3 (dense + sparse).

        Args:
            text: Text to embed

        Returns:
            Tuple of (dense_vector, sparse_vector_dict)
        """
        if self.model is None:
            self.load_model()

        # BGE-M3 returns dense, sparse, and colbert embeddings
        # We'll use dense for now (sparse requires Milvus v2.4+ full support)
        embeddings = self.model.encode(
            [text],
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False
        )

        dense_vector = embeddings['dense_vecs'][0].tolist()
        sparse_vector = embeddings['lexical_weights'][0]  # Dict format

        return dense_vector, sparse_vector

    def chunk_html(self, html: str, page_name: str, max_chunk_size: int = 1000) -> List[Dict[str, str]]:
        """Chunk HTML intelligently for embedding using HTML cleaner.

        Args:
            html: Raw HTML content
            page_name: Name of the page (for metadata)
            max_chunk_size: Maximum characters per chunk

        Returns:
            List of chunk dicts with text and metadata
        """
        # Use HTML cleaner to extract clean, structured chunks
        chunks = html_cleaner.clean_and_chunk(
            html=html,
            page_name=page_name,
            chunk_size=max_chunk_size,
            overlap=200  # 20% overlap for context
        )

        logger.debug(f"Chunked '{page_name}' into {len(chunks)} clean chunks")
        return chunks

    def chunk_markdown(self, markdown: str, page_name: str, max_chunk_size: int = 4000) -> List[Dict[str, str]]:
        """Chunk markdown intelligently for embedding.

        Args:
            markdown: Cleaned markdown content
            page_name: Name of the page (for metadata)
            max_chunk_size: Maximum characters per chunk (default 4000 to stay well below 8192 limit)

        Returns:
            List of chunk dicts with text and metadata
        """
        if not markdown or not markdown.strip():
            return []

        chunks = []
        lines = markdown.split('\n')
        current_chunk = []
        current_size = 0
        current_heading = ""

        for line in lines:
            # Track headings for context
            if line.startswith('#'):
                current_heading = line.strip('# ').strip()

            line_len = len(line) + 1  # +1 for newline

            # If adding this line would exceed max size, save current chunk
            if current_size + line_len > max_chunk_size and current_chunk:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    # Ensure chunk is under 8000 chars (safety margin for 8192 limit)
                    if len(chunk_text) > 8000:
                        chunk_text = chunk_text[:8000]
                    chunks.append({
                        "text": chunk_text,
                        "heading": current_heading,
                        "page_name": page_name
                    })
                current_chunk = [line]
                current_size = line_len
            else:
                current_chunk.append(line)
                current_size += line_len

        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                # Ensure chunk is under 8000 chars (safety margin for 8192 limit)
                if len(chunk_text) > 8000:
                    chunk_text = chunk_text[:8000]
                chunks.append({
                    "text": chunk_text,
                    "heading": current_heading,
                    "page_name": page_name
                })

        logger.debug(f"Chunked '{page_name}' into {len(chunks)} markdown chunks")
        return chunks

    def insert_chunks(
        self,
        domain: str,
        gym_name: str,
        page_name: str,
        page_url: str,
        chunks: List[Dict[str, str]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """Insert chunked and embedded text into Milvus.

        Args:
            domain: Website domain
            gym_name: Gym/studio name
            page_name: Page name
            page_url: Page URL
            chunks: List of text chunks
            progress_callback: Optional callback function(current, total) for progress tracking
        """
        if self.collection is None:
            self.create_collection()

        if not chunks:
            logger.warning(f"No chunks to insert for {page_url}")
            return

        # Load model if needed
        if self.model is None:
            self.load_model()

        # Prepare data for insertion
        chunk_ids = []
        domains = []
        gym_names = []
        page_names = []
        page_urls = []
        chunk_texts = []
        dense_vectors = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{domain}_{page_name}_{i}"
            chunk_text = chunk["text"]

            # Embed chunk
            dense_vec, sparse_vec = self.embed_text(chunk_text)

            chunk_ids.append(chunk_id)
            domains.append(domain)
            gym_names.append(gym_name)
            page_names.append(page_name)
            page_urls.append(page_url)
            # Ensure text is well under 8192 limit (use 8000 for safety)
            safe_chunk_text = chunk_text[:8000] if len(chunk_text) > 8000 else chunk_text
            chunk_texts.append(safe_chunk_text)
            dense_vectors.append(dense_vec)

            # Report progress if callback provided
            if progress_callback:
                progress_callback(i + 1, len(chunks))

        # Insert into Milvus
        data = [
            chunk_ids,
            domains,
            gym_names,
            page_names,
            page_urls,
            chunk_texts,
            dense_vectors,
        ]

        self.collection.insert(data)
        # Note: flush() is optional and can cause issues with Milvus Lite
        # Data will be persisted automatically

        logger.info(f"Inserted {len(chunks)} chunks for {domain}/{page_name}")

    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_domain: Optional[str] = None,
        filter_gym: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks using hybrid dense search.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_domain: Optional domain filter
            filter_gym: Optional gym name filter

        Returns:
            List of search results with chunks and metadata
        """
        # Connect and get collection if not already done
        if self.collection is None:
            self._connect()
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
            else:
                logger.error(f"Collection '{self.collection_name}' does not exist")
                return []

        # Load collection into memory
        self.collection.load()

        # Embed query
        dense_vec, sparse_vec = self.embed_text(query)

        # Build filter expression
        filter_expr = None
        if filter_domain:
            filter_expr = f'domain == "{filter_domain}"'
        if filter_gym:
            gym_filter = f'gym_name == "{filter_gym}"'
            filter_expr = f"{filter_expr} && {gym_filter}" if filter_expr else gym_filter

        # Search with dense vectors
        search_params = {
            "metric_type": "IP",
            "params": {"ef": 64}
        }

        results = self.collection.search(
            data=[dense_vec],
            anns_field="dense_vector",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=["chunk_id", "domain", "gym_name", "page_name", "page_url", "chunk_text"]
        )

        # Format results
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "chunk_id": hit.entity.get("chunk_id"),
                    "domain": hit.entity.get("domain"),
                    "gym_name": hit.entity.get("gym_name"),
                    "page_name": hit.entity.get("page_name"),
                    "page_url": hit.entity.get("page_url"),
                    "chunk_text": hit.entity.get("chunk_text"),
                    "score": hit.score,
                })

        logger.info(f"Search for '{query}' returned {len(formatted_results)} results")
        return formatted_results

    def delete_by_domain(self, domain: str):
        """Delete all chunks for a specific domain.

        Args:
            domain: Domain to delete
        """
        if self.collection is None:
            logger.error("Collection not loaded")
            return

        expr = f'domain == "{domain}"'
        self.collection.delete(expr)
        logger.info(f"Deleted all chunks for domain: {domain}")

    def close(self):
        """Close Milvus connection."""
        if self.collection:
            self.collection.release()
        connections.disconnect("default")
        logger.info("Disconnected from Milvus")


# Global instance
vector_service = VectorService()
