"""
Feedback Clustering for theme identification.
Groups related feedback using semantic clustering.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config.settings import settings
from agents.feedback_agent.rag import RetrievedChunk


@dataclass
class FeedbackCluster:
    """A cluster of related feedback."""
    id: str
    theme: str
    chunks: List[Any]
    representative_quotes: List[str]
    sentiment: str
    size: int
    keywords: List[str]


class FeedbackClusterer:
    """Clusters feedback chunks by semantic similarity."""
    
    def __init__(self):
        self.min_cluster_size = 3
        self.max_clusters = 20
        self.similarity_threshold = 0.7
    
    def cluster_chunks(self, chunks: List[RetrievedChunk], method: str = "kmeans") -> List[FeedbackCluster]:
        """Cluster chunks into themes."""
        if len(chunks) < self.min_cluster_size:
            return [self._create_single_cluster(chunks)]
        
        # Extract texts
        texts = [chunk.content for chunk in chunks]
        
        # Create embeddings using TF-IDF (fast, no external API)
        vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8,
        )
        
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
        except ValueError:
            return [self._create_single_cluster(chunks)]
        
        # Determine optimal number of clusters
        n_clusters = min(self.max_clusters, max(2, len(chunks) // 5))
        
        if method == "kmeans":
            clusters = self._kmeans_cluster(tfidf_matrix, n_clusters, chunks, vectorizer)
        elif method == "dbscan":
            clusters = self._dbscan_cluster(tfidf_matrix, chunks)
        else:
            clusters = self._kmeans_cluster(tfidf_matrix, n_clusters, chunks, vectorizer)
        
        # Filter small clusters
        clusters = [c for c in clusters if c.size >= self.min_cluster_size]
        
        # If all filtered out, return single cluster
        if not clusters:
            return [self._create_single_cluster(chunks)]
        
        return clusters
    
    def _kmeans_cluster(self, tfidf_matrix, n_clusters: int, chunks: List[RetrievedChunk], vectorizer) -> List[FeedbackCluster]:
        """Cluster using KMeans."""
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(tfidf_matrix)
        
        # Group chunks by cluster
        cluster_chunks = defaultdict(list)
        for i, label in enumerate(labels):
            cluster_chunks[label].append(chunks[i])
        
        clusters = []
        feature_names = vectorizer.get_feature_names_out()
        
        for label, cluster_chunk_list in cluster_chunks.items():
            if len(cluster_chunk_list) < self.min_cluster_size:
                continue
            
            # Get cluster center keywords
            center = kmeans.cluster_centers_[label]
            top_indices = center.argsort()[-10:][::-1]
            keywords = [feature_names[i] for i in top_indices if center[i] > 0]
            
            # Generate theme name
            theme = self._generate_theme(keywords, cluster_chunk_list)
            
            # Get representative quotes
            quotes = self._get_representative_quotes(cluster_chunk_list, kmeans.cluster_centers_[label], tfidf_matrix, labels, label)
            
            # Determine sentiment
            sentiment = self._determine_sentiment(cluster_chunk_list)
            
            clusters.append(FeedbackCluster(
                id=f"cluster_{label}",
                theme=theme,
                chunks=cluster_chunk_list,
                representative_quotes=quotes,
                sentiment=sentiment,
                size=len(cluster_chunk_list),
                keywords=keywords[:5],
            ))
        
        return clusters
    
    def _dbscan_cluster(self, tfidf_matrix, chunks: List[RetrievedChunk]) -> List[FeedbackCluster]:
        """Cluster using DBSCAN."""
        # Convert to dense for cosine similarity
        dense_matrix = tfidf_matrix.toarray()
        
        # Use cosine distance
        from sklearn.metrics.pairwise import cosine_distances
        distance_matrix = cosine_distances(dense_matrix)
        
        dbscan = DBSCAN(
            eps=0.5,
            min_samples=self.min_cluster_size,
            metric="precomputed",
        )
        labels = dbscan.fit_predict(distance_matrix)
        
        cluster_chunks = defaultdict(list)
        for i, label in enumerate(labels):
            if label != -1:  # -1 is noise
                cluster_chunks[label].append(chunks[i])
        
        clusters = []
        for label, cluster_chunk_list in cluster_chunks.items():
            if len(cluster_chunk_list) < self.min_cluster_size:
                continue
            
            # Use TF-IDF for keywords
            texts = [c.content for c in cluster_chunk_list]
            vectorizer = TfidfVectorizer(max_features=500, stop_words='english', ngram_range=(1, 2))
            try:
                tfidf = vectorizer.fit_transform(texts)
                feature_names = vectorizer.get_feature_names_out()
                # Mean TF-IDF for cluster
                mean_tfidf = tfidf.mean(axis=0).A1
                top_indices = mean_tfidf.argsort()[-10:][::-1]
                keywords = [feature_names[i] for i in top_indices]
            except ValueError:
                keywords = []
            
            theme = self._generate_theme(keywords, cluster_chunk_list)
            quotes = cluster_chunk_list[:3]  # Simple representative
            sentiment = self._determine_sentiment(cluster_chunk_list)
            
            clusters.append(FeedbackCluster(
                id=f"cluster_{label}",
                theme=theme,
                chunks=cluster_chunk_list,
                representative_quotes=[c.content[:200] for c in quotes],
                sentiment=sentiment,
                size=len(cluster_chunk_list),
                keywords=keywords[:5],
            ))
        
        return clusters
    
    def _create_single_cluster(self, chunks: List[RetrievedChunk]) -> FeedbackCluster:
        """Create a single cluster from all chunks."""
        texts = [c.content for c in chunks]
        vectorizer = TfidfVectorizer(max_features=500, stop_words='english', ngram_range=(1, 2))
        try:
            tfidf = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()
            mean_tfidf = tfidf.mean(axis=0).A1
            top_indices = mean_tfidf.argsort()[-10:][::-1]
            keywords = [feature_names[i] for i in top_indices if mean_tfidf[i] > 0]
        except ValueError:
            keywords = []
        
        theme = self._generate_theme(keywords, chunks)
        quotes = chunks[:3]
        sentiment = self._determine_sentiment(chunks)
        
        return FeedbackCluster(
            id="cluster_all",
            theme=theme,
            chunks=chunks,
            representative_quotes=[c.content[:200] for c in quotes],
            sentiment=sentiment,
            size=len(chunks),
            keywords=keywords[:5],
        )
    
    def _generate_theme(self, keywords: List[str], chunks: List[RetrievedChunk]) -> str:
        """Generate a human-readable theme name."""
        if not keywords:
            return "General Feedback"
        
        # Map keywords to theme categories
        theme_mapping = {
            "bug": "Bug Reports",
            "crash": "App Crashes",
            "slow": "Performance Issues",
            "login": "Authentication Issues",
            "payment": "Payment Problems",
            "billing": "Billing Issues",
            "feature": "Feature Requests",
            "ui": "UI/UX Feedback",
            "mobile": "Mobile App",
            "search": "Search Issues",
            "notification": "Notifications",
            "sync": "Sync Problems",
            "export": "Export Issues",
            "import": "Import Problems",
            "onboard": "Onboarding",
            "tutorial": "Tutorial/Help",
            "price": "Pricing Feedback",
            "subscription": "Subscription Issues",
            "cancel": "Cancellation Feedback",
        }
        
        for keyword in keywords[:5]:
            for key, theme in theme_mapping.items():
                if key in keyword.lower():
                    return theme
        
        # Default: use top keywords
        return f"Feedback: {', '.join(keywords[:3])}"
    
    def _get_representative_quotes(self, chunks: List[RetrievedChunk], center, tfidf_matrix, labels, label) -> List[str]:
        """Get representative quotes from cluster."""
        # Find chunks closest to center
        cluster_indices = [i for i, l in enumerate(labels) if l == label]
        if not cluster_indices:
            return [c.content[:200] for c in chunks[:3]]
        
        # Get similarity to center
        from sklearn.metrics.pairwise import cosine_similarity
        center_vec = center.reshape(1, -1)
        cluster_matrix = tfidf_matrix[cluster_indices]
        similarities = cosine_similarity(center_vec, cluster_matrix)[0]
        
        # Sort by similarity
        sorted_indices = np.argsort(similarities)[::-1]
        top_chunks = [chunks[cluster_indices[i]] for i in sorted_indices[:3]]
        
        return [c.content[:300] for c in top_chunks]
    
    def _determine_sentiment(self, chunks: List[RetrievedChunk]) -> str:
        """Determine overall sentiment of cluster."""
        sentiments = [c.metadata.get("sentiment", "neutral") for c in chunks]
        sentiment_counts = defaultdict(int)
        for s in sentiments:
            sentiment_counts[s] += 1
        
        if not sentiment_counts:
            return "neutral"
        
        return max(sentiment_counts, key=sentiment_counts.get)


def cluster_feedback(chunks: List[RetrievedChunk], method: str = "kmeans") -> List[FeedbackCluster]:
    """Convenience function to cluster feedback."""
    clusterer = FeedbackClusterer()
    return clusterer.cluster_chunks(chunks, method)