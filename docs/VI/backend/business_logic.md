# Business Logic - Research Assistant Framework

## Use Cases

### UC1: Theo dõi keyword nghiên cứu

**Actor**: Researcher

**Precondition**: User đã đăng ký account

**Flow**:
1. User tạo Source mới: `type=keyword`, `value="Network Intrusion Detection"`
2. User set schedule: "Every Monday 8am"
3. Hệ thống lưu vào DB
4. Cronjob trigger Ingestion Service
5. Searcher query ArXiv với keyword
6. Analyzer filter papers theo date range và relevance
7. Summarizer tạo insights cho mỗi paper
8. Papers được lưu vào DB

**Postcondition**: User có danh sách papers mới được theo dõi

---

### UC2: Tạo báo cáo định kỳ

**Actor**: Researcher

**Precondition**: Đã có ít nhất 10 papers trong DB cho topic

**Flow**:
1. User request: "Tạo báo cáo tuần này cho topic X"
2. System query DB: papers trong 7 ngày qua, topic X, `is_relevant=true`
3. Clusterer phân nhóm papers theo semantic similarity
4. LLM đặt tên cho mỗi cluster (Research Direction)
5. Writer tạo báo cáo Markdown:
   - Overview section
   - Mỗi cluster một section với summary + paper list
6. Delivery service send email cho user

**Postcondition**: User nhận được báo cáo qua email

---

### UC3: Khám phá papers liên quan

**Actor**: Researcher

**Precondition**: User đang đọc 1 paper cụ thể

**Flow**:
1. User click "Find similar papers" trên paper A
2. System lấy embedding của paper A từ Vector DB
3. Vector search tìm top 10 papers gần nhất (cosine similarity)
4. Filter: chỉ hiển thị papers cùng topic hoặc published trong 2 năm gần
5. Hiển thị kết quả sorted by similarity score

**Postcondition**: User thấy danh sách papers tương tự

---

## Core Business Rules

### BR1: Relevance Scoring
**Rule**: Paper chỉ được lưu vào DB nếu `relevance_score >= 7`

**Logic**:
```python
def evaluate_relevance(paper: Paper, topic: Topic) -> float:
    """
    LLM scoring với prompt:
    'Topic: {topic.description}
     Paper Abstract: {paper.abstract}
     Rate relevance from 0-10.
     Return JSON: {score: float, reasoning: str}'
    """
    response = llm.generate(prompt)
    score = response['score']
    
    # Save evaluation for audit
    db.save(PaperEvaluation(
        paper_id=paper.id,
        topic_id=topic.id,
        score=score,
        reasoning=response['reasoning']
    ))
    
    return score >= 7  # Threshold
```

---

### BR2: Deduplication Strategy
**Rule**: Không lưu duplicate papers

**Logic**:
```python
def create_fingerprint(paper: Paper) -> str:
    """Generate unique fingerprint for dedup"""
    # Normalize
    title = paper.title.lower().strip()
    authors = sorted([a.lower() for a in paper.authors])
    
    # Hash
    content = f"{title}|{'|'.join(authors)}"
    return hashlib.sha256(content.encode()).hexdigest()

def is_duplicate(paper: Paper) -> bool:
    fingerprint = create_fingerprint(paper)
    return db.exists("papers", fingerprint=fingerprint)
```

**Edge Cases**:
- Papers với title khác nhau nhưng cùng DOI → Dùng DOI làm fingerprint nếu có
- Preprint vs Published version → Accept both, link bằng `arxiv_id`

---

### BR3: Time Window Filtering
**Rule**: Chỉ process papers trong range `[date_from, date_to]`

**Logic**:
```python
def filter_by_time(papers: List[Paper], report: Report) -> List[Paper]:
    return [
        p for p in papers
        if report.date_from <= p.published_date <= report.date_to
    ]
```

**Configuration**:
- Default: Last 7 days
- User customizable: 1 day to 1 year

---

### BR4: Clustering Threshold
**Rule**: Cluster phải có ít nhất `min_papers` members

