"""Vector database service using ChromaDB with BGE-M3 embeddings and ZeroGPU acceleration."""
import os
# Disable HuggingFace progress bars and multiprocessing before any imports
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import chromadb
from chromadb.config import Settings
from FlagEmbedding import BGEM3FlagModel

from ..config import settings
from ..utils.logger import logger

# Try to import spaces for ZeroGPU, but don't fail if not available (local dev)
try:
    import spaces
    HAS_ZEROGPU = True
except ImportError:
    HAS_ZEROGPU = False
    # Create a no-op decorator for local development
    class spaces:
        @staticmethod
        def GPU(func):
            return func


class VectorServiceChroma:
    """Service for embedding and vector search with ChromaDB + BGE-M3."""

    def __init__(
        self,
        collection_name: str = "scraped_sites",
        milvus_host: str = None,  # Kept for API compatibility
        milvus_port: int = 19530,  # Kept for API compatibility
    ):
        """Initialize the vector service.

        Args:
            collection_name: Name of the ChromaDB collection
            milvus_host: Ignored (kept for compatibility)
            milvus_port: Ignored (kept for compatibility)
        """
        self.collection_name = collection_name
        self.client: Optional[chromadb.ClientAPI] = None
        self.collection = None
        self.connected = False

        # BGE-M3 model for dense embeddings
        self.model: Optional[BGEM3FlagModel] = None

        # ChromaDB persistence path
        self.db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")

    def _connect(self):
        """Initialize ChromaDB client (lazy initialization)."""
        if self.connected:
            return

        try:
            # Create persistent ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            self.connected = True
            logger.info(f"Connected to ChromaDB at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB at {self.db_path}: {e}")
            raise

    def load_model(self):
        """Load BGE-M3 embedding model."""
        if self.model is None:
            try:
                # Set PyTorch threads to 1 to prevent segfaults in Docker
                import torch
                import time
                torch.set_num_threads(1)

                logger.info("=" * 60)
                logger.info("Loading BGE-M3 embedding model...")
                logger.info("This may take 2-5 minutes on first run (downloading ~2GB)")
                logger.info("=" * 60)

                start_time = time.time()
                self.model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
                elapsed = time.time() - start_time

                logger.info(f"✓ BGE-M3 model loaded successfully in {elapsed:.1f}s")
            except Exception as e:
                logger.error(f"✗ Failed to load BGE-M3 model: {e}", exc_info=True)
                raise

    def create_collection(self, dim: int = 1024):
        """Create or get ChromaDB collection.

        Args:
            dim: Dimension of dense embeddings (BGE-M3 uses 1024) - ignored in ChromaDB
        """
        # Ensure connected
        self._connect()

        try:
            # Get or create collection with cosine similarity (equivalent to IP for normalized vectors)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
            logger.info(f"Collection '{self.collection_name}' ready (ChromaDB)")
        except Exception as e:
            logger.error(f"Failed to create/get collection: {e}")
            raise

    @spaces.GPU if HAS_ZEROGPU else lambda f: f
    def embed_text(self, text: str) -> Tuple[List[float], Dict[str, float]]:
        """Embed text using BGE-M3 with GPU acceleration (if available).

        Args:
            text: Text to embed

        Returns:
            Tuple of (dense_vector, sparse_vector_dict)
            Note: sparse_vector_dict is empty for ChromaDB (kept for compatibility)
        """
        if self.model is None:
            self.load_model()

        # BGE-M3 returns dense, sparse, and colbert embeddings
        # We'll use dense for ChromaDB
        embeddings = self.model.encode(
            [text],
            return_dense=True,
            return_sparse=False,  # Don't need sparse for ChromaDB
            return_colbert_vecs=False
        )

        dense_vector = embeddings['dense_vecs'][0].tolist()
        sparse_vector = {}  # Empty dict for compatibility

        return dense_vector, sparse_vector

    @spaces.GPU if HAS_ZEROGPU else lambda f: f
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in batch (GPU-accelerated).

        Args:
            texts: List of texts to embed

        Returns:
            List of dense vectors
        """
        if self.model is None:
            self.load_model()

        embeddings = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False
        )

        return embeddings['dense_vecs'].tolist()

    def chunk_markdown(self, markdown: str, page_name: str, max_chunk_size: int = 4000) -> List[Dict[str, str]]:
        """Chunk markdown intelligently for embedding.

        Args:
            markdown: Cleaned markdown content
            page_name: Name of the page (for metadata)
            max_chunk_size: Maximum characters per chunk (default 4000)

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
                    # Ensure chunk is under 8000 chars (safety margin)
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
                # Ensure chunk is under 8000 chars (safety margin)
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
        site_name: str,
        page_name: str,
        page_url: str,
        chunks: List[Dict[str, str]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """Insert chunked and embedded text into ChromaDB.

        Args:
            domain: Website domain
            site_name: Website/site name
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
        ids = []
        embeddings = []
        metadatas = []
        documents = []

        # Extract texts for batch embedding
        texts = [chunk["text"] for chunk in chunks]

        # Batch embed all chunks (GPU-accelerated if available)
        logger.info(f"Embedding {len(texts)} chunks for {domain}/{page_name}...")
        embeddings = self._embed_batch(texts)

        # Prepare for ChromaDB insertion
        for i, chunk in enumerate(chunks):
            chunk_id = f"{domain}_{page_name}_{i}"
            chunk_text = chunk["text"]

            ids.append(chunk_id)
            # ChromaDB document text (limited to 8000 chars for safety)
            safe_chunk_text = chunk_text[:8000] if len(chunk_text) > 8000 else chunk_text
            documents.append(safe_chunk_text)
            metadatas.append({
                "domain": domain,
                "site_name": site_name,
                "page_name": page_name,
                "page_url": page_url,
                "chunk_id": chunk_id
            })

            # Report progress if callback provided
            if progress_callback:
                progress_callback(i + 1, len(chunks))

        # Insert into ChromaDB
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            logger.info(f"Inserted {len(chunks)} chunks for {domain}/{page_name}")
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_domain: Optional[str] = None,
        filter_site: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks using dense search.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_domain: Optional domain filter
            filter_site: Optional site name filter

        Returns:
            List of search results with chunks and metadata
        """
        # Connect and get collection if not already done
        if self.collection is None:
            self._connect()
            try:
                self.collection = self.client.get_collection(self.collection_name)
            except Exception:
                logger.error(f"Collection '{self.collection_name}' does not exist")
                return []

        # Embed query (GPU-accelerated if available)
        dense_vec, _ = self.embed_text(query)

        # Build filter for ChromaDB
        where_filter = {}
        if filter_domain and filter_site:
            where_filter = {
                "$and": [
                    {"domain": {"$eq": filter_domain}},
                    {"site_name": {"$eq": filter_site}}
                ]
            }
        elif filter_domain:
            where_filter = {"domain": {"$eq": filter_domain}}
        elif filter_site:
            where_filter = {"site_name": {"$eq": filter_site}}

        # Search in ChromaDB
        try:
            results = self.collection.query(
                query_embeddings=[dense_vec],
                n_results=top_k,
                where=where_filter if where_filter else None
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        # Format results to match Milvus format
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "chunk_id": results['metadatas'][0][i]["chunk_id"],
                    "domain": results['metadatas'][0][i]["domain"],
                    "site_name": results['metadatas'][0][i]["site_name"],
                    "page_name": results['metadatas'][0][i]["page_name"],
                    "page_url": results['metadatas'][0][i]["page_url"],
                    "chunk_text": results['documents'][0][i],
                    "score": 1.0 - results['distances'][0][i],  # ChromaDB returns distance, convert to similarity
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

        try:
            self.collection.delete(
                where={"domain": {"$eq": domain}}
            )
            logger.info(f"Deleted all chunks for domain: {domain}")
        except Exception as e:
            logger.error(f"Failed to delete chunks for domain {domain}: {e}")
            raise

    def close(self):
        """Close ChromaDB connection."""
        # ChromaDB doesn't require explicit cleanup
        self.collection = None
        self.client = None
        self.connected = False
        logger.info("ChromaDB connection closed")


# Global instance
vector_service = VectorServiceChroma()
