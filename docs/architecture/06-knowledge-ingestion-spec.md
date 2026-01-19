# Knowledge Ingestion Specification (Docs → AI Search → Tool Draft)

## Purpose
Enable the platform to discover how to call APIs without hard-coded definitions by indexing API documentation and schemas into Azure AI Search.

## Inputs
- PDF documentation
- HTML pages (exported docs)
- Swagger/OpenAPI files (if available)
- Internal runbooks/specs (optional)

## Pipeline (MVP)
1. Document ingestion:
   - Upload or provide path/URL (MVP can be file-based)
2. Extraction:
   - Use Azure Document Intelligence for PDFs/HTML conversion to text
3. Chunking:
   - Chunk by headings/sections
   - Preserve metadata: doc source, version, section titles
4. Embeddings + Indexing:
   - Create embeddings per chunk
   - Store in AI Search with fields:
     - id, title, source, chunk_text, embedding, tags, created_at
5. Retrieval:
   - Vector search + keyword hybrid search
   - Return top-k relevant chunks

## Tool Draft Generation (MVP)
From retrieved chunks, generate:
- endpoint path(s)
- required headers/auth hints
- method(s)
- example payload schema
- response schema hints

## Approval Gating (Must-Have)
- Tool drafts are created as `pending`
- A configuration flag controls whether manual approval is required
- MVP default: approval required

## Safety Rules
- Never ingest or index secrets
- Redact obvious credentials from extracted docs
- Store only sanitized docs content in the index
