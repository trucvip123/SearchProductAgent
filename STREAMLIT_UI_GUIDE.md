## SearchProductAgent UI Guide

Hướng dẫn sử dụng giao diện Web Streamlit cho SearchProductAgent

---

## 🚀 Khởi động

### Cách 1: Quickstart Script
```bash
python quickstart.py
# Chọn "1" để chạy Streamlit UI
```

### Cách 2: Trực tiếp
```bash
streamlit run streamlit_app.py
```

Ứng dụng sẽ mở ở `http://localhost:8501`

---

## 📋 Các Thành Phần UI

### 1. **Sidebar (Trái)**
Cài đặt và thông tin agent:

- **🔍 Verbose Mode**: Bật/tắt logs chi tiết
- **📋 Hiển thị Logs**: Bật/tắt bảng logs
- **↓ Auto Scroll Logs**: Tự động cuộn logs
- **📊 Thông tin Agent**: Model LLM, endpoint hiện tại
- **🗑️ Xóa lịch sử**: Reset conversation
- **📖 Về SearchProductAgent**: Thông tin dự án

### 2. **Main Chat Area (Giữa)**

#### **📌 Current Product Context**
Hiển thị sản phẩm/thực thể đang được hỏi:
- Nếu có product: `📌 **Sản phẩm hiện tại:** [product name]`
- Nếu không: `ℹ️ Chưa có sản phẩm trong context`
- Nút **🔄 Reset**: Xóa product hiện tại

#### **💬 Chat Display**
Hiển thị lịch sử hội thoại:
- 👤 User messages (trái, màu xanh)
- 🤖 Assistant messages (phải, màu xám)
- Auto-scroll khi có tin nhắn mới

#### **📝 Input Box**
Ô nhập câu hỏi: `Nhập câu hỏi của bạn...`

#### **📊 Metadata Display**
Sau mỗi response:
- **⚠️ Topic changed**: Phát hiện thay đổi chủ đề
- **✓ Same topic**: Giữ context
- **📞 Tools**: Công cụ được gọi
- **📊 Results**: Số kết quả trả về

### 3. **Logs Panel (Dưới)**
Hiển thị 50 logs gần nhất (nếu **Hiển thị Logs** bật):
```
[10:30:45] ✓ Topic change detected: resetting context
[10:30:45] ✓ Query enriched: 'AMD ...' → 'AMD Opteron 8354 ...'
[10:30:46] 📞 TOOL_CALL: search_products
[10:30:47] 📊 TOOL_RESULT: search_products → 5 products
[10:30:47] ✓ Agent response ready (342 chars)
```

### 4. **Statistics Panel (Dưới)**
Thống kê nếu có tin nhắn hoặc tool calls:
- **💬 Tin nhắn**: Tổng số tin nhắn
- **📞 Tool calls**: Tổng số lần gọi tool
- **📝 Logs**: Số dòng logs
- **🛠️ Unique Tools**: Số loại tool khác nhau

---

## 🎯 Ví Dụ Sử Dụng

### Ví dụ 1: Tìm máy chủ Dell
```
User: Tìm máy chủ Dell dưới 50 triệu
→ [STATUS] Same topic, search_products called, 3 products returned
→ [RESPONSE] Đây là 3 máy chủ Dell dưới 50 triệu...

User: Giá của cái thứ hai bao nhiêu?
→ [STATUS] Same topic (keeping context "Dell R750")
→ [RESPONSE] Máy chủ thứ hai giá...
```

### Ví dụ 2: Topic Change Detection
```
User: Tìm máy chủ AMD dưới 100 triệu
→ [CONTEXT] product="AMD Opteron 8354..."
→ [STATUS] Same topic, search_products called, 5 products returned

User: Cho tôi xin các chip Intel dưới 1 triệu
→ [STATUS] ⚠️ Topic changed! (AMD vs Intel)
→ [ACTION] Context reset, current_product = None
→ [RESPONSE] Đây là các chip Intel dưới 1 triệu...
```

---

## ⚙️ Cài Đặt

### **🔍 Verbose Mode**
- **Bật**: Hiển thị chi tiết TOOL_CALL, TOOL_RESULT, query enrichment
- **Tắt**: Chỉ hiển thị main events

**Khuyến cáo**: Bật verbose mode để debug, tắt để giao diện sạch sẽ

### **📋 Hiển thị Logs**
- **Bật**: Hiển thị bảng logs dưới chat (50 logs gần nhất)
- **Tắt**: Ẩn bảng logs

### **↓ Auto Scroll Logs**
- **Bật**: Tự động cuộn logs khi có log mới
- **Tắt**: Giữ vị trí scroll hiện tại

---

## 🔄 Quản Lý Session

### Reset Conversation
1. Bấm nút **🗑️ Xóa lịch sử** ở sidebar
2. Hoặc bấm **🔄 Reset** bên cạnh Current Product

### Khởi động lại
- Refresh trang: `F5` hoặc `Ctrl+R`
- Hoặc click **🔄 Streamlit Rerun** (bên phải)

---

## 🛠️ Troubleshooting

### Streamlit không mở được
```bash
# Kiểm tra port 8501
netstat -an | findstr 8501

# Thay đổi port
streamlit run streamlit_app.py --server.port 8502
```

### Logs không hiển thị
- Kiểm tra **📋 Hiển thị Logs** ở sidebar
- Hoặc kiểm tra **🔍 Verbose Mode** nếu muốn chi tiết

### Agent không trả lời
1. Kiểm tra Ollama: `curl http://localhost:11434/api/tags`
2. Kiểm tra `.env`:
   - `OPENAI_BASE_URL=http://localhost:11434/v1`
   - `LOCAL_MODEL=qwen2.5:7b-instruct` (hoặc model của bạn)

### PostgreSQL connection error
- Kiểm tra `.env`: POSTGRES_* variables
- Kiểm tra PostgreSQL đang chạy
- Kiểm tra credentials đúng

---

## 📊 Logs Format

Mỗi log có format:
```
[HH:MM:SS] [PREFIX] Thông điệp

Prefixes:
✓    = Success
⚠️    = Warning
❌   = Error
📌   = Info
📞   = Tool Call
📊   = Tool Result
🔄   = Processing
```

---

## 💡 Tips & Tricks

### 1. **Debug Topic Change**
Bật Verbose Mode để thấy:
```
[TOPIC_DETECT] current_brand=amd, query_brand=intel
[TOPIC_DETECT] MATCH → Topic change (brand mismatch: amd vs intel)
```

### 2. **Track Query Enrichment**
```
[QUERY_BUILD] Query enriched: 'giá bao nhiêu?' → 'AMD Opteron 8354 giá bao nhiêu?'
```

### 3. **Monitor Tool Results**
```
[STREAM] TOOL_RESULT: search_products → 5 products
[STATE] Product detected: Intel Xeon E5-2690...
```

### 4. **View Full Logs**
Nếu chat area quá nhỏ, scroll logs panel để xem tất cả

---

## 🔗 Liên kết Nhanh

- 📚 [README](README.md) - Hướng dẫn cài đặt toàn bộ
- 🤖 [agent.py](agent.py) - Cấu hình agent & prompt
- 🛠️ [tools.py](tools/normal/tools.py) - Định nghĩa công cụ search
- 💬 [main.py](main.py) - CLI mode version
- 🌐 [streamlit_app.py](streamlit_app.py) - Web UI (file này)

---

## 📝 Thông Tin Khác

**Phiên bản**: 1.0  
**Framework**: Streamlit + LangChain + Ollama  
**Python**: 3.10+  
**Cập nhật lần cuối**: 2026-07-02
