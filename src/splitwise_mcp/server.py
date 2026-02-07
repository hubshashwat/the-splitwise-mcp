from mcp.server.fastmcp import FastMCP
from splitwise_mcp.client import SplitwiseClient
import logging
import base64

# Initialize FastMCP
mcp = FastMCP("splitwise")

# Global client (for direct Splitwise tools)
client = SplitwiseClient()

# Lazy-initialized agent (for voice/text command tools)
_agent = None
_transcriber = None

def _get_agent():
    """Lazy-initialize the Gemini agent."""
    global _agent
    if _agent is None:
        from splitwise_mcp.agent.client import GeminiSplitwiseAgent
        _agent = GeminiSplitwiseAgent()
    return _agent

def _get_transcriber():
    """Lazy-initialize the Deepgram transcriber."""
    global _transcriber
    if _transcriber is None:
        from splitwise_mcp.agent.audio import AudioTranscriber
        _transcriber = AudioTranscriber()
    return _transcriber

# =============================================================================
# Voice Agent Tools (Full Pipeline)
# =============================================================================

@mcp.tool()
def voice_command(audio_base64: str) -> str:
    """
    Process a voice command for Splitwise.
    
    Accepts base64-encoded audio (WAV or MP3 format), transcribes it using Deepgram,
    processes the intent using Gemini, and executes Splitwise actions.
    
    Args:
        audio_base64: Base64-encoded audio data (WAV or MP3).
        
    Returns:
        The result of the voice command (e.g., confirmation, clarification request, or error).
    """
    try:
        # Decode audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Transcribe with Deepgram
        transcriber = _get_transcriber()
        transcript = transcriber.transcribe_bytes(audio_bytes)
        
        if not transcript or not transcript.strip():
            return "Could not transcribe audio. Please try again with clearer audio."
        
        # Process with Gemini agent
        agent = _get_agent()
        result = agent.process_and_execute(transcript)
        
        return f"Transcribed: \"{transcript}\"\n\nResult: {result}"
        
    except Exception as e:
        return f"Voice command error: {e}"

@mcp.tool()
def text_command(text: str) -> str:
    """
    Process a text command for Splitwise.
    
    Interprets natural language text using Gemini and executes Splitwise actions.
    Use this when you already have text (e.g., from a chat message) instead of audio.
    
    Args:
        text: Natural language command (e.g., "Split 50 with Sumeet for dinner").
        
    Returns:
        The result of the command (e.g., confirmation, clarification request, or error).
    """
    try:
        agent = _get_agent()
        result = agent.process_and_execute(text)
        return result
    except Exception as e:
        return f"Text command error: {e}"

# =============================================================================
# Direct Splitwise Tools (For Manual Control)
# =============================================================================

@mcp.tool()
def configure_splitwise(consumer_key: str = None, consumer_secret: str = None, api_key: str = None) -> str:
    """
    Configure the Splitwise client with API credentials.
    You must provide either (consumer_key AND consumer_secret) OR api_key.
    """
    try:
        client.configure(consumer_key, consumer_secret, api_key)
        # Verify it works by getting current user
        user = client.get_current_user()
        name = f"{user.getFirstName()} {user.getLastName()}".strip()
        return f"Successfully configured Splitwise for user: {name}"
    except Exception as e:
        return f"Configuration failed: {e}. Please check your keys."

@mcp.tool()
def login_with_token(access_token: str) -> str:
    """
    Log in using an existing OAuth2 Access Token.
    Useful for integrations where authentication is handled externally (e.g. ChatGPT).
    """
    try:
        client.configure(access_token=access_token)
        # Verify
        user = client.get_current_user()
        name = f"{user.getFirstName()} {user.getLastName()}".strip()
        return f"Successfully logged in as: {name}"
    except Exception as e:
        return f"Login failed: {e}. Token might be invalid."


@mcp.tool()
def list_friends() -> str:
    """
    List all friends of the current user on Splitwise.
    Returns a formatted string list of friends.
    """
    try:
        # Client check is handled inside client.get_friends()
        friends = client.get_friends()
        
        if not friends:
            return "No friends found."
        
        output = ["Current Friends:"]
        for f in friends:
            name = f"{f.getFirstName() or ''} {f.getLastName() or ''}".strip()
            output.append(f"- {name} (ID: {f.getId()})")
        
        return "\n".join(output)
        
    except ValueError as e:
         return f"Configuration Error: {e}"
    except Exception as e:
        return f"Error listing friends: {e}"

@mcp.tool()
def add_expense(
    amount: str, 
    description: str, 
    friend_names: list[str], 
    split_map: dict = None, 
    group_name: str = None, 
    payer_name: str = None, 
    exclude_names: list[str] = None
) -> str:
    """
    Add an expense to Splitwise, supporting unequal splits, groups, and precise control.
    
    Args:
        amount: The total cost (e.g., "70", "10.50").
        description: A brief description.
        friend_names: Friends to split with. Can be empty if using `group_name`.
        split_map: Optional dict for unequal splits. Keys=Names (or 'me'), Values=Amount/Percentage.
                   Example: {'me': '40%', 'Alice': '60%'} or {'me': '10', 'Bob': '20'}
        group_name: Optional group to add expense to.
        payer_name: Optional name of who paid. Defaults to 'me'.
        exclude_names: Optional list of names to exclude from a group split.
    """
    if not client.client:
        return "Error: Splitwise client not configured. Use 'configure_splitwise' first."

    try:
        expense = client.add_expense(
            amount, 
            description, 
            friend_names, 
            split_map=split_map, 
            group_name=group_name, 
            payer_name=payer_name, 
            exclude_names=exclude_names
        )
        if expense:
            return f"Successfully added expense '{description}' for {amount}. (ID: {expense.getId()})"
        else:
            errors = client.client.getErrors() 
            return f"Failed to add expense. Errors: {errors}"
            
    except ValueError as e:
        return f"Error validation: {e}"
    except Exception as e:
        return f"Error adding expense: {e}"

@mcp.tool()
def delete_expense(expense_id: str) -> str:
    """
    Delete an expense by its ID.
    """
    if not client.client:
        return "Error: Splitwise client not configured."
    
    try:
        client.delete_expense(expense_id)
        return f"Successfully deleted expense {expense_id}."
    except Exception as e:
        return f"Error deleting expense: {e}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()

