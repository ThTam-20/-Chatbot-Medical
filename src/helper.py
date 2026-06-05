from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List
from langchain_core.documents import Document


#Extract Data From the PDF File
def load_pdf_file(data):
    loader= DirectoryLoader(data,
                            glob="*.pdf",
                            loader_cls=PyPDFLoader)

    documents=loader.load()

    return documents



def filter_to_minimal_docs(docs: List[Document]) -> List[Document]:
    """
    Given a list of Document objects, return a new list of Document objects
    containing only 'source' in metadata and the original page_content.
    """
    minimal_docs: List[Document] = []
    for doc in docs:
        src = doc.metadata.get("source")
        minimal_docs.append(
            Document(
                page_content=doc.page_content,
                metadata={"source": src}
            )
        )
    return minimal_docs



#Split the Data into Text Chunks
def text_split(extracted_data):
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    text_chunks=text_splitter.split_documents(extracted_data)
    return text_chunks



#Download the Embeddings from HuggingFace 
def download_hugging_face_embeddings():
    embeddings=HuggingFaceEmbeddings(model_name='intfloat/multilingual-e5-small')  #this model return 384 dimensions
    return embeddings


# --- Các hàm hỗ trợ Multi-Query Retrieval ---

def translate_query_to_english(question: str, chat_model) -> str:
    """Dịch câu hỏi tiếng Việt sang tiếng Anh để tìm kiếm tốt hơn trong tài liệu Anh."""
    translate_prompt = (
        "Translate the following medical question to English. "
        "If it is already in English, return it as-is. "
        "Only return the translation, nothing else.\n\n"
        f"Question: {question}"
    )
    response = chat_model.invoke(translate_prompt)
    return str(response.content).strip() if hasattr(response, 'content') else str(response).strip()


def expand_query(question: str, chat_model) -> List[str]:
    """Tạo các biến thể truy vấn bằng tiếng Anh để tăng recall."""
    expand_prompt = (
        "Given this medical question, generate 3 alternative search queries in English "
        "that would help find relevant medical information. "
        "Include medical terminology and common synonyms.\n"
        "Return ONLY the queries, one per line, no numbering.\n\n"
        f"Question: {question}"
    )
    response = chat_model.invoke(expand_prompt)
    content = str(response.content).strip() if hasattr(response, 'content') else str(response).strip()
    queries = [q.strip() for q in content.split('\n') if q.strip()]
    return queries


def rerank_documents(question: str, docs: List[Document], chat_model, top_k: int = 5) -> List[Document]:
    """Dùng LLM để rerank documents theo mức độ liên quan thực sự với câu hỏi."""
    if not docs:
        return []

    doc_summaries = ""
    for i, doc in enumerate(docs):
        snippet = doc.page_content[:300].replace('\n', ' ')
        doc_summaries += f"[{i}] {snippet}\n\n"

    rerank_prompt = (
        f'Given the question: "{question}"\n\n'
        "Rate the relevance of each document snippet below. "
        "Return ONLY the indices of documents that are relevant to the question, "
        "separated by commas, ordered from most to least relevant. "
        'If none are relevant, return exactly "NONE".\n\n'
        f"Documents:\n{doc_summaries}\n"
        "Relevant indices:"
    )

    response = chat_model.invoke(rerank_prompt)
    content = str(response.content).strip() if hasattr(response, 'content') else str(response).strip()

    if content.upper() == "NONE":
        return []

    try:
        indices = [int(i.strip()) for i in content.split(',') if i.strip().isdigit()]
        return [docs[i] for i in indices if i < len(docs)][:top_k]
    except Exception:
        return docs[:top_k]