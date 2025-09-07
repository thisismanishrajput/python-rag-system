import os
import re
import math
from bson import ObjectId
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
from dotenv import load_dotenv
from chromadb import PersistentClient
from chromadb.config import Settings
from typing import List, Dict, Tuple, Optional, Any

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

# 🎯 Field weights for better search relevance
FIELD_WEIGHTS = {
    'name': 4.0,
    'brand': 3.0,
    'description': 2.5,
    'tags': 2.0,
    'category': 1.5,
    'gender': 1.0,
    'price': 0.5
}

def preprocess_text(text: str) -> str:
    """Clean and preprocess text for better search"""
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters but keep spaces and alphanumeric
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_field_value(product: Dict, field: str) -> str:
    """Extract and clean field value from product"""
    if field == 'category':
        category = product.get('category', {})
        if isinstance(category, dict):
            return category.get('name', '')
        return str(category) if category else ''
    
    value = product.get(field, '')
    if isinstance(value, list):
        return ' '.join(str(item) for item in value)
    
    return str(value) if value else ''

def create_searchable_text(product: Dict) -> str:
    """Create weighted, cleaned searchable text for better embeddings"""
    text_parts = []
    
    for field, weight in FIELD_WEIGHTS.items():
        value = extract_field_value(product, field)
        if value:
            # Clean the value
            cleaned_value = preprocess_text(value)
            if cleaned_value:
                # Repeat based on weight (rounded to nearest integer)
                repeat_count = max(1, int(weight))
                text_parts.extend([cleaned_value] * repeat_count)
    
    return ' '.join(text_parts)

def extract_metadata(product: Dict) -> Dict:
    """Extract metadata for ChromaDB"""
    return {
        "name": product.get('name', ''),
        "brand": product.get('brand', ''),
        "category": extract_field_value(product, 'category'),
        "gender": product.get('gender', ''),
        "price": product.get('price', 0),
        "tags": '|'.join(product.get('tags', [])),
        "in_stock": product.get('in_stock', True)
    }

def calculate_relevance_score(distance: float, metadata: Dict, query: str, filters: Dict = None) -> float:
    """Calculate relevance score combining distance and metadata"""
    # Base score from distance (lower distance = higher score)
    base_score = max(0, 1 - distance)
    
    # Boost score based on metadata matches
    boost = 0.0
    
    # Query-based boosts
    query_lower = query.lower()
    
    # Name match boost
    if query_lower in metadata.get('name', '').lower():
        boost += 0.3
    
    # Brand match boost
    if query_lower in metadata.get('brand', '').lower():
        boost += 0.2
    
    # Category match boost
    if query_lower in metadata.get('category', '').lower():
        boost += 0.15
    
    # Filter-based boosts
    if filters:
        if filters.get('brand') and filters['brand'].lower() in metadata.get('brand', '').lower():
            boost += 0.2
        if filters.get('category') and filters['category'].lower() in metadata.get('category', '').lower():
            boost += 0.2
    
    # In-stock boost
    if metadata.get('in_stock', True):
        boost += 0.1
    
    return min(1.0, base_score + boost)

def preprocess_query(query: str) -> str:
    """Preprocess user query for better search"""
    return preprocess_text(query)

# 🔄 Full sync (for initial setup or complete refresh)
def sync_products_to_chroma():
    """Sync all products from MongoDB to ChromaDB"""
    print("🔄 Starting full sync to ChromaDB...")
    
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

    # Process products in batches for better performance
    batch_size = 100
    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        process_product_batch(batch, i + 1)
    
    print("✅ Full sync completed!")

