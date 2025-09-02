from flask import Flask, request, jsonify
from rag_utils import search_products, sync_products_to_chroma
from openai import OpenAI
import google.generativeai as genai
from pymongo import MongoClient
import os
from flask_cors import CORS
from dotenv import load_dotenv
from bson import ObjectId

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

@app.route('/search', methods=['POST'])
def ai_search():
    try:
        user_query = request.json['query']
        agent = request.json.get('agent', 'openai')
        
        print(f"🔍 Search request: '{user_query}' using {agent}")

        # Vector search
        products, hits_meta = search_products(user_query)
        used_fallback = False

        print(f"🎯 Vector search found {len(products)} products")

        # Fallback: Mongo keyword search (only if vector search fails)
        if not products:
            print("🔄 Trying MongoDB fallback search...")
            fallback_products = list(product_collection.find({
                "$or": [
                    {"brand": {"$regex": user_query, "$options": "i"}},
                    {"name": {"$regex": user_query, "$options": "i"}},
                    {"description": {"$regex": user_query, "$options": "i"}},
                    {"tags": {"$elemMatch": {"$regex": user_query, "$options": "i"}}},
                    {"gender": {"$regex": user_query, "$options": "i"}}
                ]
            }))
            print(f"📦 MongoDB fallback found {len(fallback_products)} products")
            
            if fallback_products:
                products = fallback_products
                hits_meta = [{"product_id": str(p["_id"]), "distance": 0.0} for p in fallback_products]
                used_fallback = True

        # ❌ No products at all
        if not products:
            print("❌ No products found, returning suggestions")
            suggested_products = list(product_collection.find().limit(3))
            return jsonify({
                "products": [],
                "results": [],
                "ai_response": f"Sorry, we don't currently have any products related to \"{user_query}\".",
                "agent_used": agent,
                "suggestions": [serialize_product(p) for p in suggested_products],
                "used_fallback": used_fallback
            })

        # ✅ Product summary for prompt
        limited_products = products[:5]
        product_summaries = "\n".join([
            f"- {p['name']} ({p.get('brand', 'No Brand')}): {p.get('description', '')[:100]}..."
            for p in limited_products
        ])

        prompt = f"""
You are a smart shopping assistant for an e-commerce store.
User asked: "{user_query}"

Here are the available products that match their query:
{product_summaries}

Provide a helpful response recommending these products. Be enthusiastic and mention specific product names, brands, and key features that match what they're looking for.

If the products don't seem relevant to their query, say:
"Sorry, we don't have exactly what you're looking for, but here are some similar products that might interest you."
"""

        # 🤖 Generate AI response
        ai_reply = ""
        if agent == 'gemini':
            model = genai.GenerativeModel("models/gemini-1.5-flash")
            response = model.generate_content(prompt)
            ai_reply = response.text.strip()
        else:  # default OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            ai_reply = response.choices[0].message.content.strip()

        if not ai_reply:
            ai_reply = f"Here are some products that match your search for '{user_query}'."

        print(f"✅ Returning {len(products)} products with AI response")

        return jsonify({
            "products": [serialize_product(p) for p in products],
            "results": hits_meta,
            "ai_response": ai_reply,
            "agent_used": agent,
            "used_fallback": used_fallback,
            "debug": {
                "original_query": user_query,
                "products_found": len(products),
                "vector_search_worked": len(products) > 0 and not used_fallback
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error in ai_search: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sync', methods=['POST'])
def sync():
    try:
        print("🔄 Starting sync...")
        sync_products_to_chroma()
        
        # Test search after sync
        from rag_utils import test_search
        print("\n🧪 Testing search after sync:")
        test_search("lip balm")
        
        return jsonify({"message": "Synced successfully!"})
    except Exception as e:
        print(f"❌ Sync error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=["GET"])
def test():
    return "✅ Flask is working with OpenAI, Gemini, and ChromaDB!"

@app.route('/debug', methods=["POST"])
def debug_search():
    """Debug endpoint to test search functionality"""
    try:
        query = request.json.get('query', 'lip balm')
        print(f"\n🐛 Debug search for: '{query}'")
        
        # Import test function
        from rag_utils import test_search
        products, hits_meta = test_search(query)
        
        return jsonify({
            "query": query,
            "products_found": len(products),
            "products": [serialize_product(p) for p in products],
            "hits_meta": hits_meta
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Flask app...")
    app.run(port=5050, debug=True)