"""End-to-end test over real gRPC: a fake catalog, v2, and a client, all in-process."""

import unittest
from concurrent import futures

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

import demo_pb2
import demo_pb2_grpc
from agent import PlaceholderAgent
from catalog import Catalog
from server import RecommendationServiceV2, build_server

PRODUCTS = [
    ("MUG", "Mug", ["kitchen"]),
    ("JAR", "Bamboo Glass Jar", ["kitchen"]),
    ("SALT", "Salt & Pepper Shakers", ["kitchen"]),
    ("WATCH", "Watch", ["accessories"]),
    ("SUN", "Sunglasses", ["accessories"]),
    ("TANK", "Tank Top", ["clothing", "tops"]),
    ("LOAF", "Loafers", ["footwear"]),
]


class FakeCatalog(demo_pb2_grpc.ProductCatalogServiceServicer):
    def __init__(self):
        self.products = [
            demo_pb2.Product(id=i, name=n, categories=c) for i, n, c in PRODUCTS
        ]

    def ListProducts(self, request, context):
        return demo_pb2.ListProductsResponse(products=self.products)

    def GetProduct(self, request, context):
        for product in self.products:
            if product.id == request.id:
                return product
        context.abort(grpc.StatusCode.NOT_FOUND, "no such product")


class V2ServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog_server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        demo_pb2_grpc.add_ProductCatalogServiceServicer_to_server(FakeCatalog(), cls.catalog_server)
        catalog_port = cls.catalog_server.add_insecure_port("localhost:0")
        cls.catalog_server.start()
        cls.catalog_addr = f"localhost:{catalog_port}"
        cls.servers = []

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.stop(0)
        cls.catalog_server.stop(0)

    def start_v2(self, fault_mode="none", timeout=1.0, fallback=True):
        service = RecommendationServiceV2(
            catalog=Catalog(grpc.insecure_channel(self.catalog_addr)),
            agent=PlaceholderAgent(fault_mode=fault_mode, slow_seconds=3),
            timeout_seconds=timeout,
            fallback_enabled=fallback,
        )
        server, port = build_server(service, "0")  # port 0 = any free port
        server.start()
        self.servers.append(server)
        return grpc.insecure_channel(f"localhost:{port}")

    def ask(self, channel, product_ids):
        stub = demo_pb2_grpc.RecommendationServiceStub(channel)
        request = demo_pb2.ListRecommendationsRequest(user_id="u1", product_ids=product_ids)
        return list(stub.ListRecommendations(request, timeout=10).product_ids)

    def test_agent_prefers_same_category(self):
        answer = self.ask(self.start_v2(), ["MUG"])
        self.assertNotIn("MUG", answer)
        self.assertEqual(set(answer[:2]), {"JAR", "SALT"})  # the other kitchen items come first
        self.assertEqual(len(answer), 5)

    def test_invalid_answer_falls_back(self):
        answer = self.ask(self.start_v2(fault_mode="invalid_ids"), ["MUG"])
        self.assertNotIn("NOT_A_PRODUCT", answer)
        self.assertNotIn("MUG", answer)

    def test_slow_agent_falls_back_within_deadline(self):
        answer = self.ask(self.start_v2(fault_mode="slow", timeout=0.5), ["MUG"])
        self.assertEqual(len(answer), 5)

    def test_error_without_fallback_is_a_grpc_error(self):
        channel = self.start_v2(fault_mode="error", fallback=False)
        with self.assertRaises(grpc.RpcError) as caught:
            self.ask(channel, ["MUG"])
        self.assertEqual(caught.exception.code(), grpc.StatusCode.INTERNAL)

    def test_health_check_reports_serving(self):
        stub = health_pb2_grpc.HealthStub(self.start_v2())
        reply = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=5)
        self.assertEqual(reply.status, health_pb2.HealthCheckResponse.SERVING)


if __name__ == "__main__":
    unittest.main()