def process_product_batch(products: List[Dict], start_index: int):
    """Process a batch of products for ChromaDB"""
    documents = []
    embeddings = []
    ids = []
    metadatas = []
    
    for product in products:
        try:
            # Create optimized searchable text
            text = create_searchable_text(product)
            if not text.strip():
                continue
            
            # Generate embedding
            embedding = model.encode(text).tolist()
            
            # Prepare data for batch insert
            documents.append(text)
            embeddings.append(embedding)
            ids.append(str(product['_id']))
            metadatas.append(extract_metadata(product))
            
        except Exception as e:
            print(f"❌ Error processing product {product.get('name', 'Unknown')}: {e}")
    
    # Batch insert to ChromaDB
    if documents:
        collection.add(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        print(f"📝 Processed batch {start_index}-{start_index + len(products) - 1}: {len(documents)} products")

# 🔄 Incremental sync (for single product updates)
def sync_single_product(product_id: str) -> bool:
    """Sync a single product to ChromaDB"""
    try:
        product = product_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            print(f"❌ Product {product_id} not found in MongoDB")
            return False
        
        # Create optimized text and metadata
        text = create_searchable_text(product)
        if not text.strip():
            print(f"❌ Product {product_id} has no searchable content")
            return False
        
        embedding = model.encode(text).tolist()
        metadata = extract_metadata(product)
        
        # Upsert to ChromaDB
        collection.upsert(
            ids=[str(product_id)],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata]
        )
        
        print(f"✅ Synced product: {product.get('name', 'Unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Error syncing product {product_id}: {e}")
        return False

def delete_product_from_chroma(product_id: str) -> bool:
    """Delete a product from ChromaDB"""
    try:
        collection.delete(ids=[str(product_id)])
        print(f"✅ Deleted product {product_id} from ChromaDB")
        return True
    except Exception as e:
        print(f"❌ Error deleting product {product_id}: {e}")
        return False

# 🔎 Enhanced vector search with better ranking and filtering
def search_products_improved(
    query: str, 
    top_k: int = 8, 
    page: int = 1, 
    limit: int = 10,
    filters: Dict = None,
    max_distance: float = 1.2
) -> Tuple[List[Dict], List[Dict], int]:
    """Enhanced search with pagination, filtering, and better ranking"""
    print(f"🔍 Searching for: '{query}' (page {page}, limit {limit})")
    
    try:
        # Check if collection has data
        collection_count = collection.count()
        print(f"📊 ChromaDB has {collection_count} products")
        
        if collection_count == 0:
            print("❌ ChromaDB is empty! Need to sync first.")
            return [], [], 0
        
        # Preprocess query
        processed_query = preprocess_query(query)
        embedding = model.encode(processed_query).tolist()
        
        # Build metadata filter for ChromaDB
        where_clause = {}
        if filters:
            if filters.get('brand'):
                where_clause['brand'] = {"$eq": filters['brand']}
            if filters.get('category'):
                where_clause['category'] = {"$eq": filters['category']}
            if filters.get('gender'):
                where_clause['gender'] = {"$eq": filters['gender']}
            if filters.get('in_stock') is not None:
                where_clause['in_stock'] = {"$eq": filters['in_stock']}
        
        # Search with more results for better ranking
        search_limit = min(top_k * 3, 50)  # Get more results for ranking
        results = collection.query(
            query_embeddings=[embedding],
            n_results=search_limit,
            where=where_clause if where_clause else None,
            include=["documents", "distances", "metadatas"]
        )

        print(f"🎯 ChromaDB returned {len(results.get('ids', [[]])[0])} results")

        if not results['ids'] or not results['ids'][0]:
            print("❌ No vector search results")
            return [], [], 0

        # Rank results by relevance score
        ranked_results = []
        for i, _id in enumerate(results['ids'][0]):
            distance = results['distances'][0][i]
            metadata = results['metadatas'][0][i]
            document = results.get('documents', [[]])[0][i] if results.get('documents') else ""
            
            # Skip if distance is too high
            if distance > max_distance:
                continue
            
            # Calculate relevance score
            relevance_score = calculate_relevance_score(distance, metadata, query, filters)
            
            ranked_results.append({
                "product_id": str(_id),
                "distance": distance,
                "relevance_score": relevance_score,
                "document": document,
                "metadata": metadata
            })

        # Sort by relevance score (higher is better)
        ranked_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        print(f"✅ Found {len(ranked_results)} products after ranking")

        if not ranked_results:
            print(f"❌ No products within distance threshold of {max_distance}")
            return [], [], 0

        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_results = ranked_results[start_idx:end_idx]
        
        # Get products from MongoDB
        if paginated_results:
            product_ids = [ObjectId(item["product_id"]) for item in paginated_results]
            mongo_docs = list(product_collection.find({
                "_id": {"$in": product_ids}
            }))
            
            # Sort MongoDB results to match ChromaDB order
            id_to_doc = {str(doc['_id']): doc for doc in mongo_docs}
            ordered_docs = [id_to_doc[item["product_id"]] for item in paginated_results if item["product_id"] in id_to_doc]
            
            print(f"📦 Retrieved {len(ordered_docs)} products from MongoDB")
            return ordered_docs, paginated_results, len(ranked_results)
        
        return [], [], 0

    except Exception as e:
        print(f"❌ Search error: {e}")
        import traceback
        traceback.print_exc()
        return [], [], 0

