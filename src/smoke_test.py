import time

from dotenv import load_dotenv
from google import genai

load_dotenv()  # copies .env into os.environ; Client() reads GEMINI_API_KEY from there
client = genai.Client()

MODELS = ["models/gemini-3.8-flash", "models/gemini-3.5-flash-lite"]

for model in MODELS:
    start = time.perf_counter()
    response = client.models.generate_content(model=model, contents="Reply with OK")
    elapsed = time.perf_counter() - start

    usage = response.usage_metadata
    print(f"{model}: {response.text!r} in {elapsed:.2f}s")
    print(f"  prompt={usage.prompt_token_count}"
          f"  answer={usage.candidates_token_count}"
          f"  thinking={usage.thoughts_token_count}"  # None if the model didn't think
          f"  total={usage.total_token_count}")