from sentence_transformers import SentenceTransformer
import numpy as np

from app.rag.documents import load_documents


class SemanticSearcher:
    def __init__(self):
        self.documents = load_documents()

        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        self.embeddings = self.model.encode(
            [document["text"] for document in self.documents],
            normalize_embeddings=True,
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
        metadata_filter: dict | None = None,
    ) -> list[dict]:

        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]

        scores = np.dot(
            self.embeddings,
            query_embedding,
        )

        ranked_indices = np.argsort(scores)[::-1]

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