import asyncio
import os
from dotenv import load_dotenv
from agents import Runner, RunConfig
from openai.types.responses import ResponseTextDeltaEvent
from agents.items import TResponseInputItem


load_dotenv()
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")

from agent import orchestrator_agent, LOCAL_MODEL


async def main():
    run_config = RunConfig(tracing_disabled=True)

    print(f"Model running: {LOCAL_MODEL}")
    print(f"Endpoint: {os.getenv('OPENAI_BASE_URL')}")

    input_items: list[TResponseInputItem] = []
    while True:
        input_query = input("Enter the query: ")
        input_items.append({"content": input_query, "role": "user"})
        result = Runner.run_streamed(orchestrator_agent, input_items, run_config=run_config)
        async for item in result.stream_events():
            if item.type == "raw_response_event" and isinstance(item.data, ResponseTextDeltaEvent):
                print(item.data.delta, end="", flush=True)

        input_items = result.to_input_list()
        print("\n")

                

if __name__ == "__main__":
    asyncio.run(main())