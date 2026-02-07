from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from splitwise_mcp.client import SplitwiseClient
import os

app = FastAPI(title="Splitwise ChatGPT Connector", description="API to manage Splitwise expenses via ChatGPT")

# Global client
client = SplitwiseClient()

class ConfigureRequest(BaseModel):
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    api_key: Optional[str] = None

class LoginTokenRequest(BaseModel):
    access_token: str

class AddExpenseRequest(BaseModel):
    amount: str
    description: str
    friend_names: List[str]

@app.get("/list_friends")
def list_friends():
    """List all friends."""
    if not client.client:
        raise HTTPException(status_code=401, detail="Not configured. Please call /configure or /login_with_token first.")
    
    try:
        friends = client.get_friends()
        output = []
        for f in friends:
             output.append({
                 "id": f.getId(),
                 "name": f"{f.getFirstName() or ''} {f.getLastName() or ''}".strip()
             })
        return {"friends": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_expense")
def add_expense(req: AddExpenseRequest):
    """Add an expense."""
    if not client.client:
        raise HTTPException(status_code=401, detail="Not configured.")
        
    try:
        expense = client.add_expense(req.amount, req.description, req.friend_names)
        if expense:
            return {"status": "success", "id": expense.getId(), "message": f"Added {req.amount} for {req.description}"}
        else:
             raise HTTPException(status_code=400, detail="Failed to add expense")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/configure")
def configure(req: ConfigureRequest):
    """Set API Keys manually."""
    try:
        client.configure(req.consumer_key, req.consumer_secret, req.api_key)
        return {"status": "success", "message": "Configured successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login_with_token")
def login_with_token(req: LoginTokenRequest):
    """Log in with OAuth2 token."""
    try:
        client.configure(access_token=req.access_token)
        return {"status": "success", "message": "Logged in successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
