import os
import json
from google import genai
from google.genai import types
from splitwise_mcp.client import SplitwiseClient
from colorama import Fore, Style

class GeminiSplitwiseAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             raise ValueError("Missing GEMINI_API_KEY in .env")
        
        self.client = genai.Client(api_key=api_key)
        self.splitwise = SplitwiseClient()
        self.model_name = "gemini-3-flash-preview"
        
        # Tools definitions
        self.tool_functions = {
            "add_expense": self._add_expense_impl,
            "list_friends": self._list_friends_impl,
            "delete_expense": self._delete_expense_impl,
            "_add_expense_impl": self._add_expense_impl,
            "_list_friends_impl": self._list_friends_impl,
            "_delete_expense_impl": self._delete_expense_impl
        }
        
        # Pre-load friends and groups for context
        print(f"{Fore.CYAN}👥 Pre-loading friends and groups...{Style.RESET_ALL}")
        try:
            friends = self.splitwise.get_friends()
            self.friend_list_str = ", ".join([f"{f.getFirstName()} {f.getLastName()} (ID: {f.getId()})" for f in friends])
            
            groups = self.splitwise.get_groups()
            self.group_list_str = ", ".join([f"{g.getName()} (ID: {g.getId()})" for g in groups])
        except Exception as e:
            print(f"{Fore.RED}⚠️ Failed to pre-load data: {e}{Style.RESET_ALL}")
            self.friend_list_str = "Could not load friends."
            self.group_list_str = "Could not load groups."

        system_prompt = (
            "You are a helpful assistant that manages Splitwise expenses.\n"
            f"Here is the user's current friend list: [{self.friend_list_str}].\n"
            f"Here is the user's current group list: [{self.group_list_str}].\n"
            "Rules:\n"
            "1. If the transcribed name does NOT exactly match a friend's name in the list, "
            "you MUST ask for clarification. For example, if user says 'Humeet' but you have 'Sumeet' in the list, "
            "ask 'Did you mean Sumeet?' Do NOT assume phonetic matches.\n"
            "2. If the name is completely not found, ask the user to spell it again.\n"
            "3. Do NOT guess friend IDs. Only use IDs from the list above.\n"
            "4. If the user wants to add an expense, call 'add_expense' with the matched friend names.\n"
            "5. If the user specifies unequal splits (e.g. 'I owe 10, Sumeet owes 20', or 'Split 50/50%'), use 'split_map'. "
            "Map 'me' or 'I' to the user's share, and friend names to their share (amounts or percentages).\n"
            "6. If the user mentions a group (e.g. 'add to Apartment group'), use 'group_name'. Match against the group list above.\n"
            "7. If the user specifies who paid (e.g. 'Alice paid'), use 'payer_name'. Default is YOU paid.\n"
            "8. If excluding someone from a group expense, use 'exclude_names'.\n"
            "9. To delete an expense, use 'delete_expense' with the ID (if known) or ask user for it.\n"
            "10. Be concise and conversational."
        )

        # Create chat session
        self.chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                tools=[self._add_expense_impl, self._list_friends_impl, self._delete_expense_impl],
                system_instruction=system_prompt,
                automatic_function_calling={"disable": True} 
            )
        )

    # --- Tool Implementations ---
    # --- Tool Implementations ---
    def _add_expense_impl(self, amount: str, description: str, friend_names: list[str], split_map: dict = None, group_name: str = None, payer_name: str = None, exclude_names: list[str] = None):
        """Add a new expense to Splitwise. Use this when the user wants to split a cost.
        
        Args:
            amount: The numeric amount of the expense (e.g. '50.00').
            description: Short description of the expense (e.g. 'Dinner', 'Cab').
            friend_names: List of names of friends to split with. Can be empty if matching a group.
            split_map: Optional dictionary for unequal splits. 
                       Keys are names (use 'me' for yourself), Values are amounts (e.g. '10.50') OR percentages (e.g. '50%').
                       Example: {'me': '40%', 'Sumeet Singh': '60%'}
            group_name: Optional name of the group to add this expense to.
            payer_name: Optional name of who paid the full amount. Defaults to current user if not specified.
            exclude_names: Optional list of names to exclude from a group split.
        """
        # This function won't be called automatically by Gemini anymore.
        # We will call it manually in 'execute_tool'.
        print(f"{Fore.YELLOW}🛠️  Executing: add_expense({amount}, {description}, {friend_names}, split_map={split_map}, group_name={group_name}, payer={payer_name}, exclude={exclude_names}){Style.RESET_ALL}")
        try:
            res = self.splitwise.add_expense(amount, description, friend_names, split_map=split_map, group_name=group_name, payer_name=payer_name, exclude_names=exclude_names)
            if res:
                return f"Success! Added expense (ID: {res.getId()})"
            return "Failed to add expense."
        except Exception as e:
            return f"Error: {e}"

    def _delete_expense_impl(self, expense_id: str):
        """Delete an expense by ID."""
        print(f"{Fore.YELLOW}🛠️  Executing: delete_expense({expense_id}){Style.RESET_ALL}")
        try:
            self.splitwise.delete_expense(expense_id)
            return f"Success! Deleted expense {expense_id}."
        except Exception as e:
            return f"Error: {e}"

    def _list_friends_impl(self):
        """List the user's friends on Splitwise."""
        print(f"{Fore.YELLOW}🛠️  Executing: list_friends(){Style.RESET_ALL}")
        try:
            friends = self.splitwise.get_friends()
            names = [f"{f.getFirstName()} {f.getLastName()}" for f in friends]
            return f"Friends: {', '.join(names)}"
        except Exception as e:
            return f"Error: {e}"

    # --- Agent Logic ---

    def process_input(self, user_text: str):
        """
        Sends text to Gemini. 
        Returns structure:
         { "type": "text", "content": "..." }
         OR
         { "type": "confirmation_required", "tool_name": "...", "tool_args": {...}, "call_id": ... }
        """
        print(f"{Fore.CYAN}🧠 Thinking...{Style.RESET_ALL}")
        response = self.chat.send_message(user_text)
        
        # Check if the model wants to call a function
        # response.parts is a list. Look for function_call.
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    tool_name = fc.name
                    tool_args = fc.args
                    
                    # Optimization: Auto-execute read-only tools
                    if tool_name == "_list_friends_impl":
                        print(f"{Fore.MAGENTA}🔄 Auto-executing read-only tool: {tool_name}{Style.RESET_ALL}")
                        # Execute and feed back to model
                        # 1. Execute tool locally.
                        func = self.tool_functions.get(tool_name)
                        if not func:
                             res_str = f"Error: Tool {tool_name} not found."
                        else:
                             res_str = func(**tool_args)
                        
                        # 2. Send ToolResponse to Gemini
                        tool_response_part = types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={'result': res_str}
                            )
                        )
                        print(f"{Fore.MAGENTA}📤 Sending auto-result back to model...{Style.RESET_ALL}")
                        
                        # Recurse: Ask model again
                        next_response = self.chat.send_message([tool_response_part])
                        
                        # Check THIS response for function calls (e.g. add_expense)
                        if next_response.candidates and next_response.candidates[0].content.parts:
                             for next_part in next_response.candidates[0].content.parts:
                                 if next_part.function_call:
                                     return {
                                        "type": "confirmation_required",
                                        "tool_name": next_part.function_call.name,
                                        "tool_args": next_part.function_call.args, 
                                        "call_id": "auto_recursive"
                                     }
                        
                        # Else it's text
                        return {
                            "type": "text",
                            "content": next_response.text
                        }



                    return {
                        "type": "confirmation_required",
                        "tool_name": tool_name,
                        "tool_args": tool_args, # Dictionary
                        "call_id": "manual_execution" 
                    }
        
        # Otherwise just text
        return {
            "type": "text",
            "content": response.text
        }

    def execute_tool_and_reply(self, tool_name, tool_args):
        """
        Executes the tool (after user said YES) and sends the output back to Gemini.
        Returns the final text response from Gemini.
        """
        # 1. Execute
        func = self.tool_functions.get(tool_name)
        if not func:
            result = f"Error: Tool {tool_name} not found."
        else:
            try:
                # Unpack args
                result = func(**tool_args)
            except Exception as e:
                result = f"Error calling function: {e}"

        print(f"{Fore.GREEN}✅ Output: {result}{Style.RESET_ALL}")

        # 2. Send result back to Gemini
        # We need to construct a ToolResponse part.
        
        # In the new SDK, we send the message with the function response.
        # We need to construct the 'parts' with 'function_response'.
        
        # NOTE: With automatic_function_calling disabled, we need to send the response manually.
        # The SDK expects us to send a message containing the function response.
        
        # part = types.Part.from_function_response(name=tool_name, response={'result': result}) 
        # API expects specific structure. 
        
        # Let's try sending it as a properly formatted tool response.
        tool_response_part = types.Part(
            function_response=types.FunctionResponse(
                name=tool_name,
                response={'result': result}
            )
        )

        try:
            response = self.chat.send_message([tool_response_part])
            return response.text
        except Exception as e:
            print(f"{Fore.RED}⚠️ Gemini failed to acknowledge tool execution: {e}{Style.RESET_ALL}")
            return f"✅ Action Executed Successfully: {result}\n\n(Note: Gemini could not generate a follow-up reply due to network/server issues)."

    def reject_tool(self, reason: str):
        """
        User said NO or provided correction.
        We send this feedback to Gemini so it can try again.
        """
        # We just send the user's correction text.
        # Gemini sees: 
        # User: "Split 50..."
        # Model: Call add_expense(50)
        # User (Feedback): "No, change amount to 15"
        # Model: Call add_expense(15)
        
        # BUT, if we just send "No..." does Gemini know we REJECTED the previous call?
        # Since we didn't send the ToolResponse, the previous turn is technically incomplete?
        # Actually in Google GenAI, if we don't send the function response, 
        # we might need to "rewind" or just send the text.
        # Sending text "No, do X" usually works as a follow up.
        
        # Let's treat it as a new user message.
        return self.process_input(reason)

    def process_and_execute(self, user_text: str) -> str:
        """
        Process user text and auto-execute any tool calls.
        Used by MCP server where tools should be executed without human confirmation.
        
        Returns the final response text (either from Gemini or tool execution result).
        """
        result = self.process_input(user_text)
        
        if result["type"] == "text":
            return result["content"]
        
        elif result["type"] == "confirmation_required":
            # Auto-execute the tool
            tool_name = result["tool_name"]
            tool_args = result["tool_args"]
            return self.execute_tool_and_reply(tool_name, tool_args)
        
        return "Unexpected response type."

# Export
SplitwiseAgent = GeminiSplitwiseAgent
