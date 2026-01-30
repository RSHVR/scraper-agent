"""RAG tools wrapping existing VectorServiceCohere for LangChain agents."""

from typing import Any
from langchain_core.tools import tool
from urllib.parse import urlparse

from ..services.vector_service_cohere import VectorServiceCohere
from ..services.html_cleaner import HTMLCleaner


def create_rag_tool(vector_service: VectorServiceCohere):
    """
    Create a LangChain tool for searching the knowledge base.

    This tool allows the agent to search previously embedded content.

    Args:
        vector_service: The VectorServiceCohere instance to wrap

    Returns:
        A LangChain @tool for searching content
    """

    @tool
    def search_knowledge_base(query: str) -> str:
        """Search the knowledge base for previously scraped and embedded content. Use this to find information from websites that have been scraped before. Input should be a natural language query describing what you're looking for."""
        import json

        try:
            results = vector_service.search(
                query=query,
                top_k=30,
                rerank_top_n=10
            )

            if not results:
                return json.dumps({
                    "success": True,
                    "results": [],
                    "message": "No relevant content found in the knowledge base."
                })

            # Format results
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "page_name": r.get('page_name', 'Unknown'),
                    "url": r.get('url', ''),
                    "content": r.get('content', '')[:500]
                })

            return json.dumps({
                "success": True,
                "results": formatted_results,
                "count": len(formatted_results)
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Search failed: {str(e)}"
            })

    return search_knowledge_base


def create_embed_tool(vector_service: VectorServiceCohere, cleaner: HTMLCleaner):
    """
    Create a LangChain tool for embedding content.

    Args:
        vector_service: The VectorServiceCohere instance
        cleaner: The HTMLCleaner for chunking content

    Returns:
        A LangChain @tool for embedding content
    """

    @tool
    def embed_content(
        content: str,
        url: str,
        title: str = "untitled",
        page_name: str = "page"
    ) -> str:
        """Embed content into the knowledge base for later retrieval. Use this to save extracted content for future searches."""
        import json

        try:
            # Chunk the content
            chunks = cleaner.clean_and_chunk(content, page_name=title)

            # Extract domain from URL
            domain = urlparse(url).netloc

            # Insert into vector store
            vector_service.insert_chunks(
                domain=domain,
                site_name=title,
                page_name=page_name,
                page_url=url,
                chunks=chunks
            )

            return json.dumps({
                "success": True,
                "embedded": True,
                "chunks_count": len(chunks),
                "domain": domain
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Embedding failed: {str(e)}"
            })

    return embed_content
