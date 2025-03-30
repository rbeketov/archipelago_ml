import time
import yaml

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


def wait_for_qdrant(host: str, port: int):
    client = QdrantClient(host=host, port=port)
    while True:
        try:
            client.get_collections()
            print("Qdrant is ready!")
            return client
        except Exception as e:
            print("Waiting for Qdrant to start... ", e)
            time.sleep(2)


def load_config(config_path: str):
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    return config


def create_collection(client: QdrantClient, config: dict):
    distance_enum = getattr(Distance, config["distance"].upper(), Distance.COSINE)

    client.create_collection(
        collection_name=config['collection_name'],
        vectors_config=VectorParams(size=config["vector_size"], distance=distance_enum),
    )


if __name__ == "__main__":
    config = load_config("./schema.yml")
    client = wait_for_qdrant(config['host'], config['port'])
#    if client['collection_name'] not in client.get_collections():
    create_collection(client, config)

    #print(f"Collection '{client['collection_name']}' ready")
