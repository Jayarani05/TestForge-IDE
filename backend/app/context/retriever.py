import re

from app.context.models import (
    ContextChunk,
    ContextQuery,
    ContextResponse,
    ContextResult,
)


class ContextRetriever:
    """Retrieve repository context using lexical relevance scoring."""

    INTENT_EXPANSIONS = {
        "repository": {
            "repository",
            "repo",
            "project",
            "source",
            "tree",
            "files",
            "directories",
        },
        "analyze": {
            "analyze",
            "analysis",
            "analyzer",
            "analyse",
            "inspect",
            "inspection",
            "detect",
            "detection",
        },
        "test": {
            "test",
            "tests",
            "testing",
            "pytest",
            "playwright",
            "selenium",
        },
        "failure": {
            "failure",
            "failed",
            "error",
            "exception",
            "root",
            "cause",
            "rca",
        },
        "generate": {
            "generate",
            "generation",
            "create",
            "creation",
            "produce",
        },
        "context": {
            "context",
            "chunk",
            "chunks",
            "retrieve",
            "retrieval",
            "embedding",
            "vector",
        },
    }

    IMPLEMENTATION_PATHS = {
        "analyzer",
        "analyzer_service",
        "repository",
        "tree_service",
        "context",
        "retriever",
        "agent",
        "execution",
        "analytics",
        "service",
    }

    def retrieve(
        self,
        chunks: list[ContextChunk],
        query: ContextQuery,
    ) -> ContextResponse:
        query_terms = self._expand_query(
            self._tokenize(query.query)
        )

        if not query_terms:
            return ContextResponse(
                query=query.query,
                repository_path=query.repository_path,
                results=[],
                total_results=0,
            )

        candidates: list[ContextResult] = []

        for chunk in chunks:
            if chunk.repository_path != query.repository_path:
                continue

            if query.source_types:
                if chunk.source_type not in query.source_types:
                    continue

            if query.languages:
                if chunk.language not in query.languages:
                    continue

            score = self._score_chunk(
                chunk=chunk,
                query=query.query,
                query_terms=query_terms,
            )

            if score <= 0:
                continue

            candidates.append(
                ContextResult(
                    chunk=chunk,
                    score=min(score, 1.0),
                )
            )

        candidates.sort(
            key=lambda result: (
                result.score,
                result.chunk.relative_path,
                result.chunk.start_line or 0,
            ),
            reverse=True,
        )

        results = candidates[: query.top_k]

        return ContextResponse(
            query=query.query,
            repository_path=query.repository_path,
            results=results,
            total_results=len(candidates),
        )

    def _score_chunk(
        self,
        chunk: ContextChunk,
        query: str,
        query_terms: set[str],
    ) -> float:
        content = chunk.content.lower()
        path_text = chunk.relative_path.lower()

        content_terms = self._tokenize(content)

        if not content_terms:
            return 0.0

        matched_terms = query_terms.intersection(
            content_terms
        )

        if not matched_terms:
            return 0.0

        coverage = len(matched_terms) / len(query_terms)

        score = coverage * 0.45

        normalized_query = " ".join(
            self._tokenize(query)
        )

        normalized_content = " ".join(
            self._tokenize(content)
        )

        if normalized_query in normalized_content:
            score += 0.20

        path_terms = self._tokenize(path_text)

        path_matches = len(
            query_terms.intersection(path_terms)
        )

        score += min(
            path_matches * 0.04,
            0.16,
        )

        implementation_matches = len(
            self.IMPLEMENTATION_PATHS.intersection(
                path_terms
            )
        )

        score += min(
            implementation_matches * 0.08,
            0.32,
        )

        if (
            "repository" in query_terms
            and (
                "analyzer" in path_text
                or "analysis" in path_text
            )
        ):
            score += 0.20

        if (
            "analyze" in query_terms
            and "analyzer" in path_text
        ):
            score += 0.20

        return min(score, 1.0)

    def _expand_query(
        self,
        query_terms: set[str],
    ) -> set[str]:
        expanded = set(query_terms)

        for intent, related_terms in self.INTENT_EXPANSIONS.items():
            if intent in query_terms:
                expanded.update(related_terms)

        return expanded

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = re.findall(
            r"[A-Za-z0-9_]+",
            text.lower(),
        )

        return {
            token
            for token in tokens
            if len(token) >= 2
        }
