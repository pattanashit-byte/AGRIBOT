from flask import Blueprint, request, jsonify
from utils.metrics_store import increment_metric
from utils.response_utils import format_response
from transformers import AutoTokenizer, AutoModelForCausalLM

chatbot_bp = Blueprint("chatbot", __name__)

# Load the model and tokenizer
tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")

def generate_reply(msg):
    try:
        # Encode the new user input, add the eos_token and return a tensor in Pytorch
        input_ids = tokenizer.encode(msg + tokenizer.eos_token, return_tensors='pt')
        # Generate a response
        chat_history_ids = model.generate(input_ids, max_length=1000, pad_token_id=tokenizer.eos_token_id)
        # Decode the response
        response = tokenizer.decode(chat_history_ids[:, input_ids.shape[-1]:][0], skip_special_tokens=True)
        return response
    except Exception as e:
        return "Sorry, I couldn't generate a response right now."

@chatbot_bp.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        data = request.get_json()
        message = data.get("message", "")

        reply = generate_reply(message)
        increment_metric("chatbot_interactions")

        return jsonify(format_response("success", "Chatbot response", reply))

    except Exception as e:
        return jsonify(format_response("error", str(e), None))
