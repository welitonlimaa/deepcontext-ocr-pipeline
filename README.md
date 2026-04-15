# OCR Pipeline — PDF para LLM Context

Pipeline desacoplado para extração e transformação de PDFs grandes
em contexto otimizado para LLMs, usando **markitdown**, **pdfplumber**, **Redis**, **MinIO** e **Celery**.

---

## Arquitetura

![flow](/image/mxGraphModel.jpg)

---

## Formato dos Outputs

### Resposta imediata (202) — `POST /jobs/submit`

```json
{
  "job_id": "3f7a2c1d-...",
  "status": "queued",
  "message": "PDF recebido. Processamento iniciado em background.",
  "tracking": {
    "status_url": "/jobs/3f7a2c1d-...",
    "index_url": "/jobs/3f7a2c1d-.../index",
    "storage_path": "minio://ocr-pipeline/jobs/3f7a2c1d-.../"
  },
  "metadata": {
    "filename": "relatorio-anual.pdf",
    "size_mb": 12.4,
    "tags": ["relatorio", "2024"]
  }
}
```

### Estado do job — `GET /jobs/{id}`

```json
{
  "job_id": "3f7a2c1d-...",
  "status": "extracting",
  "message": "Extraindo 120 páginas em 12 chunks...",
  "progress_pct": 41.6,
  "progress_pages": 50,
  "total_pages": 120,
  "updated_at": "2024-11-15T14:32:10Z",
  "outputs": {}
}
```

### Índice final — `GET /jobs/{id}/index` (quando COMPLETED)

```json
{
  "job_id": "3f7a2c1d-...",
  "total_pages": 120,
  "total_chunks": 12,
  "chunks_processed": 12,
  "chunks_failed": 0,
  "total_tokens_estimate": 48300,
  "total_tables_extracted": 14,
  "chunks": [
    {
      "chunk_index": 0,
      "start_page": 1,
      "end_page": 10,
      "markdown_key": "jobs/3f7a2c1d-.../chunks/chunk_0000.md",
      "json_key": "jobs/3f7a2c1d-.../chunks/chunk_0000.json",
      "tokens_estimate": 3800,
      "tables_count": 2,
      "markdown_url": "http://minio:9000/ocr-pipeline/jobs/...?X-Amz-..."
    }
  ],
  "llm_context": {
    "format": "markdown",
    "chunk_keys": ["jobs/.../chunk_0000.md", "jobs/.../chunk_0001.md"],
    "structured_keys": ["jobs/.../chunk_0000.json"],
    "recommended_chunk_size_tokens": 8000,
    "total_estimated_tokens": 48300
  }
}
```

### Chunk estruturado JSON — `jobs/{id}/chunks/chunk_NNNN.json`

```json
{
  "job_id": "3f7a2c1d-...",
  "chunk_index": 0,
  "start_page": 1,
  "end_page": 10,
  "tokens_estimate": 3800,
  "tables": [
    {
      "table_index": 0,
      "headers": ["Produto", "Vendas", "Meta", "% Atingido"],
      "rows": [
        {"Produto": "Produto A", "Vendas": "R$ 4.200.000", "Meta": "R$ 4.000.000", "% Atingido": "105%"}
      ],
      "row_count": 3
    }
  ],
  "pages_summary": [
    {"page_num": 1, "word_count": 312, "has_tables": false, "has_images": false}
  ]
}
```

### Chunk markdown — `jobs/{id}/chunks/chunk_NNNN.md`

```markdown
# Chunk 1 | Páginas 1–10

## Página 1

Relatório Corporativo — Exercício 2024

Este documento apresenta os resultados financeiros consolidados...

---

## Página 2

**Tabela 1:**
| Produto  | Vendas        | Meta          | % Atingido |
|----------|---------------|---------------|------------|
| Produto A| R$ 4.200.000  | R$ 4.000.000  | 105%       |
```

---

## Estrutura de Arquivos

```
ocr-pipeline/
├── app/
│   ├── api.py          # FastAPI endpoints
│   ├── extractor.py    # Engine OCR (pdfplumber + markitdown)
│   ├── job_state.py    # Estado dos jobs no Redis
│   └── storage.py      # Client MinIO
├── workers/
│   └── pipeline.py     # Tasks Celery (process_document, extract_chunk, finalize)
├── config/
│   └── settings.py     # Configurações via env vars
├── tests/
│   └── test_pipeline.py # Teste de integração completo
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Sobe infraestrutura
docker-compose up -d --build

# 2. Envia um PDF
curl -X POST http://localhost:8000/jobs/submit \
  -F "file=@relatorio.pdf" \
  -F "tags=relatorio,2024"

# 3. Acompanha progresso
curl http://localhost:8000/jobs/{job_id}

# 4. Obtém índice e chaves dos chunks
curl http://localhost:8000/jobs/{job_id}/index
```

---

## Variáveis de Ambiente

| Variável              | Padrão             | Descrição                          |
|-----------------------|--------------------|------------------------------------|
| `REDIS_URL`           | redis://localhost:6379 | Broker e backend Celery        |
| `MINIO_ENDPOINT`      | localhost:9000     | Endpoint MinIO                     |
| `MINIO_ACCESS_KEY`    | minioadmin         | Access key MinIO                   |
| `MINIO_SECRET_KEY`    | minioadmin123      | Secret key MinIO                   |
| `MINIO_BUCKET`        | ocr-pipeline       | Nome do bucket                     |
| `CHUNK_SIZE_PAGES`    | 10                 | Páginas por chunk                  |
| `MAX_FILE_SIZE_MB`    | 200                | Tamanho máximo do PDF              |

---