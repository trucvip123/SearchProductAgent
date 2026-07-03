## Price-Specific Filtering for SearchProductAgent

**Cập nhật:** 2026-07-02  
**Feature:** Tự động filter sản phẩm khi user so sánh giá

---

## 📋 Tính Năng

### **Auto-Detection: Query So Sánh Giá**

Khi user nhập query so sánh giá, system tự động detect và áp dụng filter:

```python
def _is_price_comparison_query(query: str) -> bool:
    """Phát hiện nếu query là so sánh giá"""
```

**Patterns được detect:**
- ✓ "dưới X triệu" → "Tìm máy chủ dưới 50 triệu"
- ✓ "từ X đến Y triệu" → "Từ 50 đến 150 triệu"
- ✓ "từ X tới Y triệu" → "Từ 10 tới 50 triệu"
- ✓ "X triệu trở lên" → "500 triệu trở lên"
- ✓ "rẻ hơn X triệu" → "Rẻ hơn 80 triệu"
- ✓ "đắt hơn X triệu" → "Đắt hơn 100 triệu"
- ✓ "giá dưới" → "Giá dưới 200 triệu"
- ✓ "so sánh giá" → "So sánh giá các máy chủ"
- ✓ "giá rẻ" / "rẻ hơn" → "Giá rẻ mà mạnh"

---

### **Auto-Filter: Loại Bỏ Sản Phẩm Không Có Giá Cụ Thể**

Khi detect price comparison query, tự động filter:

```python
def _filter_products_with_specific_price(products: List[Dict]) -> List[Dict]:
    """Filter để chỉ giữ sản phẩm có giá cụ thể"""
```

**Removed (không cụ thể):**
- ❌ "Liên hệ báo giá"
- ❌ "Liên hệ"
- ❌ "TBD"
- ❌ "N/A"
- ❌ "Unknown"
- ❌ "Chưa có"
- ❌ "Cập nhật"

**Kept (cụ thể):**
- ✅ "50000000" (số)
- ✅ "50 triệu"
- ✅ "50-100 triệu" (khoảng)
- ✅ "3.5 triệu"
- ✅ "1.2 tỷ"

---

## 🔄 Integration Flow

### **Scenario 1: User so sánh giá**

```
User Query: "Tìm máy chủ Dell dưới 100 triệu"
    ↓
Agent calls search_products
    ↓
search_products returns 5 products:
  - Dell R740: "50000000" ✓
  - Dell R750: "Liên hệ báo giá" ✗
  - HPE ProLiant: "80000000" ✓
  - HPE DL560: "Liên hệ" ✗
  - ASUS RS720: "120-150 triệu" ✓
    ↓
[FILTER] Price comparison detected
    ↓
Filtered result: 3 products (loại bỏ 2 "Liên hệ")
    ↓
Agent response: "Tìm được 3 máy chủ Dell dưới 100 triệu với giá cụ thể..."
```

### **Scenario 2: User không so sánh giá**

```
User Query: "Tìm thông tin máy chủ HPE nào?"
    ↓
Agent calls search_products
    ↓
search_products returns all matching products
    ↓
[NO FILTER] Not a price comparison query
    ↓
Agent response: "Máy chủ HPE gồm: ... (bao gồm cả 'Liên hệ báo giá')"
```

---

## 📊 Code Changes

### **File: tools/normal/tools.py**

**Added Functions:**
1. `_is_price_comparison_query(query: str) -> bool`
   - Detect price comparison patterns
   - Return: True nếu query so sánh giá

2. `_filter_products_with_specific_price(products: List[Dict]) -> List[Dict]`
   - Filter sản phẩm theo giá
   - Return: List products có giá cụ thể

**Modified Function:**
- `search_products()`: Added filter logic trước khi return JSON
  ```python
  # ── Filter sản phẩm nếu query là so sánh giá ─────────────────────
  is_price_comparison = _is_price_comparison_query(base_query) or _is_price_comparison_query(effective_query)
  if is_price_comparison and products:
      original_count = len(products)
      products = _filter_products_with_specific_price(products)
      _log("FILTER", f"Price comparison query detected: filtered {original_count} → {len(products)} products")
  ```

---

## 🧪 Test Results

```
TEST 1: Price Comparison Query Detection
✓ PRICE COMPARISON             | Tìm máy chủ Dell dưới 100 triệu đồng
✓ PRICE COMPARISON             | Từ 50 đến 150 triệu
✓ PRICE COMPARISON             | Giá rẻ hơn 80 triệu
✓ PRICE COMPARISON             | So sánh giá các máy chủ HPE
✓ PRICE COMPARISON             | Tìm máy chủ 500 triệu trở lên
✗ NOT price comparison         | Giá máy chủ bao nhiêu?
✗ NOT price comparison         | Tìm cấu hình máy chủ

TEST 2: Product Filtering
Before filter: 7 products
After filter: 3 products
Removed: 4 products with non-specific prices ("Liên hệ", "N/A", "TBD", "Liên hệ báo giá")

✅ All tests passed!
```

---

## 🎯 Usage

### **As End User:**

```
👤 User: "Tìm máy chủ Dell dưới 100 triệu, so sánh giá"
🤖 Agent: "Tìm được 3 máy chủ Dell với giá cụ thể:
  1. Dell R740 - 50 triệu
  2. Dell R750 - 75 triệu
  3. Dell R760 - 90 triệu"
```

### **In Logs:**

```
[2026-07-02 10:48:25] [search_products] [START] user_query='Tìm máy chủ Dell dưới 100 triệu'
[2026-07-02 10:48:26] [search_products] [RESULT] Products parsed=5
[2026-07-02 10:48:26] [search_products] [FILTER] Price comparison query detected: filtered 5 → 3 products
[2026-07-02 10:48:26] [search_products] [DONE] Successfully found 3 products from PostgreSQL
```

---

## 📝 Notes

1. **Non-Fatal Filter**: Nếu filter loại bỏ tất cả sản phẩm, agent sẽ nhận được empty list → có thể inform user "Không tìm thấy sản phẩm với giá cụ thể"

2. **Price Range Detection**: System detect được cả range prices (ví dụ "50-100 triệu") → không bị loại bỏ

3. **Case-Insensitive**: Filter work với cả chữ hoa/thường: "LIÊN HỆ", "liên hệ", "Liên Hệ" → đều bị detect

4. **Multilingual**: Hiện tại hỗ trợ tiếng Việt. Nếu cần expand, thêm keywords vào `skip_keywords` list

---

## 🚀 Future Enhancements

- [ ] Parse giá thành số để so sánh (ví dụ: "50 triệu" → 50000000)
- [ ] Rank sản phẩm theo giá khi user so sánh
- [ ] Store price range patterns per brand
- [ ] Add price range analysis (avg, min, max)
- [ ] Multilingual support (English, Chinese, etc.)

---

**Status:** ✅ Complete  
**Test File:** [test_price_filter.py](test_price_filter.py)  
**Implementation Date:** 2026-07-02
