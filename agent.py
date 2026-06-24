from tools.normal.tools import search_server_products
from agents import Agent
from os import getenv


LOCAL_MODEL = getenv("LOCAL_MODEL", "qwen2.5:7b-instruct")

local_assistant_agent = Agent(
    name="Local Assistant Agent",
    instructions="""Bạn là trợ lý AI chạy local. Hãy trả lời ngắn gọn, rõ ràng bằng tiếng Việt.
    Nếu câu hỏi thuộc phạm vi tìm sản phẩm máy chủ từ database, hãy để orchestrator chuyển sang agent phù hợp.
    """,
    model=LOCAL_MODEL,
)

server_product_agent = Agent(
    name="Server Product Agent",
    instructions="""You are a server product agent that searches for server products from Vector Database.
    You help users find and filter server products based on natural language queries:
    - Price searches: "máy chủ dưới 200k", "máy chủ từ 100k đến 500k"
    - Configuration searches: "máy có 16 core", "Dell R760xs", "HPE ProLiant"
    - Brand searches: "máy Dell", "máy HPE", "máy ASUS"
    - Combined searches: "máy Dell dưới 300k", "HPE 8 core giá rẻ"
    
    When a user asks for products:
    1. Understand their natural language query
    2. Convert it to a semantic search query
    3. Use the search_server_products tool to query the vector database
    4. Present the results clearly in Vietnamese with product name, price, and specifications.
    
    The tool will return results from vector database sorted by relevance.
    """,
    tools=[search_server_products],
    model=LOCAL_MODEL,
)

orchestrator_agent = Agent(
    name="Orchestrator Agent",
    instructions="""You are a orchestrator agent that orchestrates the other agents.
    You will be given a query and you will need to decide which agent to use to answer the query.
    - If the query is a general question, you will use the local assistant agent.
    - If the query is about server products from Siêu Thị Máy Chủ, you will use the server product agent.
    """,
    tools=[
        local_assistant_agent.as_tool(
            tool_name="local_assistant",
            tool_description="Trả lời các câu hỏi chung bằng mô hình local.",
        ),
        server_product_agent.as_tool(
            tool_name="search_server_products",
            tool_description="Search for server products from Siêu Thị Máy Chủ website by price, configuration, or brand.",
        ),
    ],
    model=LOCAL_MODEL,
)