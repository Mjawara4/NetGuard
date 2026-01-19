
import os
import sys
from google import genai

# from dotenv import load_dotenv
# load_dotenv() # handled by shell

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Try .env
    # load_dotenv('.env')
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env.production or .env")
    sys.exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("Listing available models...")
    # List models
    # The new SDK might use client.models.list() or similar. 
    # Based on snippets, it should be client.models.list()
    # We filter for 'generateContent' support
    
    models = client.models.list()
    found_any = False
    for m in models:
        # Check if it supports generateContent
        # m.supported_generation_methods usually contains 'generateContent'
        if 'generateContent' in (m.supported_generation_methods or []):
            print(f"- {m.name} (Display: {m.display_name})")
            found_any = True
            
    if not found_any:
        print("No models found supporting generateContent.")

except Exception as e:
    print(f"Error listing models: {e}")
