from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from src.prompt import *
import os


app = Flask(__name__)


load_dotenv()

PINECONE_API_KEY=os.environ.get('PINECONE_API_KEY')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY


embeddings = download_hugging_face_embeddings()

index_name = "medical-chatbot" 
# Embed each chunk and upsert the embeddings into your Pinecone index.
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)




retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k":3})

# Hệ thống sẽ tự động bốc biến GEMINI_API_KEY hoặc GOOGLE_API_KEY bạn đã nạp trong os.environ lúc nãy
chatModel = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3         
)


def answer_question(question):
    """Answer a question using retrieval augmented generation"""
    # Retrieve relevant documents
    retrieved_docs = retriever.invoke(question)
    
    # Format the context from retrieved documents
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    # Prepare the prompt
    prompt_text = system_prompt.format(context=context, question=question)
    
    # Get answer from the model using invoke
    response = chatModel.invoke(prompt_text)
    
    return str(response.content) if hasattr(response, 'content') else str(response)



@app.route("/")
def index():
    return render_template('chat.html')



@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    input = msg
    print(input)
    response = answer_question(msg)
    print("Response : ", response)
    return str(response)



if __name__ == '__main__':
    app.run(host="0.0.0.0", port= 8080, debug= True)