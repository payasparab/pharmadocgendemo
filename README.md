Here’s a human-readable README for your `flask_api.py` that explains what it does, the API routes it exposes (grouped by purpose), and a high-level dependency map.

# Overview (what this app does)

* Provides a Flask HTTP API for **Egnyte** file/folder operations (auth, list, create, download, upload) with built-in **rate-limiting and token caching** to respect Egnyte limits. &#x20;
* Kicks off **background jobs** to create standardized **Egnyte project folder structures** and to **generate documents** with OpenAI, reporting progress via status endpoints. &#x20;
* Includes helper utilities like **clearing the Egnyte token cache** and a **threading test** endpoint. &#x20;

---

# API Routes

## 1) Utilities & Status

* `GET /test-thread` – fires a 10-second background thread to verify threading works; returns immediately with a timestamp.&#x20;
* `GET /folder-status?molecule_code=<>&campaign_number=<>` – status for **folder creation** jobs (running/progress/completed + data). &#x20;
* `GET /document-status?molecule_code=<>&campaign_number=<>` – status for **document generation** jobs (running/progress/completed + data).&#x20;
* `POST /egnyte-clear-cache` – clears in-memory and on-disk token cache for Egnyte auth.&#x20;

## 2) Egnyte – Folder Lifecycle & Listings

* `POST /egnyte-generate-folder-structure` – starts background job to create a project/campaign folder tree (Pre/Post, dept/status subfolders). Returns a `job_key` + poll URL. &#x20;
* `GET /egnyte-folder-status?molecule_code=<>&campaign_number=<>` – status for the above folder-creation job.&#x20;
* `GET /egnyte-list-folder?folder_id=<>` – list folders/files for a folder ID (defaults to `ROOT_FOLDER`). &#x20;
* `POST /egnyte-create-folder` – create a folder under `parent_folder_id` (defaults to `ROOT_FOLDER`); returns path and a direct Egnyte web URL. &#x20;
* `GET /egnyte-list-templates` – list files/folders inside the predefined templates folder. &#x20;
* `GET /egnyte-list-source-documents` – list files/folders inside the predefined source documents folder. &#x20;
* `GET /list-docs` – list documents for a **folder path** (not ID); returns each file plus a navigable link built from its `group_id`. &#x20;

## 3) Egnyte – File Download / Document Generation

* `POST /egnyte-download-file` – download a file by file ID; returns base64 content, content type, and size. &#x20;
* `POST /egnyte-generate-document` – background job that: downloads a template + source docs from Egnyte, uses OpenAI to generate a new document, and uploads it back. Returns `job_key` + poll URL. &#x20;
* `GET /egnyte-document-status?job_key=<>` – status for the above document generation job (progress/completed + file URL when done).&#x20;

## 4) Regulatory Docs – Bulk

* `POST /reg-docs-bulk-request` – accepts a JSON array (e.g., from Retool), parses product/version info, fetches templates, and orchestrates bulk regulatory doc actions. &#x20;

## 5) Dev/Test Helpers

* `POST /test-document-generation` – local test runner that reads a sample template/PDF from disk, calls the OpenAI pipeline, and writes a DOCX to disk; returns timings & details. &#x20;

---

# Core Function Categories (what the code is organized around)

1. **Egnyte Authentication & Governance**

   * **Token acquisition & retry** with rate-limiting and detailed logging. **Caches tokens** in memory and on disk; supports clearing the cache.  &#x20;
   * **Constants & limits**: waits \~1s/request by default; comments document Egnyte limits.&#x20;

2. **Egnyte Folder/File Operations**

   * List folder contents (by ID or by path), create folders, and build direct file links. &#x20;
   * **Background folder scaffold** builder for project/campaign (Pre/Post → Dept → Status).&#x20;

3. **Document Generation Pipeline (OpenAI)**

   * Downloads template + sources from Egnyte, extracts text, prompts OpenAI, writes a DOCX, and uploads the result. Exposed via `/egnyte-generate-document` with status polling.  &#x20;

4. **Job Management & Status**

   * All long-running operations run in **background threads**; the app tracks `job_status`/`job_results` and exposes read-only status endpoints returning progress, timestamps, and results. &#x20;

5. **Bulk Regulatory Workflow**

   * Parses incoming requests, normalizes version strings, pulls supporting docs/templates from Egnyte, and orchestrates document actions at scale. &#x20;

---

# Dependency & Integration Map (high-level)

**Framework & HTTP**

* **Flask** (routing, JSON I/O), **Flask-CORS** (cross-origin access). &#x20;

**External Services**

* **Egnyte REST API** – OAuth token + folder/file endpoints (create/list/download/upload). Rate-limit helper `rate_limit_delay()`, persistent token cache file `egnyte_token_cache.json`. &#x20;
* **OpenAI** – `initialize_openai()` builds a client from env/credentials; used by `generate_document_with_openai()` (chat completions) to assemble DOCX outputs. &#x20;

**Doc/Report Generation**

* **python-docx** for DOCX building; **reportlab** for PDF export utilities; **pandas** for bulk request parsing.  &#x20;

**HTTP & Utils**

* **requests** (Egnyte calls), **urllib.parse** (encoding), **threading** (background jobs), **logging** (observability), **datetime/time** (timestamps, delays). &#x20;

**Optional/Visualization Imports**
(Loaded but not central to the routes shown): **plotly**, **matplotlib**, **seaborn**, **PIL**, **numpy**. &#x20;

**Config & Secrets**

* Tries `credentials.py`; otherwise reads env vars: `EGNYTE_DOMAIN`, `EGNYTE_CLIENT_ID`, `EGNYTE_CLIENT_SECRET`, `EGNYTE_USERNAME`, `EGNYTE_PASSWORD`, `EGNYTE_ROOT_FOLDER`, `OPENAI_API_KEY`. Sets booleans `EGNYTE_AVAILABLE`/`OPENAI_AVAILABLE`.&#x20;

---
