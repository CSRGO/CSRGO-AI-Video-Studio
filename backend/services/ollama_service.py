import ollama
from backend.core.config import settings

class OllamaService:
    def __init__(self):
        self.client = ollama.Client(host=settings.ollama_base_url)

    def list_models(self):
        return self.client.list()

    def generate(self, prompt: str, model: str | None = None, system: str | None = None):
        response = self.client.generate(
            model=model or settings.ollama_model,
            prompt=prompt,
            system=system,
            options={"temperature": 0.7, "num_ctx": 4096},
        )
        return response.response

    def chat(self, messages: list[dict], model: str | None = None):
        response = self.client.chat(
            model=model or settings.ollama_model,
            messages=messages,
            options={"temperature": 0.7, "num_ctx": 4096},
        )
        return response.message.content

ollama_service = OllamaService()
