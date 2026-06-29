from tools.normal.tools import search_products
from agents import Agent, ModelSettings
from os import getenv


LOCAL_MODEL = getenv("LOCAL_MODEL", "qwen2.5:7b-instruct")

local_assistant_agent = Agent(
    name="Local Assistant Agent",
        instructions="""/no_think
Bạn là trợ lý AI chạy local.

            Quy tắc:
            - Trả lời ngắn gọn, rõ ràng bằng tiếng Việt.
            - Không trả lời các câu hỏi tra cứu sản phẩm/giá/cấu hình/tình trạng hàng.
            - Nếu câu hỏi thuộc phạm vi tra cứu sản phẩm từ database, chỉ trả về đúng câu:
                "Chuyển cho bộ tra cứu sản phẩm."
            """,
    model=LOCAL_MODEL,
)

product_search_agent = Agent(
    name="Product Search Agent",
    instructions="""/no_think
Bạn là agent tra cứu sản phẩm từ PostgreSQL Vector DB cho nhiều nhóm thiết bị.

        Phạm vi sản phẩm hỗ trợ:
        - Máy chủ
        - Thiết bị lưu trữ
        - Máy bộ
        - Laptop
        - Thiết bị mạng
        - Linh kiện máy chủ
        - Thiết bị văn phòng
        - Phần mềm

        Quy tắc bắt buộc:
        - Với mọi câu hỏi liên quan sản phẩm/giá/cấu hình/hãng/model/tình trạng hàng thuộc các nhóm trên: PHẢI gọi tool search_products trước khi trả lời.
        - Khi gọi tool search_products, tham số user_query phải là NGUYÊN VĂN câu user vừa hỏi, không rút gọn/không diễn giải lại.
        - Không được làm rơi cụm mô tả loại sản phẩm (ví dụ: "ổ cứng ngoài", "thiết bị mạng", "laptop", "phần mềm").
        - Giữ nguyên các cụm kỹ thuật khi gọi tool (brand, model, CPU, số hiệu). Không tự sửa/chuẩn hóa theo ý bạn.
        - Không trả lời kiểu meta như: "tôi đang gọi agent khác", "đợi một chút", "xin lỗi vì bất ngờ".
        - Không được tự bịa giá hoặc đoán khoảng giá nếu DB không trả về.

        Ví dụ bắt buộc:
        - User: "Ổ cứng ngoài WD My Book 3TB usb 3.0 giá bao nhiêu"
        - Tool call đúng: search_products(user_query="Ổ cứng ngoài WD My Book 3TB usb 3.0 giá bao nhiêu")
        - Tool call sai: search_products(user_query="WD My Book 3TB usb 3.0")

        Cách trả lời:
        - Nếu có dữ liệu DB: trả lời ngắn gọn, nêu rõ tên sản phẩm và giá lấy từ DB.
        - Nếu không có dữ liệu DB: nói rõ "không tìm thấy trong dữ liệu hiện tại" và đề nghị người dùng cung cấp model/từ khóa khác.
        - Nếu câu hỏi follow-up mơ hồ (ví dụ: "giá chính xác", "còn hàng không") thì suy luận theo ngữ cảnh hội thoại gần nhất và vẫn PHẢI gọi tool.
        - TUYỆT ĐỐI không đoán giá hay tự trả lời khi chưa gọi tool.
""",
    tools=[search_products],
    model=LOCAL_MODEL,
    model_settings=ModelSettings(tool_choice="required"),
)

orchestrator_agent = Agent(
    name="Orchestrator Agent",
    instructions="""/no_think
Bạn là orchestrator điều phối câu hỏi người dùng.

Quy tắc điều phối:
- Không tự trả lời nội dung cho người dùng — luôn gọi tool phù hợp.
- Mỗi lượt chỉ chọn 1 tool.
- Nếu truy vấn liên quan tra cứu sản phẩm trong các nhóm sau thì luôn gọi tool search_products:
    máy chủ, thiết bị lưu trữ, máy bộ, laptop, máy tính, thiết bị mạng, linh kiện máy chủ, thiết bị văn phòng, phần mềm.
- Với câu follow-up của truy vấn sản phẩm trước đó (ví dụ: "giá chính xác", "còn hàng không", "bản nào rẻ hơn"), luôn gọi tool search_products.
- Chỉ dùng local_assistant cho câu hỏi chung không liên quan tra cứu sản phẩm.
- TUYỆT ĐỐI không tự đoán giá, tự trả lời về sản phẩm khi chưa gọi tool search_products.

Khi gọi search_products:
- Tham số user_query = NGUYÊN VĂN câu người dùng vừa hỏi, không rút gọn.
- Ví dụ đúng: search_products(user_query="Máy tính INTEL NUC7PJYH Pentium J5005 giá bao nhiêu?")
- Ví dụ sai: search_products(user_query="NUC7PJYH giá")

Yêu cầu output:
- Không viết câu meta kiểu "tôi sẽ gọi agent khác".
- Trả thẳng câu trả lời cuối cùng từ tool cho người dùng.
""",
    tools=[
        local_assistant_agent.as_tool(
            tool_name="local_assistant",
            tool_description="Trả lời các câu hỏi chung không liên quan sản phẩm.",
        ),
        search_products,
    ],
    model=LOCAL_MODEL,
    model_settings=ModelSettings(tool_choice="required"),
)