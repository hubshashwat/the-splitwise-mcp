import sys
from splitwise_mcp.agent.audio import AudioTranscriber
from splitwise_mcp.agent.client import SplitwiseAgent
from colorama import Fore, Style
import time
import json

def main():
    print(f"{Fore.GREEN}🤖 Splitwise Voice Agent (with Confirmation){Style.RESET_ALL}")
    print("Commands:")
    print(" - 'v' or 'voice':  Record 10s of audio")
    print(" - 't' or 'text':   Type text input")
    print(" - 'q' or 'quit':   Exit")
    
    agent = SplitwiseAgent()
    transcriber = AudioTranscriber()
    
    while True:
        try:
            choice = input(f"\n{Fore.BLUE}Enter command (voice/text/quit): {Style.RESET_ALL}").strip().lower()
            
            if choice in ['q', 'quit']:
                print("Bye!")
                break
                
            user_text = ""
            
            if choice in ['v', 'voice']:
                try:
                    audio_path = transcriber.record_audio(duration=10)
                    user_text = transcriber.transcribe(audio_path)
                    transcriber.cleanup(audio_path)
                    print(f"🗣️  You said: {Style.BRIGHT}{user_text}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Audio Error: {e}{Style.RESET_ALL}")
                    continue

            elif choice in ['t', 'text']:
                user_text = input("Enter request: ")

            else:
                continue
                
            if user_text:
                # --- Interaction Loop for Confirmation ---
                current_text = user_text
                
                while True:
                    result = agent.process_input(current_text)
                    
                    if result["type"] == "text":
                        print(f"\n{Fore.MAGENTA}🤖 Agent: {result['content']}{Style.RESET_ALL}")
                        break # Done with this turn
                        
                    elif result["type"] == "confirmation_required":
                        tool_name = result["tool_name"]
                        args = result["tool_args"]
                        
                        print(f"\n{Fore.YELLOW}⚠️  Proposed Action:{Style.RESET_ALL}")
                        print(f"   Function: {tool_name}")
                        print(f"   Args: {json.dumps(args, indent=2)}")
                        
                        confirm = input(f"\n{Fore.WHITE}Proceed? (yes/edit/cancel): {Style.RESET_ALL}").lower().strip()
                        
                        if confirm in ['y', 'yes']:
                            print("Executing...")
                            final_resp = agent.execute_tool_and_reply(tool_name, args)
                            print(f"\n{Fore.MAGENTA}🤖 Agent: {final_resp}{Style.RESET_ALL}")
                            break # Request completed
                            
                        elif confirm in ['c', 'cancel', 'n', 'no']:
                            print("❌ Cancelled action.")
                            break # Break loop, go back to main menu
                            
                        else:
                            # User wants to edit or provided feedback
                            # e.g. "No, make it 15"
                            feedback_text = confirm
                            # If they just said "edit", ask for details
                            if feedback_text == "edit":
                                feedback_text = input("What corrections? (e.g. 'amount is 15'): ")
                            
                            print(f"🔄 Feedback: {feedback_text}")
                            # We feed this back as 'current_text' to the agent loop
                            current_text = feedback_text
                            # Loop continues... agent.process_input(feedback_text) will be called next
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
