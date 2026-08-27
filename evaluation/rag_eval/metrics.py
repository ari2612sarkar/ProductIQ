"""
RAG Evaluation Metrics
"""
from typing import List, Dict, Any, Set
from dataclasses import dataclass
from collections import Counter
import math


@dataclass
class RAGEvalResult:
    query: str
    retrieved_docs: List[str]
    relevant_docs: List[str]
    generated_answer: str
    reference_answer: str

    # Computed metrics
    retrieval_precision: float = 0.0
    retrieval_recall: float = 0.0
    retrieval_f1: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    faithfulness: float = 0.0
    answer_relevance: float = 0.0


def evaluate_rag(
    query: str,
    retrieved_docs: List[str],
    relevant_docs: List[str],
    generated_answer: str,
    reference_answer: str,
) -> RAGEvalResult:
    """Evaluate a single RAG query."""

    result = RAGEvalResult(
        query=query,
        retrieved_docs=retrieved_docs,
        relevant_docs=relevant_docs,
        generated_answer=generated_answer,
        reference_answer=reference_answer,
    )

    # Retrieval metrics
    retrieved_set = set(retrieved_docs)
    relevant_set = set(relevant_docs)

    if retrieved_set:
        result.retrieval_precision = len(retrieved_set & relevant_set) / len(retrieved_set)
    else:
        result.retrieval_precision = 0.0

    if relevant_set:
        result.retrieval_recall = len(retrieved_set & relevant_set) / len(relevant_set)
    else:
        result.retrieval_recall = 1.0 if not retrieved_set else 0.0

    if result.retrieval_precision + result.retrieval_recall > 0:
        result.retrieval_f1 = (
            2 * result.retrieval_precision * result.retrieval_recall
            / (result.retrieval_precision + result.retrieval_recall)
        )

    # Context precision (precision at each relevant position)
    result.context_precision = _compute_context_precision(retrieved_docs, relevant_docs)

    # Context recall
    result.context_recall = _compute_context_recall(retrieved_docs, relevant_docs)

    # Faithfulness (answer supported by context)
    result.faithfulness = _compute_faithfulness(generated_answer, retrieved_docs)

    # Answer relevance (simple keyword overlap with reference)
    result.answer_relevance = _compute_answer_relevance(generated_answer, reference_answer)

    return result


def _compute_context_precision(retrieved: List[str], relevant: List[str]) -> float:
    """Compute precision at each relevant document position."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0

    precision_sum = 0.0
    relevant_found = 0

    for i, doc in enumerate(retrieved, 1):
        if doc in relevant_set:
            relevant_found += 1
            precision_sum += relevant_found / i

    if relevant_found == 0:
        return 0.0

    return precision_sum / len(relevant_set)


def _compute_context_recall(retrieved: List[str], relevant: List[str]) -> float:
    """Compute fraction of relevant docs retrieved."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0

    retrieved_set = set(retrieved)
    return len(retrieved_set & relevant_set) / len(relevant_set)


def _compute_faithfulness(answer: str, context: List[str]) -> float:
    """
    Simple faithfulness check: answer tokens should appear in context.
    Returns fraction of answer tokens found in context.
    """
    if not answer.strip():
        return 0.0

    # Simple tokenization
    answer_tokens = set(answer.lower().split())
    context_text = " ".join(context).lower()
    context_tokens = set(context_text.split())

    if not answer_tokens:
        return 1.0

    found = sum(1 for token in answer_tokens if token in context_tokens)
    return found / len(answer_tokens)


def _compute_answer_relevance(answer: str, reference: str) -> float:
    """Compute relevance using token overlap (Jaccard similarity)."""
    if not answer.strip() or not reference.strip():
        return 0.0

    answer_tokens = set(answer.lower().split())
    reference_tokens = set(reference.lower().split())

    intersection = answer_tokens & reference_tokens
    union = answer_tokens | reference_tokens

    if not union:
        return 1.0

    return len(intersection) / len(union)


def compute_rag_metrics(results: List[RAGEvalResult]) -> Dict[str, float]:
    """Compute aggregate RAG metrics."""
    total = len(results)
    if total == 0:
        return {}

    return {
        "retrieval_precision": sum(r.retrieval_precision for r in results) / total,
        "retrieval_recall": sum(r.retrieval_recall for r in results) / total,
        "retrieval_f1": sum(r.retrieval_f1 for r in results) / total,
        "context_precision": sum(r.context_precision for r in results) / total,
        "context_recall": sum(r.context_recall for r in results) / total,
        "faithfulness": sum(r.faithfulness for r in results) / total,
        "answer_relevance": sum(r.answer_relevance for r in results) / total,
    }