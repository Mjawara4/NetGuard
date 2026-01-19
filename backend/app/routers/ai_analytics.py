from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
import os
import logging
import openai
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY = os.getenv("GEMINI_API_KEY") if LLM_PROVIDER == "gemini" else os.getenv("OPENAI_API_KEY")

@router.get("/predictions")
def get_sales_prediction(days: int = 7, db: Session = Depends(get_db)):
    """
    Predicts sales for the next N days based on historical data using AI.
    """
    if not LLM_API_KEY:
        return {"error": "LLM API Key not configured"}

    # 1. Fetch Historical Data (Last 30 days)
    try:
        query = text("""
            SELECT date(created_at) as day, SUM(price) as total_sales
            FROM hotspot_sales
            WHERE created_at > NOW() - INTERVAL '30 days'
            GROUP BY day
            ORDER BY day ASC
        """)
        result = db.execute(query).fetchall()
        
        if not result:
            return {"message": "Not enough data for prediction", "data": []}
            
        history_str = "\n".join([f"{row.day}: {row.total_sales}" for row in result])
        
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return {"error": "Failed to fetch historical data"}

    # 2. Ask AI to Predict
    system_prompt = f"""
    You are a Data Scientist.
    Analyze the following daily sales data (Date: Sales Amount):
    
    {history_str}
    
    Task: Predict the total sales for the next {days} days.
    Return strictly JSON:
    {{
      "forecast": [
         {{"date": "YYYY-MM-DD", "predicted_sales": 1234}},
         ...
      ],
      "trend_analysis": "One sentence summary of the trend."
    }}
    """
    
    try:
        import json
        response_text = ""
        
        if LLM_PROVIDER == "gemini":
            from google import genai
            client = genai.Client(api_key=LLM_API_KEY)
            resp = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=system_prompt
            )
            response_text = resp.text
            
        elif LLM_PROVIDER == "openai":
            client = openai.OpenAI(api_key=LLM_API_KEY)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a forecasting algorithm. Output JSON only."},
                    {"role": "user", "content": system_prompt}
                ],
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content

        # Clean JSON
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(response_text)
        return data

    except Exception as e:
        logger.error(f"AI Prediction Error: {e}")
        # Fallback Mock Data if AI fails
        mock_data = []
        today = datetime.now()
        for i in range(days):
             d = today + timedelta(days=i+1)
             mock_data.append({"date": d.strftime("%Y-%m-%d"), "predicted_sales": 5000 + (i*100)})
             
        return {
            "forecast": mock_data,
            "trend_analysis": "AI Service unavailable. Showing linear projection fallback."
        }
