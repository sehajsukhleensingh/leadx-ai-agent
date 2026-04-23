from core.chatbot import bot
from langchain_core.messages import HumanMessage
from langsmith import traceable

def show_banner():
    banner = r"""
    ██╗     ███████╗ █████╗ ██████╗ ██╗  ██╗
    ██║     ██╔════╝██╔══██╗██╔══██╗╚██╗██╔╝
    ██║     █████╗  ███████║██║  ██║ ╚███╔╝ 
    ██║     ██╔══╝  ██╔══██║██║  ██║ ██╔██╗ 
    ███████╗███████╗██║  ██║██████╔╝██╔╝ ██╗
    ╚══════╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝

    LeadX AI — Social-to-Lead Agent
    -----------------------------------

    - Persistent Memory Enabled
    Your conversations are saved and can be resumed anytime.

    Type your message to begin...
    Type 'exit/quit' to stop the conversation
    """

    return banner

@traceable(name="leadx agent flow")
def call_bot(user_mssg , username):
    response = bot.invoke({"messages":[HumanMessage(content=user_mssg)]} , 
                          config={"configurable":{"thread_id":username}})
    return response["messages"][-1].content


print(show_banner())
username = input("LeadX AI , enter your username ->  ").strip()
print(f"\n Restoring chat history for '{username}'...\n")

while True:
    user_mssg = input("you -> ").strip()
    if user_mssg.lower() == "quit" or user_mssg.lower() == "exit":
        break

    print("leadx -> " , call_bot(user_mssg,username))

    
    
