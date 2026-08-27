"""
Feedback Intelligence Agent.
Retrieves and analyzes customer feedback using RAG and clustering.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.feedback_agent.rag import get_retriever, HybridRetriever, get_ingestion_pipeline
from agents.feedback_agent.clustering import cluster_feedback, FeedbackCluster
from config.settings import settings


def _create_llm():
    """Create LLM instance based on provider (OpenAI or OpenRouter)."""
    if settings.llm_provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": settings.openrouter_http_referer or "",
                "X-Title": settings.openrouter_x_title or "",
            } if settings.openrouter_http_referer or settings.openrouter_x_title else None,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key,
            organization=settings.openai_organization,
        )


@dataclass
class FeedbackAgentState:
    """State for Feedback Agent."""
    question: str
    search_query: str
    filter: Dict[str, Any]
    retrieved_chunks: List[Any] = field(default_factory=list)
    clusters: List[FeedbackCluster] = field(default_factory=list)
    themes: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    done: bool = False


class FeedbackIntelligenceAgent:
    """Agent for retrieving and analyzing customer feedback."""
    
    def __init__(self):
        self.llm = _create_llm()
        self.retriever = get_retriever()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(FeedbackAgentState)
        
        # Nodes
        workflow.add_node("generate_search_query", self._generate_search_query_node)
        workflow.add_node("retrieve_feedback", self._retrieve_feedback_node)
        workflow.add_node("cluster_feedback", self._cluster_feedback_node)
        workflow.add_node("extract_themes", self._extract_themes_node)
        workflow.add_node("synthesize_evidence", self._synthesize_evidence_node)
        
        # Edges
        workflow.set_entry_point("generate_search_query")
        workflow.add_edge("generate_search_query", "retrieve_feedback")
        workflow.add_edge("retrieve_feedback", "cluster_feedback")
        workflow.add_edge("cluster_feedback", "extract_themes")
        workflow.add_edge("extract_themes", "synthesize_evidence")
        workflow.add_edge("synthesize_evidence", END)
        
        return workflow.compile()
    
    def _generate_search_query_node(self, state: FeedbackAgentState) -> FeedbackAgentState:
        """Generate optimized search query from question."""
        prompt = f"""
        Convert the following question into an effective search query for retrieving 
        relevant customer feedback (support tickets, NPS responses, reviews, feature requests).
        
        Question: {state.question}
        
        The search query should:
        1. Focus on key terms, product areas, and problem descriptions
        2. Include relevant synonyms
        3. Be concise but comprehensive
        
        Return only the search query string.
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        search_query = response.content.strip()
        
        # Determine filters based on question
        filter_dict = {}
        question_lower = state.question.lower()
        
        if "bug" in question_lower or "crash" in question_lower:
            filter_dict["sentiment"] = "negative"
        if "feature" in question_lower or "request" in question_lower:
            filter_dict["source"] = "feature_request"
        if "mobile" in question_lower or "app" in question_lower:
            filter_dict["product_area"] = "mobile"
        
        return FeedbackAgentState(
            question=state.question,
            search_query=search_query,
            filter=filter_dict,
        )
    
    def _retrieve_feedback_node(self, state: FeedbackAgentState) -> FeedbackAgentState:
        """Retrieve relevant feedback chunks."""
        try:
            chunks = self.retriever.retrieve(
                query=state.search_query,
                filter=state.filter,
                k=settings.rag_top_k * 2,  # Get more for clustering
            )
            return FeedbackAgentState(
                question=state.question,
                search_query=state.search_query,
                filter=state.filter,
                retrieved_chunks=chunks,
            )
        except Exception as e:
            return FeedbackAgentState(
                question=state.question,
                search_query=state.search_query,
                filter=state.filter,
                error=f"Retrieval failed: {str(e)}",
            )
    
    def _cluster_feedback_node(self, state: FeedbackAgentState) -> FeedbackAgentState:
        """Cluster retrieved feedback into themes."""
        from agents.feedback_agent.clustering import cluster_feedback
        
        if not state.retrieved_chunks:
            return FeedbackAgentState(
                question=state.question,
                search_query=state.search_query,
                filter=state.filter,
                retrieved_chunks=state.retrieved_chunks,
                error="No chunks to cluster",
            )
        
        try:
            clusters = cluster_feedback(state.retrieved_chunks)
            return FeedbackAgentState(
                question=state.question,
                search_query=state.search_query,
                filter=state.filter,
                retrieved_chunks=state.retrieved_chunks,
                clusters=state.clusters,
            )
        except Exception as e:
            return FeedbackAgentState(
                question=state.question,
                search_query=state.search_query,
                filter=state.filter,
                retrieved_chunks=state.retrieved_chunks,
                error=f"Clustering failed: {str(e)}",
            )
    
    def _extract_themes_node(self, state: FeedbackAgentState) -> FeedbackAgentState:
        """Extract structured themes from clusters."""
        themes = []
        
        for cluster in state.clusters:
            themes.append({
                "theme": cluster.theme,
                "sentiment": cluster.sentiment,
                "size": cluster.size,
                "keywords": cluster.keywords,
                "representative_quotes": cluster.representative_quotes[:3],
                "chunk_count": cluster.size,
            })
        
        return FeedbackAgentState(
            question=state.question,
            search_query=state.search_query,
            filter=state.filter,
            retrieved_chunks=state.retrieved_chunks,
            clusters=state.clusters,
            themes=themes,
        )
    
    def _synthesize_evidence_node(self, state: FeedbackAgentState) -> FeedbackAgentState:
        """Synthesize findings into evidence for the investigation."""
        evidence = []
        
        for theme in state.themes:
            # Create evidence entry for each theme
            evidence.append({
                "type": "inference",
                "source": "feedback",
                "content": f"Theme '{theme['theme']}' identified from {theme['size']} feedback items. Sentiment: {theme['sentiment']}. Key quotes: {'; '.join(theme['representative_quotes'][:2])}",
                "confidence": 0.7,
                "citation": f"feedback_theme_{theme['theme']}",
                "metadata": {
                    "theme": theme["theme"],
                    "sentiment": theme["sentiment"],
                    "supporting_count": theme["size"],
                    "keywords": theme["keywords"],
                    "quotes": theme["representative_quotes"],
                },
            })
        
        # Also add individual high-relevance chunks as facts
        for i, chunk in enumerate(state.retrieved_chunks[:5]):
            evidence.append({
                "type": "fact",
                "source": "feedback",
                "content": chunk.content[:500],
                "confidence": chunk.score,
                "citation": f"feedback_chunk_{i}",
                "metadata": chunk.metadata,
            })
        
        return FeedbackAgentState(
            question=state.question,
            search_query=state.search_query,
            filter=state.filter,
            retrieved_chunks=state.retrieved_chunks,
            clusters=state.clusters,
            themes=state.themes,
            evidence=evidence,
            done=True,
        )
    
    def investigate(self, question: str, filter: Optional[Dict] = None) -> Dict[str, Any]:
        """Run feedback investigation."""
        initial_state = FeedbackAgentState(
            question=question,
            search_query="",
            filter=filter or {},
        )
        
        result = self.graph.invoke(initial_state)
        
        return {
            "question": question,
            "themes": result.get("themes", []),
            "clusters": [
                {
                    "theme": c.theme,
                    "sentiment": c.sentiment,
                    "size": c.size,
                    "keywords": c.keywords,
                    "quotes": c.representative_quotes,
                }
                for c in result.get("clusters", [])
            ],
            "evidence": result.get("evidence", []),
            "chunks_retrieved": len(result.get("retrieved_chunks", [])),
            "error": result.get("error"),
        }
    
    def search_feedback(self, query: str, filter: Optional[Dict] = None, k: int = 10) -> List[Dict[str, Any]]:
        """Direct search for feedback."""
        from agents.feedback_agent.rag import get_retriever
        retriever = get_retriever()
        return retriever.retrieve_with_citations(query, filter, k)


def run_feedback_investigation(question: str, filter: Optional[Dict] = None) -> Dict[str, Any]:
    """Run a feedback investigation."""
    agent = FeedbackIntelligenceAgent()
    return agent.investigate(question, filter)


def search_feedback(query: str, filter: Optional[Dict] = None, k: int = 10) -> List[Dict[str, Any]]:
    """Search feedback directly."""
    agent = FeedbackIntelligenceAgent()
    return agent.search_feedback(query, filter, k)