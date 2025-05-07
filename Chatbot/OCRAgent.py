import os
from pathlib import Path
from langchain.document_loaders import UnstructuredPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA, LLMChain
from langchain.llms import OpenAI
import requests

# ─── CONFIG ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY   = os.getenv("SERPAPI_KEY")  # for live address lookup (optional)

# where to store your vector index
INDEX_DIR = Path("indexes/property_index")
INDEX_DIR.mkdir(exist_ok=True)

# ─── STEP 1: INGEST & INDEX ────────────────────────────────────────────────────
def ingest_and_index(filepath: str, index_path: Path = INDEX_DIR):
    """
    1) Load PDF (runs OCR if needed under the hood).
    2) Split into chunks.
    3) Embed & store in a FAISS index on disk.
    """
    # load
    loader = UnstructuredPDFLoader(filepath)
    docs = loader.load()

    # split
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    )
    docs = splitter.split_documents(docs)

    # embed + index
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    index = FAISS.from_documents(docs, embeddings)
    index.save_local(str(index_path))
    return index

# ─── STEP 2: BUILD A RETRIEVAL AGENT ────────────────────────────────────────────
def build_qa_chain(index_path: Path = INDEX_DIR):
    """
    Loads your FAISS index and returns a RetrievalQA chain.
    """
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    index = FAISS.load_local(str(index_path), embeddings)
    llm = OpenAI(temperature=0, openai_api_key=OPENAI_API_KEY)
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=index.as_retriever(search_kwargs={"k":5})
    )
    return qa

# ─── STEP 3: OPTIONAL LIVE ADDRESS RESEARCH ────────────────────────────────────
def serpapi_search(query: str, num: int = 3):
    """
    Do a quick Google search via SerpAPI to fetch snippets for an address.
    """
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    resp = requests.get("https://serpapi.com/search", params=params)
    data = resp.json().get("organic_results", [])
    return "\n\n".join(
        f"- {item.get('title')}: {item.get('snippet')}" for item in data
    )

# ─── STEP 4: QUERYING ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) Ingest your scraped-PDF once:
    ingest_and_index("output/document_snapshot.pdf")

    # 2) Build the QA chain:
    qa_chain = build_qa_chain()

    # 3) Ask it anything about your document:
    question = "What is the outstanding balance for 123 Main St, Houston?"
    answer = qa_chain.run(question)
    print("📄 QA:", answer)

    # 4) Do live research on that address:
    live = serpapi_search("123 Main St Houston foreclosure status")
    print("\n🌐 Live Research:\n", live)
