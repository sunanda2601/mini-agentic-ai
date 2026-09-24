from app.rag.knowledge_graph import KnowledgeGraph


def test_payment_service_graph_relationships():
    graph = KnowledgeGraph()

    assert graph.get_dependencies("payment-service") == [
        "payment-db",
        "user-service",
    ]

    assert graph.get_dependents("payment-service") == [
        "checkout-service",
    ]

    assert graph.get_owner("payment-service") == "payments-team"

    assert graph.get_runbooks("payment-service") == [
        "payment-service-high-errors",
    ]