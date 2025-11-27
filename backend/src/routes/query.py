"""Query/search routes for RAG."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import anthropic

from ..services import vector_service
from ..config import settings
from ..utils.logger import logger

router = APIRouter(prefix="/api/query", tags=["query"])


class QueryRequest(BaseModel):
    """Request model for vector search queries."""

    query: str = Field(..., description="Search query text")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    filter_domain: Optional[str] = Field(default=None, description="Filter results by domain")
    filter_gym: Optional[str] = Field(default=None, description="Filter results by gym name")


class SearchResult(BaseModel):
    """Single search result."""

    chunk_id: str
    domain: str
    gym_name: str
    page_name: str
    page_url: str
    chunk_text: str
    score: float


class QueryResponse(BaseModel):
    """Response model for vector search queries."""

    query: str
    results: List[SearchResult]
    total_results: int


@router.post("/search", response_model=QueryResponse)
async def search(request: QueryRequest):
    """Search for relevant content using vector similarity.

    This endpoint performs semantic search over embedded gym/fitness website content.

    Args:
        request: Query request with search parameters

    Returns:
        Search results with relevant chunks and metadata

    Raises:
        HTTPException: If search fails
    """
    try:
        logger.info(f"Processing search query: '{request.query}' (top_k={request.top_k})")

        # Perform vector search
        results = vector_service.search(
            query=request.query,
            top_k=request.top_k,
            filter_domain=request.filter_domain,
            filter_gym=request.filter_gym
        )

        # Convert to response format
        search_results = [
            SearchResult(
                chunk_id=result["chunk_id"],
                domain=result["domain"],
                gym_name=result["gym_name"],
                page_name=result["page_name"],
                page_url=result["page_url"],
                chunk_text=result["chunk_text"],
                score=result["score"]
            )
            for result in results
        ]

        logger.info(f"Search completed: {len(search_results)} results found")

        return QueryResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results)
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


class AskRequest(BaseModel):
    """Request model for Claude-powered Q&A."""

    question: str = Field(..., description="Question to ask about the gyms")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of chunks to retrieve")
    filter_domain: Optional[str] = Field(default=None, description="Filter results by domain")
    filter_gym: Optional[str] = Field(default=None, description="Filter results by gym name")


class AskResponse(BaseModel):
    """Response model for Claude-powered Q&A."""

    question: str
    answer: str
    optimized_query: str
    sources_used: int
    sources: List[dict]


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Ask a question and get a natural language answer from Claude using RAG.

    This endpoint implements a 3-stage RAG pipeline:
    1. Query Rewriting: Claude Haiku optimizes the query for semantic search
    2. Vector Search: Retrieve relevant chunks using BGE-M3 embeddings
    3. Answer Synthesis: Claude Sonnet generates a natural language response

    Args:
        request: Question and search parameters

    Returns:
        Natural language answer with source citations

    Raises:
        HTTPException: If query or answer generation fails
    """
    try:
        logger.info(f"Processing question: '{request.question}'")

        # Initialize Claude client
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # ========================================
        # STAGE 1: Query Rewriting with Claude Haiku
        # ========================================
        query_rewrite_prompt = f"""Given this user question about gyms/fitness studios, rewrite it as an optimized search query.

User Question: {request.question}

Instructions:
- Extract key concepts and keywords
- Add relevant synonyms and related terms
- Keep it concise (2-10 words)
- Focus on terms likely to appear in gym website content
- Do not add quotes or special characters

Return ONLY the optimized search query, nothing else."""

        query_message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            messages=[
                {"role": "user", "content": query_rewrite_prompt}
            ]
        )

        optimized_query = query_message.content[0].text.strip()
        logger.info(f"Optimized query: '{optimized_query}'")

        # ========================================
        # STAGE 2: Vector Search
        # ========================================
        results = vector_service.search(
            query=optimized_query,
            top_k=request.top_k,
            filter_domain=request.filter_domain,
            filter_gym=request.filter_gym
        )

        if not results:
            return AskResponse(
                question=request.question,
                answer="I don't have any information about that in my database. Please try rephrasing your question or asking about a different topic.",
                optimized_query=optimized_query,
                sources_used=0,
                sources=[]
            )

        # ========================================
        # STAGE 3: Answer Synthesis with Claude Sonnet
        # ========================================

        # Build context from retrieved chunks
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[Source {i} - {result['gym_name']} - {result['page_name']}]\n"
                f"{result['chunk_text']}\n"
            )

        context = "\n---\n".join(context_parts)

        system_prompt = """You are a helpful assistant answering questions about gyms and fitness studios.

You will be provided with relevant information extracted from gym websites. Use this information to answer the user's question accurately and naturally.

Guidelines:
- Provide a clear, concise answer based ONLY on the information given
- If multiple gyms are mentioned, organize the information clearly
- Include specific details like addresses, prices, class types, hours when available
- If the provided information doesn't fully answer the question, acknowledge what you can answer
- Be conversational and helpful
- Cite gym names when providing specific information
- Don't make up information not present in the sources"""

        user_prompt = f"""Based on the following information from gym websites, please answer this question:

Question: {request.question}

Relevant Information from Gym Websites:
{context}

Please provide a natural, helpful answer based on this information."""

        answer_message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        answer = answer_message.content[0].text

        # Prepare sources for response
        sources = [
            {
                "gym_name": result["gym_name"],
                "page_name": result["page_name"],
                "page_url": result["page_url"],
                "score": result["score"]
            }
            for result in results
        ]

        logger.info(f"Generated answer using {len(results)} sources")

        return AskResponse(
            question=request.question,
            answer=answer,
            optimized_query=optimized_query,
            sources_used=len(results),
            sources=sources
        )

    except Exception as e:
        logger.error(f"Question answering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(e)}")


@router.get("/health")
async def health_check():
    """Check if vector service is ready.

    Returns:
        Health status of vector database
    """
    try:
        # Try to connect to Milvus
        vector_service._connect()
        return {
            "status": "healthy",
            "service": "vector_search",
            "collection": vector_service.collection_name
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "vector_search",
            "error": str(e)
        }
