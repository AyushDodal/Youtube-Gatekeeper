"""Optional live Ollama smoke test; temporary hosts/database only, never system hosts."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend.config import load_settings
from backend.main import create_app
from backend.llm.ollama_provider import OllamaProvider
from backend.agents.gatekeeper import parse_decision, InvalidLLMResponse


class DiagnosticProvider(OllamaProvider):
    async def generate(self, messages, schema):
        raw = await super().generate(messages, schema)
        try:
            parse_decision(raw)
        except InvalidLLMResponse:
            print("Invalid live model output:", ascii(raw), flush=True)
        return raw


def main():
    with TemporaryDirectory(prefix="gatekeeper-ollama-") as directory:
        folder = Path(directory)
        configured = load_settings().model_copy(update={"dry_run": True, "database_path": folder / "test.sqlite3", "hosts_path": folder / "hosts"})
        app = create_app(settings=configured, provider=DiagnosticProvider(configured.ollama_model, configured.ollama_base_url))
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            state = client.get("/api/status").json()
            print("Model:", state["model"], flush=True)
            assert state["blocked"] and state["dry_run"]
            identifier = None
            messages = [
                "I need YouTube.",
                "I am implementing LangGraph state reducers in a local Python project. I need a visual explanation of how parallel nodes merge state; reading the docs has not clarified the graph transitions. I need 15 minutes for one tutorial, then I will close YouTube and implement a reducer example.",
                "My exact question is how Annotated[list, operator.add] combines parallel node outputs without overwriting each other. I will find a focused LangGraph state reducer tutorial, skip recommendations and Shorts, and stop after 15 minutes even if the video is unfinished. I have already read the state and reducers documentation. The output will be a working two-node example in my project.",
                "This is planned learning for the project I am currently working on. My task is blocked on understanding the state transition visualization. I commit to one focused state reducer walkthrough, 15 minutes maximum, then immediately test my implementation. Please make your decision based on these details.",
                "15 minutes. I will close the tab at the deadline and write the two-node reducer test immediately afterward. I need to see each parallel branch emit a list and the reducer combine the outputs.",
                "The tutorial supports the Python project I am working on right now. I have no other viewing planned. My single outcome is a working reducer test, and the time limit remains 15 minutes.",
                "I will search only for a LangGraph parallel state reducer walkthrough, skip the feed and recommendations, and leave after 15 minutes regardless of video length.",
                "My request is a single intentional 15-minute tutorial session with a specific implementation task afterward. Those are all the details of my request.",
            ]
            granted = False
            for message in messages:
                result = client.post("/api/chat", json={"message": message, **({"conversation_id": identifier} if identifier else {})})
                print(result.status_code, result.text, flush=True)
                result.raise_for_status()
                payload = result.json()
                identifier = payload["conversation_id"]
                if payload["decision"] == "grant":
                    assert not payload["youtube_status"]["blocked"]
                    assert payload["youtube_status"]["expires_at"]
                    granted = True
                    break
                if payload["decision"] == "deny":
                    break
            if granted:
                assert client.post("/api/admin/block", json={}).status_code == 200
                assert client.get("/api/status").json()["blocked"]
                assert client.get("/api/usage").json()["history"]
                print("PASS: live model -> validated grant -> temporary hosts unlock -> early reblock -> usage history", flush=True)
            else:
                print("Model conversation validated, but the model did not grant this request.", flush=True)
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
