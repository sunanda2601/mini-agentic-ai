from app.rag.bm25_search import BM25Searcher
from app.rag.semantic_search import SemanticSearcher


class HybridSearcher:
    def __init__(self):
        self.bm25 = BM25Searcher()
        self.semantic = SemanticSearcher()

    def search(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[dict]:

        bm25_results = self.bm25.search(
            query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

        semantic_results = self.semantic.search(
            query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

        combined = {}

        for result in bm25_results:
            combined[result["id"]] = {
                **result,
                "bm25_score": result["score"],
                "semantic_score": 0.0,
            }

        for result in semantic_results:
            if result["id"] not in combined:
                combined[result["id"]] = {
                    **result,
                    "bm25_score": 0.0,
                    "semantic_score": result["score"],
                }
            else:
                combined[result["id"]]["semantic_score"] = result["score"]

        results = list(combined.values())

        if results:
            bm25_scores = [r["bm25_score"] for r in results]
            semantic_scores = [r["semantic_score"] for r in results]

            bm25_min = min(bm25_scores)
            bm25_max = max(bm25_scores)

            semantic_min = min(semantic_scores)
            semantic_max = max(semantic_scores)

            for result in results:
                if bm25_max != bm25_min:
                    bm25_normalized = (
                        (result["bm25_score"] - bm25_min)
                        / (bm25_max - bm25_min)
                    )
                else:
                    bm25_normalized = 1.0

                if semantic_max != semantic_min:
                    semantic_normalized = (
                        (result["semantic_score"] - semantic_min)
                        / (semantic_max - semantic_min)
                    )
                else:
                    semantic_normalized = 1.0

                result["hybrid_score"] = (
                    0.5 * bm25_normalized
                    + 0.5 * semantic_normalized
                )

                result["citation"] = f"runbook:{result['id']}"

            results = sorted(
                results,
                key=lambda x: x["hybrid_score"],
                reverse=True,
            )

        return results[:top_k]
