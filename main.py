import os
import asyncio
import requests
from dotenv import load_dotenv

from langchain.tools import tool
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from openfga_sdk import (
    OpenFgaClient,
    ClientConfiguration,
)
from openfga_sdk.client.models import ClientCheckRequest

load_dotenv()


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Add it to your .env file before starting the app."
        )
    return value


GOOGLE_API_KEY = get_required_env("GOOGLE_API_KEY")
GOOGLE_MODEL_NAME = get_required_env("GOOGLE_MODEL_NAME")
STORE_ID = get_required_env("STORE_ID")
MODEL_ID = get_required_env("MODEL_ID")

llm = ChatGoogleGenerativeAI(
    model=GOOGLE_MODEL_NAME,
    google_api_key=GOOGLE_API_KEY,
    temperature=0.2,
)

fga_config = ClientConfiguration(
    api_url="http://localhost:8080",
    store_id=STORE_ID,
    authorization_model_id=MODEL_ID,
)


def check_opa(action: str) -> bool:
    try:
        response = requests.post(
            "http://localhost:8181/v1/data/agent/authz",
            json={
                "input": {
                    "action": action,
                    "time": "16:00",  # change to test policy
                }
            },
        )
        return response.json()["result"]["allow"]
    except Exception as e:
        print("OPA Error:", e)
        return False


async def check_fga(user: str, relation: str, obj: str) -> bool:
    fga_client = OpenFgaClient(fga_config)
    try:
        result = await fga_client.check(
            ClientCheckRequest(
                user=user,
                relation=relation,
                object=obj,
            )
        )
        return result.allowed
    except Exception as e:
        print("FGA Error:", e)
        return False
    finally:
        await fga_client.close()


async def authorize(user, action, relation, obj):
    if not check_opa(action):
        raise Exception(f"❌ Blocked by OPA: {action}")

    allowed = await check_fga(user, relation, obj)
    if not allowed:
        raise Exception(f"❌ Blocked by OpenFGA: {relation} on {obj}")

    return True

CURRENT_AGENT = "agent:worker-1" 

@tool
def read_file(filename: str) -> str:
    """Read a file (requires authorization)"""
    asyncio.run(authorize(
        CURRENT_AGENT,
        "read_file",
        "can_read",
        f"file:{filename}"
    ))

    with open(filename, "r") as f:
        return f.read()


@tool
def create_pr(repo: str) -> str:
    """Create a PR in a repo (mock)"""
    asyncio.run(authorize(
        CURRENT_AGENT,
        "create_pr",
        "can_write",
        f"repo:{repo}"
    ))

    return f"✅ PR successfully created in {repo}"

agent = create_agent(
    model=llm,
    tools=[read_file, create_pr],
    system_prompt="You are a secure assistant. Use tools to satisfy user requests.",
)

def run_multi_agent_task():
    global CURRENT_AGENT

    orchestrator = "agent:orchestrator"
    worker = "agent:worker-1"

    print("\n🧠 Orchestrator planning task...")

    allowed = asyncio.run(check_fga(
        orchestrator,
        "can_read",
        "repo:my-repo"
    ))

    if not allowed:
        raise Exception("❌ Orchestrator cannot delegate")

    print("🔐 Delegation allowed")

    CURRENT_AGENT = worker

    print(f"⚙️ Worker {worker} executing task...\n")

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Read notes.txt and then create a PR in my-repo",
                }
            ]
        }
    )

    return result["messages"][-1].content


if __name__ == "__main__":
    print("\n🚀 Running Multi-Agent System...\n")

    try:
        result = run_multi_agent_task()
        print("\n✅ RESULT:\n", result)

    except Exception as e:
        print("\n❌ ERROR:\n", e)
