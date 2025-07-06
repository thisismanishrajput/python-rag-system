# 🛍️ AI-Powered E-commerce Product Search (RAG System)

A Retrieval-Augmented Generation (RAG) based product search system using **Flask**, **ChromaDB**, **MongoDB**, and supports multi-agent LLMs including **OpenAI**, **Gemini**, and **HuggingFace**.

## 📁 Project Structure

```
python-rag/
│
├── app.py                 # Main Flask app
├── rag_utils.py          # ChromaDB + MongoDB logic
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (not committed)
├── .gitignore           # Git exclusions
├── chroma_store/        # Persistent vector storage (ignored by git)
└── venv/               # Python virtual environment (ignored by git)
```

## 🚀 Features

- 🔍 **Semantic product search** using SentenceTransformer + ChromaDB
- 🧠 **Multi-agent LLM support**: OpenAI GPT, Gemini 1.5 Flash, and HuggingFace (Qwen)
- 🔄 **Sync MongoDB to ChromaDB** for vector search
- 🛠️ **Fallback keyword-based search** (brand, name, tags) using MongoDB
- 📦 **Fast REST API** using Flask
- 🌍 **CORS-enabled** for frontend integration

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/python-rag.git
cd python-rag
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup environment variables

Create a `.env` file in the root directory with your credentials:

```env
MONGO_URI=mongodb://localhost:27017
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
HF_TOKEN=your_huggingface_token
```

## 🧠 Sync Products to ChromaDB

Before running search, make sure to vectorize your MongoDB products:

```bash
curl -X POST http://localhost:5050/sync
```

## 🧪 Run the Server

```bash
python app.py
```

Flask server will start on: `http://localhost:5050`

## 🔍 Sample AI Search Request

```bash
curl --location 'http://localhost:5050/search' \
--header 'Content-Type: application/json' \
--data '{
  "query": "Do you have any nivea product?",
  "agent": "huggingface"
}'
```

## ✅ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search` | Semantic + fallback product search |
| `POST` | `/sync` | Sync products from MongoDB to Chroma |
| `GET` | `/test` | Server health and agent test |

## 🛠️ Tech Stack

- **ChromaDB** - Vector database for semantic search
- **SentenceTransformers** - Text embeddings (all-MiniLM-L6-v2)
- **MongoDB** - Product data storage
- **Flask** - Web framework
- **OpenAI GPT** - Language model for intelligent responses
- **Gemini 1.5 Flash** - Google's LLM integration
- **HuggingFace** - Open-source LLM support (Qwen)

## 🛑 .gitignore

This project excludes:
- `.env` - Environment variables
- `venv/` - Virtual environment
- `chroma_store/` - Vector database storage
- `.DS_Store`, `.vscode/`, etc. - IDE and system files

## 🚀 Usage Examples

### Search with OpenAI

```bash
curl -X POST http://localhost:5050/search \
-H "Content-Type: application/json" \
-d '{
  "query": "I need a moisturizer for dry skin",
  "agent": "openai"
}'
```

### Search with Gemini

```bash
curl -X POST http://localhost:5050/search \
-H "Content-Type: application/json" \
-d '{
  "query": "Show me organic skincare products",
  "agent": "gemini"
}'
```

### Health Check

```bash
curl http://localhost:5050/test
```

## 📦 Dependencies

Key packages in `requirements.txt`:
- `flask` - Web framework
- `chromadb` - Vector database
- `pymongo` - MongoDB driver
- `sentence-transformers` - Text embeddings
- `openai` - OpenAI API client
- `google-generativeai` - Gemini API client
- `transformers` - HuggingFace transformers
- `flask-cors` - CORS support

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MONGO_URI` | MongoDB connection string | ✅ |
| `OPENAI_API_KEY` | OpenAI API key | ⚠️ (if using OpenAI) |
| `GEMINI_API_KEY` | Google Gemini API key | ⚠️ (if using Gemini) |
| `HF_TOKEN` | HuggingFace API token | ⚠️ (if using HuggingFace) |

### Supported LLM Agents

- `openai` - OpenAI GPT models
- `gemini` - Google Gemini 1.5 Flash
- `huggingface` - HuggingFace models (Qwen)

## 🏗️ Architecture

```
User Query → Flask API → ChromaDB (Vector Search) → MongoDB (Fallback) → LLM Agent → Response
```

1. **Vector Search**: Query is embedded and searched in ChromaDB
2. **Fallback Search**: If no vector results, performs keyword search in MongoDB
3. **LLM Processing**: Results are processed by selected LLM agent
4. **Response**: Formatted response returned to user

## 📊 Performance

- **Vector Search**: Sub-second response times
- **Fallback Search**: MongoDB indexing for fast keyword matching
- **Concurrent Requests**: Flask handles multiple simultaneous searches
- **Memory Efficient**: ChromaDB persistent storage

## 🔮 Future Enhancements

- 🧾 **CSV Upload**: Bulk product import functionality
- 🔐 **Authentication**: User management and API keys
- 🌐 **Frontend UI**: React or Flutter web interface
- 📊 **Analytics**: Search analytics and product insights
- 🚀 **Caching**: Redis integration for faster responses
- 📱 **Mobile API**: React Native or Flutter mobile app support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, please open an issue on GitHub or contact the maintainers.

---

⭐ **Star this repo** if you find it helpful!
