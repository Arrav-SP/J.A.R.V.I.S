"""Semantic vector memory and retrieval engine for JARVIS.

Provides local-first semantic retrieval using TF-IDF / subword n-gram vectorization
with cosine similarity, with an optional transparent upgrade to local sentence embeddings
when sentence-transformers is available in the environment.

Zero paid cloud calls. Zero remote data leaks. Completely local-first.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.logger import get_logger
from app.memory.schemas import MemoryRecord, MemorySearchResult

logger = get_logger("memory.semantic")


class LocalEmbeddingProvider:
    """Computes text vectors locally.

    Uses `sentence-transformers` if available and loaded; otherwise falls back to a fast,
    deterministic local character-n-gram TF-IDF vectorizer that requires zero downloads
    and zero network access.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", allow_neural: bool = False) -> None:
        self.allow_neural = allow_neural
        self.model_name = model_name
        self._model = None
        self._dim = 384

        if self.allow_neural:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Initializing local SentenceTransformer model '%s'...", model_name)
                self._model = SentenceTransformer(model_name)
                self._dim = self._model.get_sentence_embedding_dimension()
                logger.info("Loaded neural embedding provider (dim=%d)", self._dim)
            except Exception as err:
                logger.warning("Neural embedding load skipped (%s). Using deterministic local vectorizer.", err)
                self._model = None

    def embed_text(self, text: str) -> np.ndarray:
        """Generate a normalized 1D embedding array for the input string."""
        clean = text.strip()
        if not clean:
            return np.zeros(self._dim, dtype=np.float32)

        if self._model is not None:
            try:
                emb = self._model.encode(clean, convert_to_numpy=True, normalize_embeddings=True)
                return emb.astype(np.float32)
            except Exception as err:
                logger.error("Neural embedding failed: %s; falling back to local vectorizer", err)

        return self._local_hash_vectorize(clean, dim=self._dim)

    def _local_hash_vectorize(self, text: str, dim: int = 384) -> np.ndarray:
        """Deterministic subword / character-trigram hashed vector with TF weighting and L2 normalization."""
        vec = np.zeros(dim, dtype=np.float32)
        tokens = re.findall(r"\b\w+\b", text.lower())
        if not tokens:
            return vec

        # Term frequency + subword trigrams
        for token in tokens:
            # Word hash
            h_word = abs(hash(token)) % dim
            vec[h_word] += 2.0

            # Character 3-grams for typo / morphological tolerance (e.g. project vs projects, optgraph vs opt graph)
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    trigram = token[i : i + 3]
                    h_tri = abs(hash(trigram)) % dim
                    vec[h_tri] += 1.0

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        return vec


class SemanticMemoryStore:
    """Manages an in-memory vector index mapped to persistent memory records."""

    def __init__(self, embedding_provider: Optional[LocalEmbeddingProvider] = None) -> None:
        self.provider = embedding_provider or LocalEmbeddingProvider(allow_neural=False)
        self._vectors: Dict[str, np.ndarray] = {}  # memory_id -> normalized vector
        self._records: Dict[str, MemoryRecord] = {}  # memory_id -> MemoryRecord

    def index_record(self, record: MemoryRecord) -> None:
        """Compute and store embedding vector for a memory record."""
        # Include tags and project in the semantic footprint for enriched matching
        context_repr = record.content
        if record.project:
            context_repr += f" (project: {record.project})"
        if record.tags:
            context_repr += f" (tags: {', '.join(record.tags)})"

        vec = self.provider.embed_text(context_repr)
        self._vectors[record.id] = vec
        self._records[record.id] = record

    def remove_record(self, memory_id: str) -> None:
        """Remove record vector from index."""
        self._vectors.pop(memory_id, None)
        self._records.pop(memory_id, None)

    def clear(self) -> None:
        """Clear all indexed memory vectors."""
        self._vectors.clear()
        self._records.clear()

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.25,
        project: Optional[str] = None,
    ) -> List[MemorySearchResult]:
        """Search indexed memories by cosine similarity against the query."""
        clean_query = query.strip()
        if not clean_query or not self._vectors:
            return []

        q_vec = self.provider.embed_text(clean_query)
        q_norm = np.linalg.norm(q_vec)
        if q_norm < 1e-9:
            return []

        scored_results: List[Tuple[float, MemoryRecord]] = []

        for mem_id, m_vec in self._vectors.items():
            record = self._records.get(mem_id)
            if not record:
                continue

            # Project scope filter: if query specifies a project, restrict to that project or global
            if project is not None and record.project is not None and record.project.lower() != project.lower():
                continue

            # Cosine similarity between pre-normalized vectors is dot product
            similarity = float(np.dot(q_vec, m_vec))
            # Clamp to [0.0, 1.0]
            similarity = max(0.0, min(1.0, similarity))

            if similarity >= threshold:
                # Modulate relevance score slightly with importance
                importance_boost = record.importance.score * 0.15
                ranked_score = min(1.0, similarity + importance_boost)
                scored_results.append((ranked_score, record))

        # Sort descending by ranked relevance score
        scored_results.sort(key=lambda x: x[0], reverse=True)

        return [
            MemorySearchResult(
                record=rec,
                relevance_score=round(score, 4),
                match_source="semantic",
            )
            for score, rec in scored_results[:top_k]
        ]
