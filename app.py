from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings, translate_query_to_english, expand_query, rerank_documents
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from src.prompt import *
import os


app = Flask(__name__)


load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
# langchain_google_genai yêu cầu biến GOOGLE_API_KEY
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY


embeddings = download_hugging_face_embeddings()

index_name = "medical-chatbot" 
# Embed each chunk and upsert the embeddings into your Pinecone index.
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)




retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 7})

chatModel = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3,
    google_api_key=GEMINI_API_KEY
)


def answer_question(question):
    """Answer a question using multi-query retrieval + reranking"""
    all_docs = []
    seen_contents = set()

    def _add_unique_docs(docs):
        for doc in docs:
            if doc.page_content not in seen_contents:
                all_docs.append(doc)
                seen_contents.add(doc.page_content)

    # 1. LUÔN dịch query sang tiếng Anh trước
    translated = translate_query_to_english(question, chatModel)

    # 2. Search bằng câu hỏi gốc
    original_docs = retriever.invoke(question)
    _add_unique_docs(original_docs)

    # 3. Search bằng query đã dịch (nếu khác query gốc)
    if translated.lower() != question.lower():
        trans_docs = retriever.invoke(translated)
        _add_unique_docs(trans_docs)

    # 4. Nếu vẫn ít docs (sau dedup), mở rộng query
    if len(all_docs) < 5:
        expanded_queries = expand_query(question, chatModel)
        for eq in expanded_queries:
            eq_docs = retriever.invoke(eq)
            _add_unique_docs(eq_docs)

    # 5. Rerank để giữ lại các docs thực sự liên quan
    if all_docs:
        ranked_docs = rerank_documents(question, all_docs, chatModel, top_k=5)
        final_docs = ranked_docs if ranked_docs else all_docs[:5]
    else:
        final_docs = []

    # 6. Tổng hợp câu trả lời
    context = "\n\n".join([doc.page_content for doc in final_docs])
    prompt_text = system_prompt.format(context=context, question=question)
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