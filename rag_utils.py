import os
from bson import ObjectId
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
from dotenv import load_dotenv
from chromadb import PersistentClient  # ✅ Use PersistentClient
from chromadb.config import Settings
import google.generativeai as genai  # ✅ Gemini SDK

# 🔐 Load environment variables
load_dotenv()

# 📦 MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["ecommerce-ai"]
product_collection = db["products"]

# 🧠 ChromaDB setup with persistence
chroma_client = PersistentClient(
    path="./chroma_store",  # 💾 This ensures vector DB is stored on disk
    settings=Settings()
)
collection = chroma_client.get_or_create_collection("products")

# 🧠 Embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# 🛠 Debug helper
def debug_chroma_docs():
    data = collection.get()
    print(f"📦 Chroma has {len(data['documents'])} documents.")
    print("🆔 Document IDs:", data['ids'])

    print("\n🤖 Available Gemini Models:")
    for model in genai.list_models():
        print("•", model.name)

# 🔄 Sync Mongo products to Chroma vector DB
def sync_products_to_chroma():
    all_ids = collection.get()['ids']
    if all_ids:
        collection.delete(ids=all_ids)
        print(f"🧹 Deleted {len(all_ids)} old documents from Chroma")

    products = list(product_collection.find())
    print(f"🛒 Fetched {len(products)} products from MongoDB")

    for product in products:
        print(f"📦 Syncing product: {product['name']}")
        text = f"{product['name']} {product.get('description', '')} {product.get('brand', '')} {' '.join(product.get('tags', []))}"
        embedding = model.encode(text).tolist()
        collection.add(
            documents=[text],
            embeddings=[embedding],
            ids=[str(product['_id'])]
        )

    debug_chroma_docs()  # ✅ Optional, useful for monitoring

def search_products(query, top_k=5, max_distance=1.0):
    embedding = model.encode(query).tolist()
    results = collection.query(query_embeddings=[embedding], n_results=top_k)

    if not results['ids'] or not results['ids'][0]:
        return []

    # ✅ Filter by distance threshold
    filtered_ids = [
        results['ids'][0][i]
        for i, dist in enumerate(results['distances'][0])
        if dist <= max_distance
    ]

    if not filtered_ids:
        return []

    return list(product_collection.find({
        "_id": { "$in": [ObjectId(id) for id in filtered_ids] }
    }))
