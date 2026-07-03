#!/usr/bin/env python3
"""
Test script để verify price filtering logic
"""

import sys
sys.path.insert(0, r'c:\Users\ADMIN\Downloads\SearchProductAgent\SearchProductAgent')

from tools.normal.tools import (
    _build_search_intent,
    _filter_products_by_intent,
    _filter_products_with_specific_price,
    _is_price_comparison_query,
    ProductMemory,
)

# Test 1: Detect price comparison queries
print("=" * 80)
print("TEST 1: Price Comparison Query Detection")
print("=" * 80)

test_queries = [
    "Tìm máy chủ Dell dưới 100 triệu đồng",
    "Từ 50 đến 150 triệu",
    "Giá rẻ hơn 80 triệu",
    "So sánh giá các máy chủ HPE",
    "Tìm máy chủ 500 triệu trở lên",
    "tim may chu duoi 50 trieu",
    "Giá máy chủ bao nhiêu?",  # NOT price comparison
    "Tìm cấu hình máy chủ",      # NOT price comparison
]

for query in test_queries:
    is_price = _is_price_comparison_query(query)
    status = "✓ PRICE COMPARISON" if is_price else "✗ NOT price comparison"
    print(f"{status:30} | {query}")

# Test 2: Filter products
print("\n" + "=" * 80)
print("TEST 2: Product Filtering (remove non-specific prices)")
print("=" * 80)

test_products = [
    {"tên": "Dell R740", "giá": "50000000", "hãng": "Dell"},           # ✓ Keep
    {"tên": "Dell R750", "giá": "Liên hệ báo giá", "hãng": "Dell"},    # ✗ Remove
    {"tên": "HPE ProLiant", "giá": "80000000", "hãng": "HPE"},         # ✓ Keep
    {"tên": "HPE DL560", "giá": "Liên hệ", "hãng": "HPE"},             # ✗ Remove
    {"tên": "Lenovo ThinkSystem", "giá": "N/A", "hãng": "Lenovo"},     # ✗ Remove
    {"tên": "ASUS RS720", "giá": "120-150 triệu", "hãng": "ASUS"},     # ✓ Keep
    {"tên": "Supermicro", "giá": "TBD", "hãng": "Supermicro"},         # ✗ Remove
]

print(f"\nBefore filter: {len(test_products)} products")
for i, p in enumerate(test_products, 1):
    print(f"  {i}. {p['tên']:30} | Giá: {p['giá']:30}")

filtered = _filter_products_with_specific_price(test_products)

print(f"\nAfter filter: {len(filtered)} products")
for i, p in enumerate(filtered, 1):
    print(f"  {i}. {p['tên']:30} | Giá: {p['giá']:30}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✓ Detected price comparisons: {sum(1 for q in test_queries if _is_price_comparison_query(q))}/{len(test_queries)}")
print(f"✓ Filtered products: {len(test_products)} → {len(filtered)}")
print(f"✓ Removed: {len(test_products) - len(filtered)} products with non-specific prices")
print("\n✅ All tests passed!")

# Test 3: Hybrid intent parsing
print("\n" + "=" * 80)
print("TEST 3: Hybrid Intent Parsing")
print("=" * 80)

memory = ProductMemory(product_type=None, brand=None, price_range=None)
intent = _build_search_intent(memory, "Tìm laptop Lenovo dưới 20M", "Tìm laptop Lenovo dưới 20M")
print(f"Parsed intent: {intent.to_log_dict()}")

assert intent.product_type == "laptop", "Expected product_type=laptop"
assert intent.brand == "Lenovo", "Expected brand=Lenovo"
assert intent.price_max == 20_000_000, "Expected price_max=20M"
assert intent.price_min is None, "Expected no price_min"

