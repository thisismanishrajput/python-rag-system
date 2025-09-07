from flask import Flask, request, jsonify
from rag_utils import (
    search_products_improved, 
    sync_products_to_chroma, 
    sync_single_product,
    delete_product_from_chroma,
    fallback_search,
    get_search_stats
)
from openai import OpenAI
import google.generativeai as genai
from pymongo import MongoClient
import os
from flask_cors import CORS
from dotenv import load_dotenv
from bson import ObjectId
import traceback
import math

# 🔐 Load env variables
load_dotenv()

# ✅ Clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 📦 MongoDB setup
mongo_client = MongoClient(os.getenv("MONGO_URI"))
product_collection = mongo_client["ecommerce-ai"]["products"]

# ⚙️ Flask app
app = Flask(__name__)
CORS(app)

# 🧾 Serialize Mongo ObjectId - Enhanced version
def serialize_product(product):
    """Convert MongoDB document to JSON-serializable format"""
    if not product:
        return product
    
    product = dict(product)
    
    # Convert all ObjectId fields to strings
    for key, value in product.items():
        if isinstance(value, ObjectId):
            product[key] = str(value)
        elif isinstance(value, list):
            # Handle arrays that might contain ObjectIds
            product[key] = [str(item) if isinstance(item, ObjectId) else item for item in value]
        elif isinstance(value, dict):
            # Handle nested objects that might contain ObjectIds
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, ObjectId):
                    value[nested_key] = str(nested_value)
    
    return product

def generate_ai_response(query: str, products: list, agent: str = "openai") -> str:
    """Generate AI response based on products found"""
    if not products:
        return f"Sorry, we don't currently have any products related to \"{query}\"."
    
    # Create product summaries
    product_summaries = "\n".join([
        f"- {p['name']} ({p.get('brand', 'No Brand')}): {p.get('description', '')[:100]}..."
        for p in products[:5]  # Limit to top 5 for prompt
    ])

    prompt = f"""
You are a smart shopping assistant for an e-commerce store.
User asked: "{query}"

Here are the available products that match their query:
{product_summaries}

Provide a helpful response recommending these products. Be enthusiastic and mention specific product names, brands, and key features that match what they're looking for.

If the products don't seem relevant to their query, say:
"Sorry, we don't have exactly what you're looking for, but here are some similar products that might interest you."

Keep the response concise and engaging (max 200 words).
"""

    try:
        if agent == 'gemini':
            model = genai.GenerativeModel("models/gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        else:  # default OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ AI response error: {e}")
        return f"Here are some products that match your search for '{query}'."

@app.route('/search', methods=['POST'])
def ai_search():
    """Enhanced search endpoint with pagination and filtering"""
    try:
        data = request.json
        user_query = data.get('query', '')
        agent = data.get('agent', 'openai')
        page = data.get('page', 1)
        limit = data.get('limit', 10)
        filters = data.get('filters', {})
        max_distance = data.get('max_distance', 1.2)
        
        if not user_query:
            return jsonify({"error": "Query is required"}), 400
        
        print(f"🔍 Search request: '{user_query}' using {agent} (page {page}, limit {limit})")
        print(f"🔍 Filters: {filters}")

        # Enhanced vector search
        products, hits_meta, total_count = search_products_improved(
            query=user_query,
            top_k=limit * 2,  # Get more results for better ranking
            page=page,
            limit=limit,
            filters=filters,
            max_distance=max_distance
        )
        
        used_fallback = False
        
        # Fallback to MongoDB search if vector search fails
        if not products:
            print("🔄 Trying MongoDB fallback search...")
            products, total_count = fallback_search(
                query=user_query,
                filters=filters,
                page=page,
                limit=limit
            )
            used_fallback = True

        # Generate AI response
        ai_response = generate_ai_response(user_query, products, agent)
        
        # Calculate pagination info
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 0
        
        print(f"✅ Returning {len(products)} products (page {page}/{total_pages})")

        return jsonify({
            "products": [serialize_product(p) for p in products],
            "hits_meta": hits_meta,
            "ai_response": ai_response,
            "agent_used": agent,
            "used_fallback": used_fallback,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "filters_applied": filters,
            "debug": {
                "original_query": user_query,
                "products_found": len(products),
                "vector_search_worked": len(products) > 0 and not used_fallback,
                "max_distance": max_distance
            }
        })

    except Exception as e:
        print(f"❌ Error in ai_search: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/sync', methods=['POST'])
def sync():
    """Full sync endpoint"""
    try:
        print("🔄 Starting full sync...")
        sync_products_to_chroma()
        
        # Test search after sync
        from rag_utils import test_search
        print("\n🧪 Testing search after sync:")
        test_search("lip balm")
        
        return jsonify({"message": "Full sync completed successfully!"})
    except Exception as e:
        print(f"❌ Sync error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/sync-product', methods=['POST'])
def sync_single():
    """Sync a single product endpoint"""
    try:
        data = request.json
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({"error": "product_id is required"}), 400
        
        print(f"🔄 Syncing single product: {product_id}")
        success = sync_single_product(product_id)
        
        if success:
            return jsonify({"message": "Product synced successfully!", "product_id": product_id})
        else:
            return jsonify({"error": "Failed to sync product"}), 500
            
    except Exception as e:
        print(f"❌ Single sync error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/delete-product', methods=['POST'])
def delete_product():
    """Delete a product from ChromaDB"""
    try:
        data = request.json
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({"error": "product_id is required"}), 400
        
        print(f"🗑️ Deleting product from ChromaDB: {product_id}")
        success = delete_product_from_chroma(product_id)
        
        if success:
            return jsonify({"message": "Product deleted successfully!", "product_id": product_id})
        else:
            return jsonify({"error": "Failed to delete product"}), 500
            
    except Exception as e:
        print(f"❌ Delete error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        stats = get_search_stats()
        return jsonify(stats)
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=["GET"])
def test():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Flask RAG system is working with OpenAI, Gemini, and ChromaDB!",
        "features": [
            "Enhanced vector search with ranking",
            "Pagination support",
            "Filtering capabilities",
            "Incremental sync",
            "Fallback search",
            "AI response generation"
        ]
    })

@app.route('/debug', methods=["POST"])
def debug_search():
    """Debug endpoint to test search functionality"""
    try:
        data = request.json
        query = data.get('query', 'lip balm')
        filters = data.get('filters', {})
        
        print(f"\n🐛 Debug search for: '{query}' with filters: {filters}")
        
        # Test enhanced search
        products, hits_meta, total = search_products_improved(
            query=query,
            top_k=5,
            page=1,
            limit=5,
            filters=filters
        )
        
        return jsonify({
            "query": query,
            "filters": filters,
            "products_found": len(products),
            "total_available": total,
            "products": [serialize_product(p) for p in products],
            "hits_meta": hits_meta,
            "stats": get_search_stats()
        })
    except Exception as e:
        print(f"❌ Debug error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting enhanced Flask RAG app...")
    print("📋 Available endpoints:")
    print("  POST /search - Enhanced search with pagination and filtering")
    print("  POST /sync - Full sync all products")
    print("  POST /sync-product - Sync single product")
    print("  POST /delete-product - Delete product from ChromaDB")
    print("  GET /stats - System statistics")
    print("  GET /test - Health check")
    print("  POST /debug - Debug search functionality")
    
    app.run(port=5050, debug=True)