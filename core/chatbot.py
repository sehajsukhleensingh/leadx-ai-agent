from langgraph.graph import StateGraph , START , END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import InMemorySaver

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage , HumanMessage , AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEndpointEmbeddings

from langsmith import traceable

from utils.helper import Utility
from schema_models.lead_validator import Lead , IntentOutput

from dotenv import load_dotenv
from typing import TypedDict , Annotated , Optional , Literal
import os 
import sqlite3

load_dotenv()

class BotState(TypedDict):
    """State schema for the conversational workflow.
    
    Holds all conversation state across the agent lifecycle. Tracks message history,
    classified intent, collected lead info, and validation status.
    """
    messages : Annotated[list[BaseMessage],add_messages]

    intent : Optional[Literal["GREETING","INQUIRY","HIGH_INTENT"]]
    context : Optional[str]

    lead_state :Optional[str]

    name : Optional[str]
    email : Optional[str]
    platform : Optional[str]

    lead_storage : Optional[bool]

    valid_data : Optional[bool]

class leadx:
    """Core conversational AI agent for lead generation and support.
    
    Orchestrates the entire conversation flow: classifying intents, retrieving knowledge,
    collecting lead data, and validating information.
    """

    @traceable(name="constructor to setup llm and embedder")
    def __init__(self):
        """Initialize the LLM and embedding models.
        
        Sets up the Gemini LLM instance and HuggingFace embeddings for vector operations.
        Called once when the agent is instantiated.
        """
        self.embedder =  HuggingFaceEndpointEmbeddings(
                model = "BAAI/bge-base-en-v1.5" , 
                huggingfacehub_api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
            )
        self.llm = ChatGoogleGenerativeAI(model = "gemini-2.5-flash-lite" , 
                             temperature = 0.2)

    @traceable(name="intent classifier node")
    def intent_classifer(self, state : BotState) -> Literal["GREETING","INQUIRY","HIGH_INTENT"]:
        """Classify user intent from the latest message.
        
        Input: Current conversation state with the user's latest message.
        Output: Dict with intent field set to GREETING, INQUIRY, or HIGH_INTENT.
        
        Determines if user is greeting, asking about services, or showing purchase intent.
        """
        structured_llm = self.llm.with_structured_output(IntentOutput)
        user_query = state["messages"][-1].content

        prompt = PromptTemplate(template = Utility.fetch_prompt("prompts/intent_classification.md") ,
                                input_variables= ["user_input"])
        
        chain = prompt | structured_llm

        try : 
            res = chain.invoke({"user_input":user_query})
            output = res.intent
            return {"intent":output}
        
        except Exception as e:
            print(f"some error occured {e}")
            return {"messages":"GREETING"}


    @traceable(name="intent router")
    def router(self, state : BotState) -> Literal["chat_node","rag_node","lead_collection_node"]:
        """Route to appropriate handler based on intent and lead collection state.
        
        Input: Current state with classified intent and lead_state.
        Output: String node name - either 'chat_node', 'rag_node', or 'lead_collection_node'.
        
        Routes to lead collection if data is incomplete, otherwise routes based on intent.
        """
        if state.get("lead_state") and state.get("lead_state") != "complete":
            return "lead_collection_node"
        
        intent = state.get("intent").upper().strip()
        
        if intent == "HIGH_INTENT":
            return "lead_collection_node"
        
        elif intent == "INQUIRY":
            return "rag_node"
        
        elif intent == "GREETING":
            return "chat_node"

        else:
            print("error in router input")

    @traceable(name="chat node")
    def chat_func(self, state : BotState) -> BotState:
        """Handle general conversation without knowledge base context.
        
        Input: State with full message history for a greeting/general query.
        Output: Updated state with LLM-generated response added to messages.
        
        Used for casual greetings and conversations outside product scope.
        """
        usr_message = state["messages"]

        output = self.llm.invoke(usr_message)
        return {"messages":[output]}


    @traceable(name="rag node")
    def rag_func(self, state : BotState) -> BotState:
        """Retrieve relevant knowledge and generate contextual response.
        
        Input: State with user query about product/services.
        Output: Updated state with knowledge-augmented response and retrieved context.
        
        Loads cached vector store, finds similar docs, and generates answer with context.
        """
        user_query = state["messages"][-1].content

        PATH_VDB = "database/vectordb"
        if not os.path.exists(PATH_VDB):
            vector_store = Utility.create_vector_store()
        
        else:
            vector_store = FAISS.load_local(
                PATH_VDB , 
                self.embedder , 
                allow_dangerous_deserialization=True
            )
        prompt = PromptTemplate(template = Utility.fetch_prompt("prompts/rag_based_query.md") ,
                                input_variables=["context","user_query"])
        
        retriver = vector_store.as_retriever(search_type = "similarity" , kwargs=5)
        retrieved_docs = retriver.invoke(user_query)

        contextual_data = '\n'.join(text.page_content for text in retrieved_docs)

        chain = prompt | self.llm

        output = chain.invoke({"context":contextual_data,"user_query":user_query})
        
        return {"messages":[output],"context":contextual_data}


    @traceable(name="lead collection node")
    def lead_collection_func(self, state : BotState) -> BotState:
        """Progressively collect lead information through multi-turn conversation.
        
        Input: State with optional name, email, platform fields and lead_state stage.
        Output: Updated state with collected data and next stage (name -> email -> platform -> complete).
        
        Asks for missing info step-by-step. Completes when all three fields are filled.
        """
        stage = state.get("lead_state")
        name = state.get("name")
        email = state.get("email")
        platform = state.get("platform")

        last_mssg = state["messages"][-1].content.strip()

        if stage == "name":
            name = last_mssg
        elif stage == "mail":
            email = last_mssg
        elif stage == "platform":
            platform = last_mssg

        if not name:
            stage = "name"
            return {"messages":[AIMessage(content="what's your name ?")] , 
                    "lead_state":stage}
        
        if not email:
            stage = "mail"
            return {"name":name,
                    "messages":[AIMessage(content="please enter your email.")] , 
                    "lead_state":stage}
        
        if not platform:
            stage = "platform"
            return {"name":name , 
                    "email":email,
                    "messages":[AIMessage(content="Enter the platform name for which you want to create content on.")] ,
                    "lead_state":stage}
        
    
        return {"messages":[AIMessage(content="Thanks! Processing your details...")] ,
                "lead_state":"complete",
                "name":name,
                "email":email,
                "platform":platform, 
                "lead_storage":True}

    def lead_router(self , state : BotState) -> BotState:
        """Route to validation after all lead data is collected.
        
        Input: State after lead_collection_func with lead_storage flag.
        Output: String node name - 'validation_node' or '__end__'.
        
        Decides whether to validate the collected data or exit the lead flow.
        """
        if state.get("lead_storage"):
            return "validation_node"
        return "__end__"
    
    @traceable(name="data validator name")
    def validate_data(self, state : BotState) -> BotState:
        """Validate lead data and handle validation errors.
        
        Input: State with name, email, and platform fields to validate.
        Output: Updated state with valid_data flag and error messages if validation fails.
        
        Uses Lead model to validate each field. Returns error message if any field is invalid.
        """
        try:
            lead = Lead(
                name=state.get("name") , 
                email=state.get("email") , 
                platform=state.get("platform")
            )
            return {"messages":[] , 
                    "valid_data":True}
            
        except Exception as e:
            
            error = str(e).lower()

            if "email" in error:
                return{
                    "email":None,
                    "lead_state":"mail" , 
                    "messages":[AIMessage(content="Invalid email , please enter again")],
                    "valid_data": False
                }
            
            elif "platform" in error:
                return {
                    "platform": None,
                    "lead_stage": "platform",
                    "messages": [AIMessage(content="Invalid platform. Choose YouTube, Instagram, or TikTok.")],
                    "valid_data": False  }

            else:
                return {
                    "name": None,
                    "lead_stage": "name",
                    "messages": [AIMessage(content="Invalid name. Please enter your name again.")],
                    "valid_data": False
                }

    @traceable(name="tool node")        
    def tool_node(self, state: BotState) ->BotState:
        """Save validated lead data to storage.
        
        Input: State with valid_data flag and lead information (name, email, platform).
        Output: State with success or failure message.
        
        Calls mock_lead_capture to save the lead. Handles invalid data gracefully.
        """
        if state.get("valid_data", False):
            name = state.get("name")
            email = state.get("email")
            platform = state.get("platform")

            Utility.mock_lead_capture(name=name, email=email, platform=platform)
            return{"messages":[AIMessage(content="Lead captured succcessfully , Our team will reach out to you soon")]}
        
        else:
            return{"messages":[AIMessage(content="something is wrong , missing details")]}


agent = leadx()

workflow = StateGraph(BotState)
PATH_CONVOS = "database/convos/data.db"
conn = sqlite3.connect(PATH_CONVOS , check_same_thread = False)
checkpointer = SqliteSaver(conn=conn)

workflow.add_node("intent_classifier_node",agent.intent_classifer)
workflow.add_node("chat_node",agent.chat_func)
workflow.add_node("rag_node",agent.rag_func)
workflow.add_node("lead_collection_node",agent.lead_collection_func)
workflow.add_node("validation_node",agent.validate_data)
workflow.add_node("tool_node", agent.tool_node)

workflow.add_edge(START,"intent_classifier_node")
workflow.add_conditional_edges("intent_classifier_node",agent.router,{"chat_node":"chat_node","rag_node": "rag_node", "lead_collection_node": "lead_collection_node"})
workflow.add_edge("chat_node",END)
workflow.add_edge("rag_node",END)
workflow.add_conditional_edges("lead_collection_node",agent.lead_router ,  {"validation_node":"validation_node", "__end__":END})
workflow.add_edge("validation_node","tool_node")
workflow.add_edge("tool_node",END)

bot = workflow.compile(checkpointer=checkpointer) 