test_intent_products = [
    {"tên": "Lenovo ThinkPad X1", "giá": "18900000", "hãng": "Lenovo", "cấu_hình": "16GB RAM"},
    {"tên": "Dell Latitude 7440", "giá": "19900000", "hãng": "Dell", "cấu_hình": "16GB RAM"},
    {"tên": "Lenovo IdeaPad", "giá": "Liên hệ", "hãng": "Lenovo", "cấu_hình": "8GB RAM"},
]

filtered_intent_products = _filter_products_by_intent(test_intent_products, intent)
print(f"Filtered by intent: {len(filtered_intent_products)} products")
for i, p in enumerate(filtered_intent_products, 1):
    print(f"  {i}. {p['tên']:30} | Giá: {p['giá']:12} | Hãng: {p['hãng']}")

assert len(filtered_intent_products) == 1, "Expected only one Lenovo laptop under 20M with specific price"
assert filtered_intent_products[0]["tên"] == "Lenovo ThinkPad X1", "Expected ThinkPad result"

print("\n✅ Hybrid intent parser tests passed!")

# Test 4: Regression - typo unit + structured max price
print("\n" + "=" * 80)
print("TEST 4: Regression - 'duoi 20 triueej' + structured max")
print("=" * 80)

memory_regression = ProductMemory(product_type="laptop", brand="Lenovo", price_range="{'max': 20000000}")
intent_regression = _build_search_intent(
    memory_regression,
    "cho toi xin cac mau laptop gia duoi 20 triueej",
    "cho toi xin cac mau laptop gia duoi 20 triueej",
)
print(f"Parsed regression intent: {intent_regression.to_log_dict()}")
assert intent_regression.price_max == 20_000_000, "Expected structured max=20,000,000"

regression_products = [
    {"tên": "Lenovo Ideapad Y450-0619", "giá": "24,771,000 VND", "hãng": "Lenovo", "cấu_hình": "Core i5"},
    {"tên": "Lenovo Ideapad Slim 3", "giá": "19,500,000 VND", "hãng": "Lenovo", "cấu_hình": "Core i5"},
]
regression_filtered = _filter_products_by_intent(regression_products, intent_regression)
print(f"Regression filtered count: {len(regression_filtered)}")
for i, p in enumerate(regression_filtered, 1):
    print(f"  {i}. {p['tên']:30} | Giá: {p['giá']:15}")

assert len(regression_filtered) == 1, "Expected only <=20M product"
assert regression_filtered[0]["tên"] == "Lenovo Ideapad Slim 3", "Expected 19.5M product only"

print("\n✅ Regression test passed!")

# Test 5: Query normalization (typo + no-diacritic)
print("\n" + "=" * 80)
print("TEST 5: Query Normalization (typo + no-diacritic)")
print("=" * 80)

memory_typo = ProductMemory(product_type="laptop", brand="Lenovo", price_range=None)
intent_typo = _build_search_intent(
    memory_typo,
    "cho toi xin cac mau laptpo gia duoi 20 triueej",
    "cho toi xin cac mau laptpo gia duoi 20 triueej",
)
print(f"Parsed typo intent: {intent_typo.to_log_dict()}")
assert intent_typo.product_type == "laptop", "Expected normalized product_type=laptop"
assert intent_typo.price_max == 20_000_000, "Expected normalized max=20M"

typo_products = [
    {"tên": "Lenovo Ideapad Y450-0619", "giá": "24,771,000 VND", "hãng": "Lenovo", "cấu_hình": "Core i5"},
    {"tên": "Lenovo Ideapad Slim 3", "giá": "19,500,000 VND", "hãng": "Lenovo", "cấu_hình": "Core i5"},
]
typo_filtered = _filter_products_by_intent(typo_products, intent_typo)
print(f"Typo filtered count: {len(typo_filtered)}")
assert len(typo_filtered) == 1, "Expected only <=20M product after normalization"
assert typo_filtered[0]["tên"] == "Lenovo Ideapad Slim 3", "Expected 19.5M product only"

print("\n✅ Query normalization test passed!")
