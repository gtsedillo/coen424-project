"""Call a recommendation service and show the answer with product names.

Works against v1 or v2, so the two can be compared side by side. It looks up
every returned ID in the product catalog, which also shows at a glance whether
an answer is valid.

Examples (run inside the v2 container, which already knows the catalog address):
  python demo_client.py --list
  python demo_client.py --target recommendation-v1:8080 6E92ZMYYFZ
  python demo_client.py --target localhost:8080 6E92ZMYYFZ 9SIQT8TOJO
"""

import argparse
import os
import sys

import grpc

import demo_pb2
import demo_pb2_grpc
from catalog import Catalog
from validator import validate


def describe(product):
    return f"{product.id}  {product.name:<24} {', '.join(product.categories)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("product_ids", nargs="*", help="IDs to send, e.g. cart contents")
    parser.add_argument("--target", default="localhost:8080",
                        help="recommendation service address (default: localhost:8080)")
    parser.add_argument("--user", default="demo-user", help="user_id to send")
    parser.add_argument("--catalog",
                        default=os.environ.get("PRODUCT_CATALOG_SERVICE_ADDR", "localhost:3550"),
                        help="product catalog address")
    parser.add_argument("--list", action="store_true", help="only print the whole catalog")
    args = parser.parse_args()

    catalog = Catalog(grpc.insecure_channel(args.catalog))
    products = {p.id: p for p in catalog.list_products()}

    if args.list:
        print(f"Catalog ({len(products)} products):")
        for product in sorted(products.values(), key=lambda p: p.name):
            print("  " + describe(product))
        return 0

    print(f"Request to {args.target}  (user_id={args.user})")
    for pid in args.product_ids:
        print("  in:  " + (describe(products[pid]) if pid in products else f"{pid}  (not in catalog)"))

    stub = demo_pb2_grpc.RecommendationServiceStub(grpc.insecure_channel(args.target))
    response = stub.ListRecommendations(
        demo_pb2.ListRecommendationsRequest(user_id=args.user, product_ids=args.product_ids),
        timeout=30,
    )

    print("Recommendations:")
    for pid in response.product_ids:
        print("  out: " + (describe(products[pid]) if pid in products else f"{pid}  UNKNOWN ID"))

    check = validate(response.product_ids, args.product_ids, products.keys())
    print("Valid: yes" if check.valid else "Valid: NO  " + "; ".join(check.problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
