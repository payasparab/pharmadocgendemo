# Basic imports
import io
import os


# Flask imports
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Create Flask app and ensure CORS
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024         # define upper limit for input content
CORS(app)


# import sdk for azure openai api
from openai import AzureOpenAI

# retrieve or set necessary information for client initialization
endpoint = os.getenv('AZURE_AI_API_ENDPOINT')
subscription_key = os.getenv('AZURE_AI_API_KEY')
model_name = "gpt-4.1"
deployment = "gpt-4.1"
api_version = "2024-12-01-preview"

# initializes a client to communicate with Azure OpenAI model
def initialize_client():
    return AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=subscription_key,
    )

# given a client and messages, perform the chat completion endpoint to retrieve a response from the model
def get_response(client, messages: list[str]):
    response = client.chat.completions.create(
        messages=messages,
        max_completion_tokens=13107,
        temperature=1.0,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        model=deployment,
    )

    return response.choices[0].message.content


# Routes

@app.route('/generate-document', methods = ['POST'])
def generate_doc():

    client = initialize_client()
    data = request.get_json()
    prompt = data.get('prompt')

    messages = [{
            'role':'system',
            "content": "You are a document generator that only outputs documents according to specifications in markdown or html that can be transformed later into pdfs and docx files."
        },
        {
            'role':'user',
            'content': prompt
        }]

    response = get_response(client, messages)
    client.close()
    return jsonify(response)


if __name__ == "__main__":

    app.run(host='0.0.0.0', port=10000)

