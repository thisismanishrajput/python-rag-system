# 🛍️ AI-Powered E-commerce Product Search (RAG System)

This is a Retrieval-Augmented Generation (RAG) based product search system using **Flask**, **ChromaDB**, **MongoDB**, and supports multi-agent LLMs including **OpenAI**, **Gemini**, and **HuggingFace**.

---

## 📁 Project Structure

python-rag/
│
├── app.py # Main Flask app
├── rag_utils.py # ChromaDB + MongoDB logic
├── requirements.txt # Python dependencies
├── .env # Environment variables (not committed)
├── .gitignore # Git exclusions
├── chroma_store/ # Persistent vector storage (ignored by git)
└── venv/ # Python virtual environment (ignored by git)


---

## 🚀 Features

- 🔍 Semantic product search using SentenceTransformer + ChromaDB  
- 🧠 Multi-agent LLM support: OpenAI GPT, Gemini 1.5 Flash, and HuggingFace (Qwen)  
- 🔄 Sync MongoDB to ChromaDB for vector search  
- 🛠️ Fallback keyword-based search (brand, name, tags) using MongoDB  
- 📦 Fast REST API using Flask  
- 🌍 CORS-enabled for frontend integration  

---

## ⚙️ Installation

### 1. Clone the repo

```bash
git clone https://github.com/your-username/python-rag.git
cd python-rag

```
2. Create and activate a virtual environment
bash
Copy
Edit
python3 -m venv venv
source venv/bin/activate
3. Install dependencies
bash
Copy
Edit
pip install -r requirements.txt
4. Setup .env file
Create a .env file in the root with your credentials:

env
Copy
Edit
MONGO_URI=mongodb://localhost:27017
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
HF_TOKEN=your_huggingface_token
🧠 Sync Products to ChromaDB
Before running search, make sure to vectorize your MongoDB products:

bash
Copy
Edit
curl -X POST http://localhost:5050/sync
🧪 Run the Server
bash
Copy
Edit
python app.py
Flask server will start on: http://localhost:5050

🔍 Sample AI Search Request
bash
Copy
Edit
curl --location 'http://localhost:5050/search' \
--header 'Content-Type: application/json' \
--data '{
  "query": "Do you have any nivea product?",
  "agent": "huggingface"
}'
✅ API Endpoints
Method	Endpoint	Description
POST	/search	Semantic + fallback product search
POST	/sync	Sync products from MongoDB to Chroma
GET	/test	Server health and agent test

🧠 Powered By
ChromaDB for vector search

SentenceTransformers (all-MiniLM-L6-v2) for embeddings

MongoDB for product storage

OpenAI, Gemini, and HuggingFace for LLM reasoning

🛑 .gitignore Notes
This project excludes:

.env

venv/

chroma_store/

.DS_Store, .vscode/, etc.

✨ Future Ideas
🧾 Upload CSV product data

🧩 Add authentication

🌐 Frontend UI with React or Flutter Web

yaml
Copy
Edit

---







