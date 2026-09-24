from app.tools.dependencies import get_dependency_graph
from app.tools.schemas import GetDependencyGraphRequest


def main():
    request = GetDependencyGraphRequest(
    service="payment-service",
    environment="staging",
)
    response = get_dependency_graph(request)

    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()