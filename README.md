# rag-chatbot 🤖🎙️📄

An advanced, full-stack **Retrieval-Augmented Generation (RAG)** chatbot that allows users to have context-aware conversations about their uploaded documents (PDFs and Word documents) with hybrid search capabilities, persistent chat history, and voice features (speech-to-text & text-to-speech).

Built using **FastAPI** for the backend, **Chainlit** for the interactive frontend, and **LangChain** with **FAISS & BM25** for hybrid retrieval.

---

## 🌟 Key Features

- **Hybrid Search RAG:** Combines vector embeddings (**FAISS**) and keyword search (**BM25**) for highly accurate document retrieval.
- **Voice Interactions:** 
  - **Speech-to-Text:** Record your queries directly using the microphone.
  - **Text-to-Speech (TTS):** The chatbot can read its responses out loud.
- **Session & History Persistence:** 
  - Save, resume, and manage past chat sessions.
  - SQLite database backend to store message logs and thread details.
- **Document Export:** Export and download your chat sessions as beautifully formatted PDF reports.
- **OpenAI-Compatible & Custom Models:** Support for any API-compliant models (Google Gemini, OpenAI, Ollama, etc.) via configurable endpoints.

---

## 🛠️ Tech Stack

- **Frontend:** [Chainlit](https://chainlit.io/) (Rich, web-based chat UI)
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous high-performance REST API)
- **Database:** SQLite (Message persistence and session storage)
- **AI/LLM Framework:** [LangChain](https://www.langchain.com/) (Chain building, agent orchestration, and embeddings)
- **Vector Store:** FAISS (Facebook AI Similarity Search)
- **Document Processing:** PyPDF & python-docx

---

## 📁 Repository Structure

```text
├── backend/
│   ├── database/          # SQLite connection and schema definitions
│   ├── routes/            # FastAPI routers (chat, upload, history, debug)
│   ├── services/          # RAG pipeline, hybrid search, PDF parsing/generation
│   ├── config.py          # Settings validation (Pydantic)
│   └── main.py            # FastAPI main entrypoint
├── frontend/
│   ├── api/               # API clients for communication with backend
│   ├── public/            # Styling (custom.css, custom.js) and assets
│   ├── utils/             # Helper utilities (speech processing, TTS)
│   └── app.py             # Chainlit main app file
├── requirements.txt       # Project dependencies
└── README.md              # Project documentation
```

---

## 🚀 Getting Started

Follow these instructions to set up the project locally:

### 1. Prerequisites
- Python 3.9 or higher installed.

### 2. Clone the Repository
```bash
git clone https://github.com/ritika-291/rag-chatbot.git
cd rag-chatbot
```

### 3. Setup Virtual Environment
```bash
# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (cmd/PowerShell):
.\venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Create a `.env` file in the root directory:
```env
# LLM Configurations
LLM_API_KEY=your_openai_or_gemini_api_key
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL_NAME=gpt-4o-mini
LLM_URL=https://api.openai.com/v1 # or custom endpoint if using Ollama/Gemini

# Processing Configs (Optional overrides)
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### 6. Run the Application

You need to run both the backend server and the frontend client simultaneously.

#### Start the FastAPI Backend:
```bash
uvicorn backend.main:app --reload --reload-dir backend --port 8001
```

#### Start the Chainlit Frontend:
In a new terminal window (with virtual environment activated):
```bash
cd frontend
chainlit run app.py
```
The app will open automatically in your browser (usually at `http://localhost:8000`).

---

## 🔒 License
This project is licensed under the MIT License.
