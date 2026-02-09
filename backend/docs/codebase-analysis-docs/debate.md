# DEBATE.md — Agentic Research (Citation-first) Workflow
Version: 1.0
Date: 2026-02-09
Owner: Research Assistant Backend
Goal: From user query/keywords → comprehensive related work corpus → evidence-grounded synthesis report with citations + future directions.

---

## 1) Problem & Success Criteria

### Problem statement
Build an agentic research workflow that starts from an initial user query/keywords and produces:
- A broad, deduplicated corpus of relevant papers
- A citation-grounded report (every key claim must be attributable to evidence spans in source papers)
- A “future research directions” section derived from extracted limitations/gaps, not free-form hallucination

### Success criteria (acceptance)
- (Citations) 100% of “key claims” in the final report have ≥1 citation pointing to an evidence span (paper + locator).  
- (Auditability) For any claim, system can return: `claim_text → evidence_spans[] → (paper_id, snippet, locator, url)`.  
- (Usability) End user can run one-shot by default; system only asks approval at high-cost/high-risk gates (HITL approval-gate pattern). [web:32]  
- (Reproducibility) Each run is reproducible: store `plan_id`, tool args, model/version, prompt version, paper hashes.

### Non-goals (v1)
- Perfect PDF parsing for all publishers
- Full systematic-review PRISMA compliance (but workflow should be “systematic-like”: screening + extraction + synthesis)
- Multi-node distributed execution (can be future)

---

## 2) Proposed Workflow (Citation-first)

### High-level phases
A. Clarify (minimal)
B. Plan
C. Collect + Deduplicate
D. Title/Abstract Screening (include/exclude + reason)
E. Full-text Loading (budgeted)
F. Evidence Extraction (required)
G. Thematic Structuring (cluster/taxonomy)
H. Grounded Synthesis Report + Future Directions
I. Citation Audit (evaluator gate)
J. Publish (store artifacts, indexes)

### Why insert Screening + Evidence Extraction?
Structured literature review workflows commonly separate: title/abstract screening → full-text screening → data extraction, to keep traceability and reduce verification burden. [web:31]

### Detailed phase spec

#### A) Clarify (minimal)
Input: user message (query + optional keywords/time window)
Output: `ResearchRequest` finalized
Rules:
- Ask at most 1–2 questions ONLY if missing: time window, domain scope, budget constraints (max_papers, max_pdf), output language.

#### B) Plan
Output: `ResearchPlan` with:
- collection strategy (sources + queries)
- budgets (max_papers_total, max_pdf_download, token_budget)
- approval gates (see HITL section)

#### C) Collect + Deduplicate
- Collect from: arXiv, HF trending (optional), custom URLs
- Normalize metadata: title/authors/date/pdf_url
- Dedup:
  1) arxiv_id exact
  2) fingerprint title+first_author
  3) fuzzy title similarity threshold

Artifacts:
- `CorpusRaw[]`
- `DedupMap` (raw_id → canonical_id)

#### D) Title/Abstract Screening (include/exclude + reason)
Objective: broad recall but controlled noise.
Method:
- Hybrid rule + LLM classifier
- Output per paper:
  - include_bool
  - reason_code (out_of_scope, survey_only, missing_eval, etc.)
  - short rationale (1–2 lines)

Artifact:
- `ScreeningRecord[]`

#### E) Full-text Loading (budgeted)
Policy:
- Load PDFs for top-K or score≥threshold, but always under `max_pdf_download`.
- Cache PDF content + store `pdf_hash` to detect drift.

Artifact:
- `PaperFullText` (paper_id → full_text, pdf_hash, parse_status)

#### F) Evidence Extraction (required, schema-driven)
This is the core step enabling citation-first writing.
For each included paper with full text (or abstract-only fallback):
Extract a structured “study card”:
- Problem / Task
- Method
- Dataset(s)
- Metric(s)
- Result(s)
- Limitation(s)
- Cost/efficiency notes (if present)

Each field MUST produce ≥1 `EvidenceSpan`:
- locator: page number or section heading + char offsets (best-effort)
- snippet: short quote (<= 300 chars)
- confidence

Artifacts:
- `StudyCard[]`
- `EvidenceSpan[]`

#### G) Thematic structuring
- Cluster `StudyCard` embeddings into themes (task-based / method-based / eval-based).
- Build a taxonomy matrix:
  - Rows: themes
  - Columns: datasets/metrics/method families

Artifacts:
- `Cluster[]`
- `TaxonomyMatrix`

#### H) Grounded synthesis report
Write Markdown with strict constraints:
- Any “claim” in report must reference `EvidenceSpan` ids.
- If evidence insufficient: state “insufficient evidence in corpus”.

