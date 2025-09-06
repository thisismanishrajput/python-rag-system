import os
from bson import ObjectId
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
from dotenv import load_dotenv
from chromadb import PersistentClient
from chromadb.config import Settings

# 🔐 Load environment variables
load_dotenv()

# 📦 MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["ecommerce-ai"]
product_collection = db["products"]

# 🧠 ChromaDB setup with persistence
chroma_client = PersistentClient(
    path="./chroma_store",
    settings=Settings()
)
collection = chroma_client.get_or_create_collection("products")

# 🧠 Embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# 🔄 Sync Mongo products to Chroma vector DB
def sync_products_to_chroma():
    print("🔄 Starting sync to ChromaDB...")
    
    # Clear existing data
    try:
        all_ids = collection.get()['ids']
        if all_ids:
            collection.delete(ids=all_ids)
            print(f"🗑️ Deleted {len(all_ids)} existing records")
    except Exception as e:
        print(f"⚠️ Error clearing collection: {e}")

    # Get all products from MongoDB
    products = list(product_collection.find())
    print(f"📦 Found {len(products)} products in MongoDB")
    
    if not products:
        print("❌ No products found in MongoDB!")
        return

    # Add products to ChromaDB
    for i, product in enumerate(products):
        try:
            # Create searchable text combining all relevant fields
            text_parts = [
                product.get('name', ''),
                product.get('description', ''),
                product.get('brand', ''),
                ' '.join(product.get('tags', [])),
                product.get('gender', ''),
                product.get('category', {}).get('name', '') if isinstance(product.get('category'), dict) else ''
            ]
            text = ' '.join(filter(None, text_parts))  # Remove empty strings
            
            print(f"📝 Product {i+1}: {product.get('name')} -> Text: {text[:100]}...")
            
            embedding = model.encode(text).tolist()
            collection.add(
                documents=[text],
                embeddings=[embedding],
                ids=[str(product['_id'])],
                metadatas=[{
                    "name": product.get('name', ''),
                    "brand": product.get('brand', ''),
                    "category": product.get('category', {}).get('name', '') if isinstance(product.get('category'), dict) else ''
                }]
            )
        except Exception as e:
            print(f"❌ Error adding product {product.get('name', 'Unknown')}: {e}")
    
    print("✅ Sync completed!")

# 🔎 Vector search with improved logic
def search_products(query, top_k=8, max_distance=1.5):  # Increased max_distance
    print(f"🔍 Searching for: '{query}'")
    
    try:
        # Check if collection has data
        collection_count = collection.count()
        print(f"📊 ChromaDB has {collection_count} products")
        
        if collection_count == 0:
            print("❌ ChromaDB is empty! Need to sync first.")
            return [], []
        
        embedding = model.encode(query).tolist()
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]  # ✅ Fixed: removed "ids"
        )

        print(f"🎯 ChromaDB returned {len(results.get('ids', [[]])[0])} results")

        if not results['ids'] or not results['ids'][0]:
            print("❌ No vector search results")
            return [], []

        # Process results with more lenient distance threshold
        hits_meta = []
        for i, _id in enumerate(results['ids'][0]):
            dist = results['distances'][0][i]
            doc = results.get('documents', [[]])[0][i] if results.get('documents') else ""
            
            print(f"🎯 Result {i+1}: ID={_id}, Distance={dist:.3f}, Doc='{doc[:50]}...'")
            
            if dist <= max_distance:  # More lenient threshold
                hits_meta.append({
                    "product_id": str(_id),
                    "distance": dist,
                    "document": doc
                })

        print(f"✅ Found {len(hits_meta)} products within distance threshold")

        if not hits_meta:
            print(f"❌ All results exceeded max_distance of {max_distance}")
            return [], []

        # Get products from MongoDB
        product_ids = [ObjectId(item["product_id"]) for item in hits_meta]
        mongo_docs = list(product_collection.find({
            "_id": { "$in": product_ids }
        }))

        print(f"📦 Retrieved {len(mongo_docs)} products from MongoDB")
        return mongo_docs, hits_meta

    except Exception as e:
        print(f"❌ Search error: {e}")
        import traceback
        traceback.print_exc()
        return [], []

# 🧪 Test function to debug search
def test_search(query="lip balm"):
    print(f"\n🧪 Testing search for: '{query}'")
    products, hits_meta = search_products(query)
    
    print(f"📊 Results: {len(products)} products found")
    for product in products:
        print(f"  - {product.get('name')} ({product.get('brand')})")
    
    return products, hits_meta

if __name__ == "__main__":
    # Test the search functionality
    print("🧪 Running test...")
    test_search("lip balm")
    test_search("skincare")
    test_search("car")