"""Vector database service using Cohere Embed v4 + Rerank v4 with ChromaDB storage."""
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import cohere
import chromadb
from chromadb.config import Settings

from ..config import settings
from ..utils.logger import logger


class VectorServiceCohere:
    """Service for embedding and vector search with Cohere APIs + ChromaDB."""

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

        # Cohere client and models
        self.co: Optional[cohere.Client] = None
        self.embed_model = "embed-v4.0"
        self.rerank_model = "rerank-v4.0-fast"
        self.dimensions = 1536  # Cohere embed-v4.0 default

        # For API compatibility with old interface
        self.model = None

        # Embedding cache to avoid redundant API calls
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_max_size = 1000

        # ChromaDB persistence path
        is_hf_spaces = os.getenv("SPACE_ID") is not None
        default_path = "/tmp/chroma_db" if is_hf_spaces else "./chroma_db"
        self.db_path = os.getenv("CHROMA_DB_PATH", default_path)

    def _init_cohere(self):
        """Initialize Cohere client lazily."""
        if self.co is None:
            api_key = settings.cohere_api_key
            if not api_key:
                raise ValueError("COHERE_API_KEY environment variable is required")
            self.co = cohere.Client(api_key=api_key)
            logger.info("Cohere client initialized")

    def _get_cache_key(self, text: str, input_type: str = "search_document") -> str:
        """Generate cache key from text hash and input type.

        Args:
            text: Text to hash
            input_type: Cohere input type

        Returns:
            MD5 hash string
        """
        return hashlib.md5(f"{text}:{input_type}".encode()).hexdigest()

    def _get_cached_embedding(self, text: str, input_type: str = "search_document") -> Optional[List[float]]:
        """Get embedding from cache if available.

        Args:
            text: Text to look up
            input_type: Cohere input type

        Returns:
            Cached embedding or None
        """
        cache_key = self._get_cache_key(text, input_type)
        return self._embedding_cache.get(cache_key)

    def _cache_embedding(self, text: str, embedding: List[float], input_type: str = "search_document") -> None:
        """Store embedding in cache.

        Args:
            text: Original text
            embedding: Computed embedding
            input_type: Cohere input type
        """
        # Evict oldest entry if cache is full (simple FIFO)
        if len(self._embedding_cache) >= self._cache_max_size:
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]

        cache_key = self._get_cache_key(text, input_type)
        self._embedding_cache[cache_key] = embedding

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
        """Initialize Cohere client (API-based, no local model).

        This method exists for API compatibility with the BGE-M3 version.
        """
        self._init_cohere()
        self.model = True  # Set to truthy value for compatibility checks
        logger.info("=" * 60)
        logger.info("Using Cohere embed-v4.0 API (no local model needed)")
        logger.info("Embedding: embed-v4.0 | Reranking: rerank-v4.0-fast")
        logger.info("=" * 60)

    def create_collection(self, dim: int = 1024):
        """Create or get ChromaDB collection.

        Args:
            dim: Dimension of dense embeddings (1024 for Cohere) - ignored in ChromaDB
        """
        # Ensure connected
        self._connect()

        try:
            # Get or create collection with cosine similarity
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Collection '{self.collection_name}' ready (ChromaDB + Cohere)")
        except Exception as e:
            logger.error(f"Failed to create/get collection: {e}")
            raise

    def embed_text(self, text: str, input_type: str = "search_document") -> Tuple[List[float], Dict[str, float]]:
        """Embed text using Cohere API with caching.

        Args:
            text: Text to embed
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            Tuple of (dense_vector, empty_dict_for_compatibility)
        """
        # Check cache first
        cached = self._get_cached_embedding(text, input_type)
        if cached is not None:
            return cached, {}

        # Initialize Cohere if needed
        self._init_cohere()

        try:
            response = self.co.embed(
                texts=[text],
                model=self.embed_model,
                input_type=input_type,
                embedding_types=["float"],
                truncate="END"
            )
            embedding = list(response.embeddings.float_[0])

            # Cache the result
            self._cache_embedding(text, embedding, input_type)

            return embedding, {}
        except Exception as e:
            logger.error(f"Cohere embed failed: {e}")
            raise

    def _embed_batch(self, texts: List[str], input_type: str = "search_document") -> List[List[float]]:
        """Embed multiple texts in batch using Cohere API.

        Args:
            texts: List of texts to embed
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            List of dense vectors
        """
        if not texts:
            return []

        # Initialize Cohere if needed
        self._init_cohere()

        all_embeddings = []
        batch_size = 96  # Cohere limit

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = self.co.embed(
                    texts=batch,
                    model=self.embed_model,
                    input_type=input_type,
                    embedding_types=["float"],
                    truncate="END"
                )
                batch_embeddings = [list(e) for e in response.embeddings.float_]
                all_embeddings.extend(batch_embeddings)

                logger.debug(f"Embedded batch {i // batch_size + 1}: {len(batch)} texts")
            except Exception as e:
                logger.error(f"Cohere batch embed failed: {e}")
                raise

        return all_embeddings

    def rerank(self, query: str, documents: List[str], top_n: int = 10) -> List[Dict[str, Any]]:
        """Rerank documents by relevance to query using Cohere.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_n: Number of top results to return

        Returns:
            List of dicts with index, text, and score
        """
        if not documents:
            return []

        # Initialize Cohere if needed
        self._init_cohere()

        try:
            response = self.co.rerank(
                query=query,
                documents=documents,
                model=self.rerank_model,
                top_n=min(top_n, len(documents)),
                return_documents=True
            )

            results = []
            for r in response.results:
                results.append({
                    "index": r.index,
                    "text": r.document.text,
                    "score": r.relevance_score
                })

            logger.debug(f"Reranked {len(documents)} docs, returning top {len(results)}")
            return results
        except Exception as e:
            logger.error(f"Cohere rerank failed: {e}")
            raise

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

        # Initialize Cohere if needed
        self._init_cohere()

        # Prepare data for insertion
        ids = []
        metadatas = []
        documents = []

        # Extract texts for batch embedding
        texts = [chunk["text"] for chunk in chunks]

        # Batch embed all chunks using Cohere API
        logger.info(f"Embedding {len(texts)} chunks for {domain}/{page_name} via Cohere API...")
        embeddings = self._embed_batch(texts, input_type="search_document")

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
        top_k: int = 30,
        rerank_top_n: int = 10,
        filter_domain: Optional[str] = None,
        filter_site: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks using Cohere embed + rerank.

        Args:
            query: Search query
            top_k: Number of candidates to retrieve from ChromaDB
            rerank_top_n: Number of results to return after reranking
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

        # Initialize Cohere
        self._init_cohere()

        # Embed query using search_query input type
        dense_vec, _ = self.embed_text(query, input_type="search_query")

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
            logger.error(f"ChromaDB search failed: {e}")
            return []

        # Check if we got results
        if not results['ids'] or not results['ids'][0]:
            logger.info(f"Search for '{query}' returned 0 results")
            return []

        # Rerank results using Cohere
        documents = results['documents'][0]
        reranked = self.rerank(query, documents, top_n=rerank_top_n)

        # Map reranked results back to original metadata
        formatted_results = []
        for r in reranked:
            idx = r['index']
            formatted_results.append({
                "chunk_id": results['metadatas'][0][idx]["chunk_id"],
                "domain": results['metadatas'][0][idx]["domain"],
                "site_name": results['metadatas'][0][idx]["site_name"],
                "page_name": results['metadatas'][0][idx]["page_name"],
                "page_url": results['metadatas'][0][idx]["page_url"],
                "chunk_text": r['text'],
                "score": r['score'],
            })

        logger.info(f"Search for '{query}': {top_k} candidates → {len(formatted_results)} reranked results")
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

    def clear_collection(self):
        """Clear all data from the collection by deleting and recreating it."""
        self._connect()

        try:
            # Delete the collection if it exists
            try:
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted collection '{self.collection_name}'")
            except Exception:
                pass  # Collection may not exist yet

            # Recreate empty collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Recreated empty collection '{self.collection_name}'")

            # Clear embedding cache
            self._embedding_cache.clear()

        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise

    def close(self):
        """Close connections."""
        self.collection = None
        self.client = None
        self.connected = False
        self.co = None
        logger.info("Cohere + ChromaDB connections closed")


# Global instance
vector_service = VectorServiceCohere()