# 🔎 Legacy search function (for backward compatibility)
def search_products(query: str, top_k: int = 8, max_distance: float = 1.5) -> Tuple[List[Dict], List[Dict]]:
    """Legacy search function for backward compatibility"""
    products, hits_meta, _ = search_products_improved(query, top_k, 1, top_k, None, max_distance)
    return products, hits_meta

# 🔎 Fallback search using MongoDB
def fallback_search(query: str, filters: Dict = None, page: int = 1, limit: int = 10) -> Tuple[List[Dict], int]:
    """Fallback search using MongoDB keyword search"""
    print(f"🔄 Trying MongoDB fallback search for: '{query}'")
    
    try:
        # Build MongoDB query
        mongo_query = {
            "$or": [
                {"brand": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"tags": {"$elemMatch": {"$regex": query, "$options": "i"}}},
                {"gender": {"$regex": query, "$options": "i"}}
            ]
        }
        
        # Add filters
        if filters:
            if filters.get('brand'):
                mongo_query['brand'] = {"$regex": filters['brand'], "$options": "i"}
            if filters.get('category'):
                mongo_query['category.name'] = {"$regex": filters['category'], "$options": "i"}
            if filters.get('gender'):
                mongo_query['gender'] = {"$regex": filters['gender'], "$options": "i"}
            if filters.get('in_stock') is not None:
                mongo_query['in_stock'] = filters['in_stock']
        
        # Get total count
        total_count = product_collection.count_documents(mongo_query)
        
        # Apply pagination
        skip = (page - 1) * limit
        products = list(product_collection.find(mongo_query).skip(skip).limit(limit))
        
        print(f"📦 MongoDB fallback found {len(products)} products (total: {total_count})")
        return products, total_count
        
    except Exception as e:
        print(f"❌ Fallback search error: {e}")
        return [], 0

# 🧪 Test function to debug search
def test_search(query: str = "lip balm"):
    """Test function to debug search functionality"""
    print(f"\n🧪 Testing search for: '{query}'")
    products, hits_meta, total = search_products_improved(query, top_k=5, page=1, limit=5)
    
    print(f"📊 Results: {len(products)} products found (total: {total})")
    for i, product in enumerate(products):
        print(f"  {i+1}. {product.get('name')} ({product.get('brand')}) - Score: {hits_meta[i]['relevance_score']:.3f}")
    
    return products, hits_meta

# 📊 Get search statistics
def get_search_stats() -> Dict:
    """Get statistics about the search system"""
    try:
        chroma_count = collection.count()
        mongo_count = product_collection.count_documents({})
        
        return {
            "chroma_products": chroma_count,
            "mongo_products": mongo_count,
            "sync_status": "synced" if chroma_count == mongo_count else "out_of_sync",
            "model": "all-MiniLM-L6-v2"
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Test the search functionality
    print("🧪 Running enhanced search tests...")
    test_search("lip balm")
    test_search("skincare")
    test_search("nivea")
    
    # Test with filters
    print("\n🧪 Testing with filters...")
    products, hits_meta, total = search_products_improved(
        "skincare", 
        filters={"brand": "nivea"}, 
        page=1, 
        limit=3
    )
    print(f"Filtered results: {len(products)} products")
    
    # Show stats
    print("\n📊 System stats:")
    stats = get_search_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")