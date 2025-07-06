from flask import Flask, request, jsonify
from rag_utils import search_products, sync_products_to_chroma
from openai import OpenAI
import google.generativeai as genai
from huggingface_hub import InferenceClient
from pymongo import MongoClient
import os
from flask_cors import CORS
from dotenv import load_dotenv

# 🔐 Load env variables
load_dotenv()

# ✅ Clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"

# 📦 MongoDB setup
mongo_client = MongoClient(os.getenv("MONGO_URI"))
product_collection = mongo_client["ecommerce-ai"]["products"]

# ⚙️ Flask app
app = Flask(__name__)
CORS(app)

# 🧾 Serialize Mongo ObjectId
def serialize_product(product):
    product = dict(product)
    product["_id"] = str(product["_id"])
    if "categoryId" in product:
        product["categoryId"] = str(product["categoryId"])
    return product

@app.route('/search', methods=['POST'])
def ai_search():
    try:
        user_query = request.json['query']
        agent = request.json.get('agent', 'openai')

        # 🧠 Primary vector search
        products = search_products(user_query)
        used_fallback = False

        # 🧠 Fallback: Mongo keyword search
        if not products:
            fallback_products = list(product_collection.find({
                "$or": [
                    { "brand": { "$regex": user_query, "$options": "i" } },
                    { "name": { "$regex": user_query, "$options": "i" } },
                    { "description": { "$regex": user_query, "$options": "i" } },
                    { "tags": { "$elemMatch": { "$regex": user_query, "$options": "i" } } },
                    { "gender": { "$regex": user_query, "$options": "i" } }
                ]
            }))
            if fallback_products:
                products = fallback_products
                used_fallback = True

        # ❌ No products at all
        if not products:
            return jsonify({
                "products": [],
                "ai_response": f"Sorry, we don't currently have any products related to \"{user_query}\".",
                "agent_used": agent,
                "suggestions": [
                    "Show me deodorants for men",
                    "Do you have any lip balm?",
                    "What grooming products do you offer?"
                ]
            })

        # ✅ Product summary for prompt
        limited_products = products[:5]
        product_summaries = "\n".join([
            f"- {p['name']} ({p.get('brand', 'No Brand')}): {p.get('description', '')}"
            for p in limited_products
        ])

        prompt = f"""
You are a smart shopping assistant.

User asked: "{user_query}"

Here are some available products. Choose only from this list. Suggest the most relevant product(s). Do NOT make up any product.

Product List:
{product_summaries}

If none of the products are relevant, say:
"Sorry, we don't have any product for '{user_query}' yet."

Otherwise, clearly suggest from this list using product names exactly as written.
"""

        # 🤖 Generate response
        ai_reply = ""
        if agent == 'gemini':
            model = genai.GenerativeModel("models/gemini-1.5-flash")
            response = model.generate_content(prompt)
            ai_reply = response.text.strip()

        elif agent == 'huggingface':
            try:
                client = InferenceClient(token=HF_TOKEN)
                response = client.chat_completion(
                    model=HF_MODEL,
                    messages=[{ "role": "user", "content": prompt }],
                    max_tokens=300,
                    temperature=0.7
                )
                ai_reply = response.choices[0].message["content"].strip()
            except Exception as e:
                print("⚠️ HuggingFace error:", e)
                ai_reply = ""

        else:  # OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{ "role": "user", "content": prompt }],
                max_tokens=300
            )
            ai_reply = response.choices[0].message.content.strip()

        # 🧠 If AI reply is bad or hallucinating
        if not ai_reply or (
            ("sorry" in ai_reply.lower() or "don't have" in ai_reply.lower())
            and len(products) > 0
        ):
            ai_reply = f"We found some relevant items! For example: {', '.join([p['name'] for p in limited_products])}."

        # 🧾 Final response
        return jsonify({
            "products": [serialize_product(p) for p in products],
            "ai_response": ai_reply,
            "agent_used": agent
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({ "error": str(e) }), 500

@app.route('/sync', methods=['POST'])
def sync():
    try:
        sync_products_to_chroma()
        return jsonify({ "message": "Synced successfully!" })
    except Exception as e:
        return jsonify({ "error": str(e) }), 500

@app.route('/test', methods=["GET"])
def test():
    return "✅ Flask is working with OpenAI, Gemini, and HuggingFace!"

if __name__ == '__main__':
    app.run(port=5050, debug=True)
