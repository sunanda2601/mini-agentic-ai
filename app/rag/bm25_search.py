from rank_bm25 import BM25Okapi

from app.rag.documents import load_documents


class BM25Searcher:
    def __init__(self):
        self.documents = load_documents()

        self.tokenized_documents = [
            document["text"].lower().split()
            for document in self.documents
        ]

        self.bm25 = BM25Okapi(self.tokenized_documents)

    def search(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[dict]:
        query_tokens = query.lower().split()

        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indices:
            document = self.documents[index]

            if metadata_filter:
                matches = all(
                    document["metadata"].get(key) == value
                    for key, value in metadata_filter.items()
                )

                if not matches:
                    continue

            result = document.copy()
            result["score"] = float(scores[index])
            results.append(result)

            if len(results) >= top_k:
                break

        return results