**Logic**:
```python
MIN_CLUSTER_SIZE = 3

def cluster_papers(papers: List[Paper]) -> List[Cluster]:
    embeddings = [p.embedding for p in papers]
    
    # HDBSCAN auto-determines cluster count
    clusterer = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE)
    labels = clusterer.fit_predict(embeddings)
    
    # Group by label
    clusters = defaultdict(list)
    for paper, label in zip(papers, labels):
        if label != -1:  # -1 = noise/outliers
            clusters[label].append(paper)
    
    # Generate cluster metadata
    result = []
    for cluster_id, members in clusters.items():
        name = llm_generate_cluster_name(members)
        result.append(Cluster(
            name=name,
            paper_ids=[p.id for p in members]
        ))
    
    return result
```

---

### BR5: Summary Structure
**Rule**: Mỗi paper summary phải có 3 fields: Problem, Method, Result

**Prompt Template**:
```
You are a research paper analyzer. Extract the following from the abstract:

Abstract: {abstract}

Return JSON only:
{
  "problem": "What problem does this paper address?",
  "method": "What is the proposed approach/method?",
  "result": "What are the key results/findings?",
  "keywords": ["keyword1", "keyword2", ...]
}

Be concise. Each field max 100 words.
```

**Validation**:
```python
def validate_summary(summary: dict) -> bool:
    required = ["problem", "method", "result"]
    return all(k in summary and len(summary[k]) > 10 for k in required)
```

---

## Workflow Scheduling

### Ingestion Jobs

```python
# Cron schedules
SCHEDULES = {
    "daily": "0 8 * * *",      # 8am every day
    "weekly": "0 8 * * 1",     # 8am Monday
    "monthly": "0 8 1 * *",    # 8am 1st of month
}

@celery.task
def run_ingestion_for_source(source_id: uuid):
    source = db.get(Source, source_id)
    
    # Route based on type
    if source.type == "keyword":
        papers = searcher.search(source.value)
    elif source.type == "rss":
        papers = collector.fetch_rss(source.value)
    
    # Process
    for paper in papers:
        if is_duplicate(paper):
            continue
        
        analyzer.process(paper)
    
    # Update last run
    source.last_run = datetime.now()
    db.save(source)
```

### Report Generation

```python
@celery.task
def generate_weekly_report(user_id: uuid, topic_id: uuid):
    # Date range: last 7 days
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=7)
    
    # Query relevant papers
    papers = db.query(Paper).join(PaperEvaluation).filter(
        PaperEvaluation.topic_id == topic_id,
        PaperEvaluation.is_relevant == True,
        Paper.published_date.between(date_from, date_to)
    ).all()
    
    if len(papers) < 3:
        # Not enough data
        notify_user(user_id, "Not enough new papers this week")
        return
    
    # Cluster
    clusters = clusterer.cluster(papers)
    
    # Write report
    report = writer.generate(
        topic_id=topic_id,
        clusters=clusters,
        date_from=date_from,
        date_to=date_to
    )
    
    # Deliver
    delivery.send_email(user_id, report.content)
    db.save(report)
```

---

## Error Handling

### EH1: API Rate Limiting
**Scenario**: ArXiv API returns 429

**Logic**:
```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
def fetch_arxiv(query: str) -> List[Paper]:
    response = requests.get(ARXIV_API, params={"query": query})
    
    if response.status_code == 429:
        # Exponential backoff via @retry decorator
        raise Exception("Rate limited")
    
    return parse_response(response)
```

---

### EH2: LLM Hallucination
**Scenario**: LLM returns invalid JSON or nonsense summary

**Logic**:
```python
def summarize_with_validation(abstract: str) -> dict:
    for attempt in range(3):
        summary = llm.generate(prompt)
        
        try:
            parsed = json.loads(summary)
            if validate_summary(parsed):
                return parsed
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON, retry {attempt + 1}")
            continue
    
    # Fallback: use abstract as-is
    return {
        "problem": "Unable to extract",
        "method": "Unable to extract",
        "result": abstract[:200]
    }
```

---

### EH3: No Clusters Found
**Scenario**: Papers quá ít hoặc quá diverse, clustering fail

**Logic**:
```python
def safe_cluster(papers: List[Paper]) -> List[Cluster]:
    if len(papers) < MIN_CLUSTER_SIZE:
        # Create single "Miscellaneous" cluster
        return [Cluster(name="Various Topics", paper_ids=[p.id for p in papers])]
    
    clusters = cluster_papers(papers)
    
    if len(clusters) == 0:
        # All papers are outliers
        return [Cluster(name="Uncategorized", paper_ids=[p.id for p in papers])]
    
    return clusters
```
