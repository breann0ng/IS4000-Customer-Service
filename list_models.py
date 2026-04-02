import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load env to get your key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env")
else:
    genai.configure(api_key=api_key)
    print(f"Checking available models for key: {api_key[:10]}...")
    try:
        models = genai.list_models()
        valid_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        if not valid_models:
            print("No models found with 'generateContent' support.")
        else:
            print("\nAvailable models for your account:")
            for name in valid_models:
                print(f" - {name}")
            print("\nSuggested: Use the name without the 'models/' prefix (e.g., gemini-1.5-flash-latest)")
    except Exception as e:
        if "API_KEY_INVALID" in str(e):
            print("Error: Your GEMINI_API_KEY is invalid. Please check .env")
        else:
            print(f"API Error: {e}")
