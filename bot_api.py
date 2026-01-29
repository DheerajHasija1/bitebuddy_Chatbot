from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import jwt
from main import get_data_from_database
from dotenv import load_dotenv
import os
import json  # 🔥 Add this

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://bitebuddy01.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("secret_key")

@app.post("/bot/query")
def bot_query(request: dict, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "No token provided")
    
    try:
        token = authorization.replace("Bearer ", "")
        
        # Decode JWT
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        print(f"📦 Full JWT Payload: {decoded}")
        
        # Extract userId and role
        user_id = decoded.get("userId")
        role = decoded.get("role", "ROLE_CUSTOMER")
        
        if not user_id:
            raise HTTPException(401, "userId not found in token")
        
        print(f"🔑 Decoded JWT: user_id={user_id}, role={role}")
        
        # Get data from database
        result = get_data_from_database(request["query"], user_id, role)
        
        # 🔥 Convert result to readable string
        if isinstance(result, dict) and "error" in result:
            response_text = f"Error: {result['error']}"
        elif isinstance(result, dict) and "message" in result:
            response_text = result['message']
        elif isinstance(result, list):
            if len(result) == 0:
                response_text = "No data found."
            else:
                # Format as readable string
                response_text = format_results_as_text(result)
        else:
            response_text = str(result)
        
        return {"success": True, "message": response_text}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {str(e)}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(500, f"Server error: {str(e)}")


# 🔥 NEW: Format results as readable text
def format_results_as_text(results):
    """Convert list of dicts to readable string format"""
    if not results:
        return "No results found."
    
    # If single result
    if len(results) == 1:
        result = results[0]
        lines = [f"{key}: {value}" for key, value in result.items()]
        return "\n".join(lines)
    
    # If multiple results - create a table-like format
    output = f"Found {len(results)} results:\n\n"
    for idx, result in enumerate(results, 1):
        output += f"--- Result {idx} ---\n"
        for key, value in result.items():
            output += f"{key}: {value}\n"
        output += "\n"
    
    return output.strip()