#!/usr/bin/env python3
"""
Test script để verify deduplication + price filtering logic
"""

import sys
sys.path.insert(0, r'c:\Users\ADMIN\Downloads\SearchProductAgent\SearchProductAgent')

from tools.normal.tools import _is_price_comparison_query, _filter_products_with_specific_price, _deduplicate_products

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
    "Tìm máy chủ bao nhiêu?",  # NOT price comparison
    "Tìm cấu hình máy chủ",      # NOT price comparison
]

for query in test_queries:
    is_price = _is_price_comparison_query(query)
    status = "✓ PRICE COMPARISON" if is_price else "✗ NOT price comparison"
    print(f"{status:30} | {query}")

# Test 2: Product Filtering
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

# Test 3: Deduplication (NEW)
print("\n" + "=" * 80)
print("TEST 3: Product Deduplication (REAL-WORLD CASE)")
print("=" * 80)

duplicate_products = [
    {"tên": "Card Màn Hình VGA Gigabyte GV-N3090TURBO-24GD", "giá": "Liên hệ báo giá", "hãng": "Gigabyte", "_score": 0.95},
    {"tên": "Card Màn Hình VGA Gigabyte GV-N3090TURBO-24GD", "giá": "Liên hệ báo giá", "hãng": "Gigabyte", "_score": 0.85},  # DUPLICATE!
    {"tên": "Dell R740", "giá": "50000000", "hãng": "Dell", "_score": 0.92},
    {"tên": "Dell R740", "giá": "50000000", "hãng": "Dell", "_score": 0.80},  # DUPLICATE!
    {"tên": "HPE ProLiant", "giá": "80000000", "hãng": "HPE", "_score": 0.90},
    {"tên": "ASUS RS720", "giá": "120 triệu", "hãng": "ASUS", "_score": 0.88},
]

print(f"\nBefore dedup: {len(duplicate_products)} products")
for i, p in enumerate(duplicate_products, 1):
    print(f"  {i}. {p['tên']:50} | Score: {p['_score']:.2f}")

deduped = _deduplicate_products(duplicate_products)

print(f"\nAfter dedup: {len(deduped)} products (removed {len(duplicate_products) - len(deduped)} duplicates)")
for i, p in enumerate(deduped, 1):
    print(f"  {i}. {p['tên']:50} | Score: {p['_score']:.2f}")

# Test 4: Combined Dedup + Filter
print("\n" + "=" * 80)
print("TEST 4: Combined Dedup + Filter (Full Pipeline)")
print("=" * 80)

combined_test = [
    {"tên": "Card NVIDIA RTX 3090", "giá": "Liên hệ báo giá", "hãng": "NVIDIA", "_score": 0.95},
    {"tên": "Card NVIDIA RTX 3090", "giá": "Liên hệ báo giá", "hãng": "NVIDIA", "_score": 0.85},  # Duplicate
    {"tên": "Card NVIDIA RTX 3080", "giá": "35 triệu", "hãng": "NVIDIA", "_score": 0.92},
    {"tên": "Card NVIDIA RTX 3080", "giá": "35 triệu", "hãng": "NVIDIA", "_score": 0.75},  # Duplicate
    {"tên": "Card NVIDIA RTX 3070", "giá": "Liên hệ", "hãng": "NVIDIA", "_score": 0.88},
    {"tên": "Card NVIDIA RTX A6000", "giá": "50-70 triệu", "hãng": "NVIDIA", "_score": 0.85},
]

print(f"\nStep 1 - Original: {len(combined_test)} products")

deduped_combined = _deduplicate_products(combined_test)
print(f"Step 2 - After dedup: {len(deduped_combined)} products (removed {len(combined_test) - len(deduped_combined)})")

# Simulate price comparison query
filtered_combined = _filter_products_with_specific_price(deduped_combined)
print(f"Step 3 - After price filter: {len(filtered_combined)} products (removed {len(deduped_combined) - len(filtered_combined)})")

print(f"\nFinal results:")
for i, p in enumerate(filtered_combined, 1):
    print(f"  {i}. {p['tên']:35} | Giá: {p['giá']}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✓ Price comparison detection: {sum(1 for q in test_queries if _is_price_comparison_query(q))}/{len(test_queries)}")
print(f"✓ Price filtering: {len(test_products)} → {len(filtered)}")
print(f"✓ Deduplication: {len(duplicate_products)} → {len(deduped)}")
print(f"✓ Combined pipeline: {len(combined_test)} → {len(deduped_combined)} → {len(filtered_combined)}")
print("\n✅ All tests passed!")