Report sections (suggested):
1) Scope & search strategy (brief)
2) Theme map (clusters)
3) Per-theme synthesis (what works, why)
4) Comparative table (datasets/metrics/results)
5) Limitations across the field (aggregated)
6) Future research directions (gap-driven; see below)

#### Future directions (gap-driven)
Compute “gaps” from extracted limitations + taxonomy holes:
- Frequently mentioned limitations
- Contradictory results across papers (same dataset/metric, different outcomes)
- Underexplored combinations (theme × dataset × metric)
Then generate:
- Open problems (from limitation clusters)
- Research opportunities (from taxonomy holes)
- Concrete next experiments (benchmarking suggestions)

Constraint:
- Each direction must cite at least one limitation evidence span.

#### I) Citation audit (evaluator gate)
Before returning report:
- Randomly sample N key claims (or all claims above a salience threshold)
- Verify:
  - claim has citations
  - cited evidence spans exist
  - snippet semantically supports claim (LLM judge + heuristic)

If fail:
- auto-repair loop: rewrite claim more cautiously OR fetch more evidence OR mark as uncertain.

#### J) Publish
Store:
- Plan + tool args
- Corpus (raw + included)
- Evidence artifacts
- Final report (Markdown)
- Vector index entries (for later retrieval/Q&A)

---

## 3) HITL (Human-in-the-loop) Gates

### Principle
Only ask for approval when action has meaningful cost/risk; provide full context (tool + args + estimated cost); persist pending approvals. [web:32]

### Approval gates (v1)
- Gate 1: “Download many PDFs” (when `max_pdf_download` > threshold or pdf sources include unknown domains)
- Gate 2: “Crawl external URLs” (non-arxiv/hf)
- Gate 3: “High token budget” (estimated tokens > budget threshold)

UX:
- Default: auto-run until end of Title/Abstract Screening, then show “included set preview + cost estimate”, request approval to proceed with PDF + Evidence Extraction.

---

## 4) Data Contracts (Schemas)

### Core entities (minimal additions)
#### Paper
- paper_id
- source (arxiv|hf|url)
- title, authors, published_date
- abstract
- pdf_url
- url
- status (RAW|SCREENED|FULLTEXT|EXTRACTED|REPORTED)
- hashes: metadata_hash, pdf_hash(optional)

#### ScreeningRecord
- paper_id
- include: bool
- reason_code
- rationale_short
- scored_relevance (0–10) optional

#### EvidenceSpan
- span_id
- paper_id
- field (problem|method|dataset|metric|result|limitation|other)
- snippet (short)
- locator: { page:int?, section:str?, char_start:int?, char_end:int? }
- confidence: float
- source_url (pdf_url)

#### StudyCard
- paper_id
- fields: problem, method, datasets[], metrics[], results[], limitations[]
- evidence_span_ids[] (must cover all populated fields)

#### Claim
- claim_id
- claim_text
- evidence_span_ids[]
- theme_id
- salience_score
- uncertainty_flag

### Storage
- MongoDB: Papers, ScreeningRecords, EvidenceSpan, StudyCards, Claims, Clusters, Reports, Plans
- Redis: session + checkpoint + tool_cache + pdf_cache
- Qdrant: embeddings for Paper/StudyCard/Claim for retrieval

---

## 5) Implementation Plan (Tasks + Milestones)

### Milestone 1 — Evidence layer foundation
- Add `EvidenceSpan` + `StudyCard` models + repositories
- Implement PDF locator strategy (page-based if parser supports; else section/offset best-effort)
- Implement Evidence Extraction prompt + strict JSON schema output

### Milestone 2 — Screening + approval gates
- Implement Screening step (abstract-level) with include/exclude reasons
- Implement HITL gates (pending approval state + resume), following approval-gate best practices (context, timeout, audit trail). [web:32]

### Milestone 3 — Grounded report writer
- Implement Claim graph generation:
  - convert StudyCards → Claims (atomic, citable)
- Writer uses Claims only; refuses to write uncited assertions
- Add citation audit + auto-repair loop

### Milestone 4 — Future directions module
- Implement gap miner (limitations clustering + taxonomy holes)
- Generate future directions with mandatory evidence backing

### Tests (must-have)
- Unit: dedup, schema validation, JSON repair
- Integration: end-to-end run with 20 papers; verify:
  - all claims have evidence spans
  - report renders Markdown without broken citations
- Regression: “LLM returns markdown-wrapped JSON” → parser still succeeds

### Telemetry (must-have)
- Per phase duration, token usage estimate, number of included papers
- PDF download counts + cache hit rates
- Citation audit pass rate

---

## Appendix — Notes for prompts
- Prefer schema-constrained JSON outputs for extraction/screening.
- Extraction prompt should force: “If you cannot find evidence, output empty field + no span”.
- Writer prompt must include: “You can only use provided Claims; every paragraph must cite claim_ids”.

