---
name: docling-langchain
description: >
  Builds PDF extraction pipelines and LangChain-based RAG systems using Docling.
  Use this skill whenever the user wants to:
  - Extract, parse, or index content from PDF, DOCX, PPTX, or HTML files
  - Build a RAG system, document Q&A, or embedding pipeline with LangChain
  - Work with DoclingLoader, HybridChunker, DocumentConverter, or ExportType
  - Perform document chunking, table extraction, OCR, or layout analysis
  - Phrases like "index this PDF", "load documents into vector store", "RAG with docling"
  Even if the user just says "read a PDF", trigger this skill if LangChain or RAG is in context.
---

# Docling + LangChain Skill

Docling is an open-source MIT-licensed document conversion library by IBM Research.
It converts PDF, DOCX, PPTX, HTML, Markdown, CSV, and 12+ formats into AI-ready structured output.
LangChain integration is provided via the `langchain-docling` package.

---

## Installation

```bash
pip install langchain-docling langchain-core langchain-huggingface langchain-milvus langchain python-dotenv sentence-transformers

# OCR support (optional)
# macOS:  brew install tesseract
# Ubuntu: apt-get install tesseract-ocr
```

---

## Core Concepts

### DocumentConverter (Standalone Docling)

Converts any document into Docling's rich internal format:

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("path/to/file.pdf")  # also accepts URLs
doc = result.document

doc.export_to_markdown()  # → Markdown string
doc.export_to_text()      # → Plain text
doc.export_to_dict()      # → JSON-serializable dict
```

### DoclingLoader (LangChain Integration)

Produces LangChain `Document` objects that plug directly into chains:

```python
from langchain_docling import DoclingLoader

loader = DoclingLoader(file_path="path/to/file.pdf")
docs = loader.load()
```

**Key parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `str` or `list` | Local path or URL(s) |
| `export_type` | `ExportType` | `DOC_CHUNKS` (default) or `MARKDOWN` |
| `chunker` | `HybridChunker` | Custom chunker instance |
| `converter` | `DocumentConverter` | Custom converter with pipeline options |
| `meta_extractor` | callable | Custom metadata extractor |

---

## Export Modes

### ExportType.DOC_CHUNKS *(recommended, default)*

Each chunk becomes a separate LangChain Document. Uses `HybridChunker` to split
respecting the embedding model's token limits — semantically aware, structure-preserving.

```python
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from docling.chunking import HybridChunker

EMBED_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

loader = DoclingLoader(
    file_path=["https://arxiv.org/pdf/2408.09869"],
    export_type=ExportType.DOC_CHUNKS,
    chunker=HybridChunker(tokenizer=EMBED_MODEL_ID),
)
splits = loader.load()  # each doc is already a chunk
```

> **Note:** `"Token indices sequence length is longer than..."` warning is harmless — ignore it.

### ExportType.MARKDOWN

Each document comes as a single LangChain Document. Split afterward by headers:

```python
from langchain_docling.loader import ExportType
from langchain_text_splitters import MarkdownHeaderTextSplitter

loader = DoclingLoader(file_path=FILE_PATH, export_type=ExportType.MARKDOWN)
docs = loader.load()

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")]
)
splits = [split for doc in docs for split in splitter.split_text(doc.page_content)]
```

**When to use which:**

| Use Case | Recommended Mode |
|----------|-----------------|
| Semantic search, large docs, embedding pipeline | `DOC_CHUNKS` |
| Document structure matters, header-based navigation | `MARKDOWN` |

---

## Full RAG Pipeline

```python
import os
from pathlib import Path
from tempfile import mkdtemp

from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from docling.chunking import HybridChunker
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEndpoint
from langchain_milvus import Milvus
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import PromptTemplate

# --- Config ---
FILE_PATH      = ["https://arxiv.org/pdf/2408.09869"]
EMBED_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
GEN_MODEL_ID   = "mistralai/Mixtral-8x7B-Instruct-v0.1"
TOP_K          = 3

PROMPT = PromptTemplate.from_template(
    "Context information is below.\n---------------------\n{context}\n"
    "---------------------\n"
    "Given the context information and not prior knowledge, answer the query.\n"
    "Query: {input}\nAnswer:\n"
)

# 1. Load & chunk documents
loader = DoclingLoader(
    file_path=FILE_PATH,
    export_type=ExportType.DOC_CHUNKS,
    chunker=HybridChunker(tokenizer=EMBED_MODEL_ID),
)
splits = loader.load()

# 2. Embed & store
embedding   = HuggingFaceEmbeddings(model_name=EMBED_MODEL_ID)
milvus_uri  = str(Path(mkdtemp()) / "docling.db")
vectorstore = Milvus.from_documents(
    documents=splits,
    embedding=embedding,
    collection_name="docling_demo",
    connection_args={"uri": milvus_uri},
    index_params={"index_type": "FLAT"},
    drop_old=True,
)

# 3. Build RAG chain
retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
llm       = HuggingFaceEndpoint(
    repo_id=GEN_MODEL_ID,
    huggingfacehub_api_token=os.getenv("HF_TOKEN"),
)
rag_chain = create_retrieval_chain(
    retriever,
    create_stuff_documents_chain(llm, PROMPT)
)

# 4. Query
resp = rag_chain.invoke({"input": "What are the main AI models in Docling?"})
print(resp["answer"])
```

---

## Advanced PDF Pipeline Options

For scanned PDFs or table-heavy documents:

```python
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

pipeline_options = PdfPipelineOptions(
    do_ocr=True,              # enable for scanned PDFs
    do_table_structure=True,  # enable table structure recognition
)
pipeline_options.table_structure_options.do_cell_matching = True
pipeline_options.ocr_options.lang = ["en"]
pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=4,
    device=AcceleratorDevice.AUTO  # uses GPU if available
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

loader = DoclingLoader(
    file_path="scanned_document.pdf",
    converter=converter,
    export_type=ExportType.DOC_CHUNKS,
)
```

---

## Chunk Metadata

In `DOC_CHUNKS` mode, each LangChain Document's `metadata["dl_meta"]` contains:

```json
{
  "schema_name": "docling_core.transforms.chunker.DocMeta",
  "doc_items": [{"self_ref": "#/texts/50", "label": "text", "prov": [...]}],
  "headings": ["3.2 AI models"],
  "origin": {"mimetype": "application/pdf", "filename": "doc.pdf"}
}
```

Use `headings` for context-aware retrieval and `prov` (page/bbox) for document grounding.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Token indices sequence length is longer than...` | Safe to ignore |
| Tables extracted incorrectly | Add `do_table_structure=True` + `do_cell_matching=True` |
| Scanned PDF returns empty text | Enable `do_ocr=True` in pipeline options |
| Chunks too large | Use `HybridChunker(max_tokens=512)` |
| GPU not being used | Set `AcceleratorDevice.AUTO` or `AcceleratorDevice.CUDA` |

---

## Supported Input Formats

PDF · DOCX · PPTX · HTML · Markdown · AsciiDoc · CSV · XLSX · Images (PNG, JPEG, TIFF) · XML (USPTO, JATS) · WebVTT
