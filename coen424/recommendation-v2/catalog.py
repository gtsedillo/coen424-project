"""Thin wrapper around the ProductCatalogService gRPC client.

The agent's tools and the validator both go through this class, so every call
to the catalog has a timeout and is easy to replace with a fake in tests.
"""

import demo_pb2
import demo_pb2_grpc


class Catalog:
    def __init__(self, channel, timeout_seconds=2.0):
        self._stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
        self._timeout = timeout_seconds

    def list_products(self):
        response = self._stub.ListProducts(demo_pb2.Empty(), timeout=self._timeout)
        return list(response.products)

    def get_product(self, product_id):
        return self._stub.GetProduct(
            demo_pb2.GetProductRequest(id=product_id), timeout=self._timeout
        )
