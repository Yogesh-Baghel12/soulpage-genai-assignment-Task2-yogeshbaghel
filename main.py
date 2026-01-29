
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.tools.tavily_search import TavilySearchResults
import os
from datetime import datetime
import uuid

# ---------------- CUSTOM CSS FOR BETTER UI ----------------
def inject_custom_css():
    st.markdown(
        """
        <style>
        /* Main background */
        .stApp {
            background: linear-gradient(135deg, #f8fafc 0%, #e0e7ef 100%);
        }
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background: #1e293b;
            color: #f1f5f9;
        }
        /* Chat message bubbles */
        .stChatMessage.user {
            background: #f1f5f9;
            border-radius: 16px 16px 4px 16px;
            margin-bottom: 8px;
            padding: 12px 18px;
            color: #334155;
            border: 1px solid #cbd5e1;
        }
        .stChatMessage.assistant {
            background: #e0e7ef;
            border-radius: 16px 16px 16px 4px;
            margin-bottom: 8px;
            padding: 12px 18px;
            color: #0f172a;
            border: 1px solid #cbd5e1;
        }
        /* Chat input box */
        textarea, .stTextInput > div > input {
            background: #f8fafc;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
            color: #334155;
        }
        /* Buttons */
        button[kind="primary"] {
            background: linear-gradient(90deg, #6366f1 0%, #0ea5e9 100%);
            color: #fff;
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }
        button[kind="secondary"] {
            background: #334155;
            color: #f1f5f9;
            border-radius: 8px;
        }
        /* Chat title */
        .chat-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #2563eb;
            margin-bottom: 0.5rem;
        }
        /* Chat subtitle */
        .chat-subtitle {
            color: #64748b;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }
        /* Divider */
        .stDivider {
            border-top: 1px solid #cbd5e1;
            margin: 1rem 0;
        }
        /* Chat history list */
        .stSidebar .element-container {
            margin-bottom: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

load_dotenv()

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="AI Chat Assistant",
    page_icon="💬",
    layout="wide"
)

# ---------------- INITIALIZE SESSION STATE ----------------
if "chats" not in st.session_state:
    st.session_state.chats = {}

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None

if "chat_list" not in st.session_state:
    st.session_state.chat_list = []

# ---------------- LLM ----------------
@st.cache_resource
def get_llm():
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.5
    )

llm = get_llm()

# ---------------- WEB SEARCH TOOL ----------------
@st.cache_resource
def get_search_tool():
    return TavilySearchResults(
        max_results=3,
        tavily_api_key=os.getenv("TAVILY_KEY")
    )

search_tool = get_search_tool()

# ---------------- HELPER FUNCTIONS ----------------
def should_use_search(query: str) -> bool:
    """Determine if web search should be used based on query"""
    search_keywords = [
        'current', 'latest', 'today', 'recent', 'now', 'this year',
        'who is the', 'what is the current', 'latest news',
        '2024', '2025', '2026', 'updates'
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in search_keywords)

def perform_search(query: str) -> str:
    """Perform web search and return formatted results"""
    try:
        results = search_tool.invoke(query)
        if results:
            search_context = "\n\nWeb Search Results:\n"
            for i, result in enumerate(results, 1):
                search_context += f"\n{i}. {result.get('content', '')}\n"
                if 'url' in result:
                    search_context += f"   Source: {result['url']}\n"
            return search_context
        return ""
    except Exception as e:
        st.warning(f"Search failed: {str(e)}")
        return ""

def get_session_history(session_id: str):
    """Get or create chat history for a session"""
    if session_id not in st.session_state.chats:
        st.session_state.chats[session_id] = {
            "history": ChatMessageHistory(),
            "messages": [],
            "title": "New Chat",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    return st.session_state.chats[session_id]["history"]

def create_new_chat():
    """Create a new chat session"""
    chat_id = str(uuid.uuid4())
    st.session_state.current_chat_id = chat_id
    st.session_state.chats[chat_id] = {
        "history": ChatMessageHistory(),
        "messages": [],
        "title": "New Chat",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if chat_id not in st.session_state.chat_list:
        st.session_state.chat_list.insert(0, chat_id)
    return chat_id

def update_chat_title(chat_id, first_message):
    """Update chat title based on first message"""
    if st.session_state.chats[chat_id]["title"] == "New Chat":
        title = first_message[:50] + "..." if len(first_message) > 50 else first_message
        st.session_state.chats[chat_id]["title"] = title

def delete_chat(chat_id):
    """Delete a chat session"""
    if chat_id in st.session_state.chats:
        del st.session_state.chats[chat_id]
    if chat_id in st.session_state.chat_list:
        st.session_state.chat_list.remove(chat_id)
    
    if st.session_state.current_chat_id == chat_id:
        if st.session_state.chat_list:
            st.session_state.current_chat_id = st.session_state.chat_list[0]
        else:
            create_new_chat()

def get_ai_response(user_input: str, session_id: str) -> str:
    """Get AI response with optional web search"""
    try:
        # Get chat history
        history = get_session_history(session_id)
        
        # Build messages list
        messages = []
        
        # Add system message
        system_prompt = """You are a conversational AI assistant with memory.

Conversation understanding:
- Use previous messages only when they are relevant to the current question.
- Resolve references like "he", "she", "they", "this", "that" using recent context.
- If a new person/entity is introduced, update your reference.

Memory usage:
- Use conversation history when it helps answer the current question.
- Don't force old context into unrelated questions.
- Treat user-provided personal details as authoritative.

Response style:
- Be conversational and natural
- Provide clear, concise answers
- Ask for clarification when needed"""

        messages.append({"role": "system", "content": system_prompt})
        
        # Add chat history
        for msg in history.messages[-8:]:  # Last 8 messages for context
            if hasattr(msg, 'type'):
                if msg.type == 'human':
                    messages.append({"role": "user", "content": msg.content})
                elif msg.type == 'ai':
                    messages.append({"role": "assistant", "content": msg.content})
        
        # Check if we need web search
        search_context = ""
        if should_use_search(user_input):
            with st.spinner("🔍 Searching the web..."):
                search_context = perform_search(user_input)
        
        # Add current user message with optional search context
        current_input = user_input
        if search_context:
            current_input = f"{user_input}\n{search_context}"
        
        messages.append({"role": "user", "content": current_input})
        
        # Get response from LLM
        response = llm.invoke(messages)
        
        # Update history
        history.add_user_message(user_input)
        history.add_ai_message(response.content)
        
        return response.content
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        st.error(error_msg)
        return f"I apologize, but I encountered an error. Please try again or start a new chat."

# ---------------- STREAMLIT UI ----------------

def main():
    inject_custom_css()
    # Ensure we have at least one chat
    if not st.session_state.current_chat_id:
        create_new_chat()

    # Sidebar for chat history
    with st.sidebar:
        st.markdown("<div style='text-align:center; margin-bottom:1.5rem;'><span style='font-size:2rem;'>💬</span><br><span style='font-size:1.3rem; font-weight:700;'>Chat History</span></div>", unsafe_allow_html=True)

        # New Chat Button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            create_new_chat()
            st.rerun()

        st.markdown('<div class="stDivider"></div>', unsafe_allow_html=True)

        # Display chat list
        if st.session_state.chat_list:
            for chat_id in st.session_state.chat_list:
                chat_data = st.session_state.chats[chat_id]

                col1, col2 = st.columns([5, 1])

                with col1:
                    # Chat button
                    is_current = chat_id == st.session_state.current_chat_id
                    button_type = "primary" if is_current else "secondary"

                    if st.button(
                        f"💭 {chat_data['title']}",
                        key=f"chat_{chat_id}",
                        use_container_width=True,
                        type=button_type
                    ):
                        st.session_state.current_chat_id = chat_id
                        st.rerun()

                with col2:
                    # Delete button
                    if st.button("🗑️", key=f"del_{chat_id}"):
                        delete_chat(chat_id)
                        st.rerun()

                # Show creation time for current chat
                if is_current:
                    st.caption(f"🕒 <span style='color:#a5b4fc;'>{chat_data['created_at']}</span>", unsafe_allow_html=True)
        else:
            st.info("No chats yet. Start a new conversation!")

        # Instructions
        st.markdown('<div class="stDivider"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div style='margin-top:1rem; color:#a5b4fc; font-size:1.1rem;'><b>💡 Tips:</b></div>
        <ul style='color:#cbd5e1; font-size:1rem; margin-top:0.5rem;'>
            <li>Use <b>'current', 'latest', 'today'</b> for web search</li>
            <li>Each chat has independent memory</li>
            <li>Switch chats to restore context</li>
        </ul>
        """, unsafe_allow_html=True)

    # Main chat area
    current_chat = st.session_state.chats[st.session_state.current_chat_id]

    st.markdown("<div class='chat-title'>🤖 AI Chat Assistant</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='chat-subtitle'>Chat: <b>{current_chat['title']}</b></div>", unsafe_allow_html=True)

    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for message in current_chat["messages"]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    # Chat input
    prompt_input = st.chat_input("Type your message here...")
    if prompt_input:
        # Update chat title if this is the first message
        if len(current_chat["messages"]) == 0:
            update_chat_title(st.session_state.current_chat_id, prompt_input)

        # Add user message to chat
        current_chat["messages"].append({"role": "user", "content": prompt_input})

        # Display user message
        with st.chat_message("user"):
            st.write(prompt_input)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                assistant_response = get_ai_response(
                    prompt_input,
                    st.session_state.current_chat_id
                )
                st.write(assistant_response)

        # Add assistant response to chat
        current_chat["messages"].append({"role": "assistant", "content": assistant_response})

        # Rerun to update the UI
        st.rerun()

if __name__ == "__main__":
    main()