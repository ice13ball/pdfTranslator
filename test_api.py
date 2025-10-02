from openai import AzureOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

try:
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "user", "content": "Hello, translate 'Hello world' to Spanish"}
        ]
    )
    print("API Test Successful:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"API Test Failed: {e}")
