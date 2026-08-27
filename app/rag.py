import os
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.vectorstores import FAISS

from langchain_huggingface import HuggingFaceEmbeddings

BASE_URL = "https://naikroop.com"

VECTORSTORE_PATH = "data/faiss_index"

MAX_PAGES = 20

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
})

def get_page(url):
    try:
        response = session.get(
            url,
            timeout=20
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(
            f"Could not fetch {url}: {e}"
        )
        return ""

def extract_page_content(
    html,
    url
):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "iframe"
    ]):
        tag.decompose()
    content = []
    if soup.title:
        title = soup.title.get_text(
            strip=True
        )
        if title:
            content.append(
                f"Page Title: {title}"
            )
            
    description = soup.find(
        "meta",
        attrs={
            "name": "description"
        }
    )

    if description:

        value = description.get(
            "content",
            ""
        ).strip()

        if value:

            content.append(
                f"Description: {value}"
            )

    keywords = soup.find(
        "meta",
        attrs={
            "name": "keywords"
        }
    )

    if keywords:
        value = keywords.get(
            "content",
            ""
        ).strip()
        if value:
            content.append(
                f"Keywords: {value}"
            )

    for heading in soup.find_all(
        ["h1", "h2", "h3", "h4"]
    ):
        text = heading.get_text(
            " ",
            strip=True
        )

        if text:
            content.append(
                text
            )

    for paragraph in soup.find_all(
        "p"
    ):
        text = paragraph.get_text(
            " ",
            strip=True
        )
        if text:
            content.append(
                text
            )

    for item in soup.find_all(
        "li"
    ):
        text = item.get_text(
            " ",
            strip=True
        )
        if text:
            content.append(
                text
            )

    unique_content = []

    seen = set()

    for text in content:
        text = " ".join(
            text.split()
        )
        if not text:
            continue

        if text in seen:
            continue

        seen.add(text)

        unique_content.append(
            text
        )
    return "\n".join(
        unique_content
    )

def find_internal_links(
    html,
    current_url
):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    links = set()

    for anchor in soup.find_all(
        "a",
        href=True
    ):
        href = anchor["href"].strip()
        if not href:
            continue
        full_url = urljoin(
            current_url,
            href
        )
        parsed = urlparse(
            full_url
        )
        if parsed.scheme not in [
            "http",
            "https"
        ]:
            continue

        if parsed.netloc != "naikroop.com":
            continue
        clean_url = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        )
        links.add(
            clean_url
        )
    return links

def crawl_website():
    pages_to_visit = [
        BASE_URL
    ]
    visited_pages = set()
    documents = []
    while pages_to_visit and len(
        visited_pages
    ) < MAX_PAGES:
        url = pages_to_visit.pop(0)
        if url in visited_pages:
            continue
        print(
            f"Crawling: {url}"
        )
        html = get_page(
            url
        )
        if not html:
            continue
        visited_pages.add(
            url
        )
        
        text = extract_page_content(
            html,
            url
        )
        if text:
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": url
                    }
                )
            )
            print(
                f"  Extracted: "
                f"{len(text)} characters"
            )

        links = find_internal_links(
            html,
            url
        )
        for link in links:
            if link not in visited_pages:
                if link not in pages_to_visit:
                    pages_to_visit.append(
                        link
                    )
    print()
    print(
        f"Pages crawled: "
        f"{len(visited_pages)}"
    )
    print(
        f"Documents created: "
        f"{len(documents)}"
    )
    return documents

def build_vectorstore():

    print()
    print("============================================================")
    print("BUILDING NAIKROOP KNOWLEDGE BASE")
    print("============================================================")

    documents = crawl_website()

    if not documents:
        raise RuntimeError("No website content was extracted.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )

    chunks = splitter.split_documents(
        documents
    )
    
    print()
    print(
        f"Total chunks created: "
        f"{len(chunks)}"
    )

    print()
    print("Loading embedding model...")

    embeddings = HuggingFaceEmbeddings(
        model_name=(
            "sentence-transformers/"
            "all-MiniLM-L6-v2"
        )
    )

    vectorstore = FAISS.from_documents(
        chunks,
        embeddings
    )

    os.makedirs(
        "data",
        exist_ok=True
    )

    vectorstore.save_local(
        VECTORSTORE_PATH
    )

    print()
    print("FAISS vector store saved.")
    print(f"Location: {VECTORSTORE_PATH}")

    return vectorstore

def load_vectorstore():
    embeddings = HuggingFaceEmbeddings(
        model_name=(
            "sentence-transformers/"
            "all-MiniLM-L6-v2"
        )
    )
    if not os.path.exists(
        VECTORSTORE_PATH
    ):
        return build_vectorstore()

    print("Loading existing FAISS vector store...")

    return FAISS.load_local(
        VECTORSTORE_PATH,
        embeddings,
        allow_dangerous_deserialization=True
    )

def retrieve_knowledge(
    question: str,
    k: int = 4
):
    vectorstore = load_vectorstore()
    documents = vectorstore.similarity_search(
        question,
        k=k
    )
    if not documents:
        return ""

    context_parts = []
    for document in documents:
        source = document.metadata.get(
            "source",
            BASE_URL
        )
        context_parts.append(
            f"Source: {source}\n"
            f"{document.page_content}"
        )

    return "\n\n".join(
        context_parts
    )