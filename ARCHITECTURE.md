# 🏗️ Henry the Hire Tracker - Architecture Documentation

This document provides a technical deep-dive into the system architecture, design decisions, and implementation details.

---

## System Overview

Henry the Hire Tracker is a full-stack application combining:
- **Gmail API integration** for automated job discovery
- **Claude AI (Anthropic)** for intelligent job analysis
- **Flask REST API** for backend services
- **SQLite database** for local persistence
- **React dashboard** for job management UI
- **Chrome extension** for in-browser job analysis

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                              │
├───────────────────┬──────────────────┬──────────────────────┤
│  React Dashboard  │  Chrome Extension │   Gmail (OAuth)      │
│  (Port 5000)      │  (Side Panel)     │   (Job Alerts)       │
└────────┬──────────┴────────┬──────────┴──────────┬───────────┘
         │                   │                     │
         │  HTTP/REST        │  HTTP/REST          │  Gmail API
         │                   │                     │
         ▼                   ▼                     ▼
┌──────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                           │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Flask Application (local_app.py)           │   │
│  │                                                        │   │
│  │  ┌───────────────┐  ┌────────────────┐  ┌─────────┐ │   │
│  │  │  API Routes   │  │  Job Parsers   │  │ Config  │ │   │
│  │  │  /api/*       │  │  - LinkedIn    │  │ Loader  │ │   │
│  │  │               │  │  - Indeed      │  └─────────┘ │   │
│  │  │  - /scan      │  │  - Greenhouse  │              │   │
│  │  │  - /analyze   │  │  - Wellfound   │              │   │
│  │  │  - /capture   │  │  - WWR RSS     │              │   │
│  │  └───────────────┘  └────────────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
└────────┬────────────────────────┬──────────────────┬─────────┘
         │                        │                  │
         │  SQL Queries           │  API Calls       │  YAML Load
         │                        │                  │
         ▼                        ▼                  ▼
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────┐
│  PERSISTENCE LAYER  │  │   EXTERNAL APIs   │  │ CONFIG LAYER │
│                     │  │                   │  │              │
│  ┌───────────────┐ │  │  ┌─────────────┐ │  │ config.yaml  │
│  │  SQLite DB    │ │  │  │ Anthropic   │ │  │ .env         │
│  │  (jobs.db)    │ │  │  │ Claude API  │ │  │              │
│  │               │ │  │  └─────────────┘ │  │ User prefs   │
│  │ Tables:       │ │  │  ┌─────────────┐ │  │ Resumes      │
│  │ - jobs        │ │  │  │ Gmail API   │ │  │ Locations    │
│  │ - scan_history│ │  │  │ (OAuth 2.0) │ │  └──────────────┘
│  │ - watchlist   │ │  │  └─────────────┘ │
│  │ - followups   │ │  │  ┌─────────────┐ │
│  └───────────────┘ │  │  │ WWR RSS     │ │
│                     │  │  │ Feeds       │ │
└─────────────────────┘  │  └─────────────┘ │
                         └──────────────────┘
```

---

## Core Components

### 1. Configuration System (`config_loader.py` + `config.yaml`)

**Purpose**: Centralized user configuration without hardcoded personal data.

**Design Pattern**: Singleton with lazy initialization

```python
# Global instance cached after first load
CONFIG = get_config()

# Access user preferences
CONFIG.user_name
CONFIG.primary_locations
CONFIG.get_location_filter_prompt()
```

**Key Features**:
- YAML-based configuration for readability
- Validation on load (required fields checked)
- Dot-notation access for nested values
- Location filter generation for AI prompts
- Gitignored for privacy (config.yaml vs config.example.yaml)

**Configuration Sections**:
1. **User Profile**: Name, contact info, social links
2. **Resume Management**: File paths, variants, focus areas
3. **Job Preferences**: Locations, experience level, filters
4. **Email Scanning**: Sources, scan intervals
5. **AI Settings**: Model selection, analysis parameters

---

### 2. Flask Backend (`local_app.py`)

**Purpose**: REST API server and core business logic

**Architecture**: Monolithic Flask app with functional organization

#### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve dashboard HTML |
| `/api/jobs` | GET | List jobs with filtering |
| `/api/jobs/<id>` | PATCH | Update job status/notes |
| `/api/jobs/<id>/cover-letter` | POST | Generate cover letter |
| `/api/scan` | POST | Scan Gmail for new jobs |
| `/api/wwr` | POST | Scan WeWorkRemotely RSS |
| `/api/analyze` | POST | Run AI analysis on unscored jobs |
| `/api/analyze-instant` | POST | Instant analysis for extension |
| `/api/capture` | POST | Save job from extension |
| `/api/generate-cover-letter` | POST | Generate cover letter (extension) |
| `/api/generate-answer` | POST | Generate interview answer |
| `/api/watchlist` | GET/POST/DELETE | Manage company watchlist |

#### Job Processing Pipeline

```
1. Job Discovery
   ↓
   [Gmail Scan] or [RSS Feed] or [Extension Capture]
   ↓
   Raw job data (title, company, location, description)
   ↓

2. Parsing & Deduplication
   ↓
   [URL Cleaning] → Remove tracking parameters
   ↓
   [Job ID Generation] → SHA256 hash of (url:title:company)
   ↓
   [Duplicate Check] → Skip if job_id exists
   ↓

3. AI Filtering (Baseline)
   ↓
   [ai_filter_and_score()]
   ├─ Check location match (from config)
   ├─ Check experience level fit
   ├─ Calculate baseline score (1-100)
   └─ Decision: keep or filter
   ↓

4. Storage
   ↓
   [SQLite Insert]
   ├─ Kept jobs: is_filtered=0, baseline_score>0
   └─ Filtered jobs: is_filtered=1, stored for analytics
   ↓

5. Full Analysis (On Demand)
   ↓
   [analyze_job()]
   ├─ Detailed qualification score
   ├─ Strengths & gaps analysis
   ├─ Resume variant recommendation
   └─ Should-apply recommendation
   ↓
   [Update Database] → Store analysis JSON
   ↓

6. Application Support
   ↓
   [generate_cover_letter()]
   ↓
   [User applies, updates status]
```

---

### 3. Database Schema (SQLite)

**WAL Mode**: Write-Ahead Logging enabled for concurrent read/write

#### Table: `jobs`

Primary table for job listings with AI analysis.

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,           -- SHA256 hash (16 chars)
    title TEXT,                        -- Job title
    company TEXT,                      -- Company name
    location TEXT,                     -- Job location
    url TEXT,                          -- Clean job URL
    source TEXT,                       -- linkedin|indeed|greenhouse|etc.
    status TEXT DEFAULT 'new',         -- new|interested|applied|etc.
    score INTEGER DEFAULT 0,           -- Detailed qualification score
    baseline_score INTEGER DEFAULT 0,  -- Initial AI filter score
    analysis TEXT,                     -- JSON: strengths, gaps, recommendation
    cover_letter TEXT,                 -- Generated cover letter
    notes TEXT,                        -- User notes
    raw_text TEXT,                     -- Original job description snippet
    created_at TEXT,                   -- ISO timestamp
    updated_at TEXT,                   -- ISO timestamp
    email_date TEXT,                   -- When job alert was received
    is_filtered INTEGER DEFAULT 0,     -- 1 if filtered out by AI
    viewed INTEGER DEFAULT 0           -- 1 if user clicked "View"
);
```

**Indexes**:
- Primary key on `job_id` (unique)
- Implicit index on `status` (for filtering queries)
- Implicit index on `baseline_score` (for sorting)

#### Table: `scan_history`

Tracks Gmail scan timestamps to avoid re-processing emails.

```sql
CREATE TABLE scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_scan_date TEXT,    -- ISO timestamp of last scan
    emails_found INTEGER,   -- Number of emails processed
    created_at TEXT         -- When this scan ran
);
```

**Query Pattern**:
```sql
SELECT last_scan_date FROM scan_history
ORDER BY created_at DESC LIMIT 1
```

This provides the `after:YYYY/MM/DD` parameter for Gmail API queries, ensuring incremental scans.

#### Table: `watchlist`

Companies to monitor for future job openings.

```sql
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    url TEXT,              -- Careers page URL
    notes TEXT,            -- Why watching / when to check back
    created_at TEXT
);
```

#### Table: `followups`

Interview and application follow-up tracking (future feature).

```sql
CREATE TABLE followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT,
    subject TEXT,          -- Email subject line
    type TEXT,             -- interview|offer|rejection|update
    snippet TEXT,          -- Email preview
    email_date TEXT,
    created_at TEXT
);
```

---

### 4. AI Analysis System (Claude Integration)

**Provider**: Anthropic Claude Sonnet 4 (`claude-sonnet-4-20250514`)

**Cost Optimization**:
- Baseline filtering uses minimal tokens (~500 max)
- Full analysis only on jobs that pass baseline (~1000 max)
- Cover letters generated on-demand (~1000 max)

#### Analysis Flow

1. **Baseline Filtering** (`ai_filter_and_score()`)
   - **Input**: Job + Resume + Config (location prefs, experience level)
   - **Prompt**: Location filter rules, seniority matching
   - **Output**: `{keep: bool, baseline_score: 1-100, filter_reason: str}`
   - **Token Cost**: ~400-500 tokens per job

2. **Full Analysis** (`analyze_job()`)
   - **Input**: Job + Resume
   - **Prompt**: Detailed skill matching, gap analysis, resume variant selection
   - **Output**: `{qualification_score, should_apply, strengths[], gaps[], recommendation, resume_to_use}`
   - **Token Cost**: ~800-1000 tokens per job

3. **Cover Letter Generation** (`generate_cover_letter()`)
   - **Input**: Job + Resume + Previous Analysis
   - **Prompt**: 3-4 paragraphs, <350 words, cite actual resume content
   - **Output**: Formatted cover letter text
   - **Token Cost**: ~700-900 tokens per letter

4. **Interview Answer Generation** (`api_generate_answer()`)
   - **Input**: Question + Job + Resume + Analysis
   - **Prompt**: 2-3 paragraph answer using STAR method
   - **Output**: Natural conversational answer
   - **Token Cost**: ~600-800 tokens per answer

**AI Safety Features**:
- Strict accuracy enforcement (only cite actual resume content)
- JSON-only responses to prevent hallucination
- Error handling with fallback scores
- Rate limiting (handled by Anthropic SDK)

---

### 5. Gmail Integration

**Protocol**: OAuth 2.0 with Gmail API v1

**Scope**: `https://www.googleapis.com/auth/gmail.readonly` (read-only)

#### Authentication Flow

```
1. Check for token.json
   ├─ If exists and valid → use cached credentials
   └─ If missing/expired → initiate OAuth flow
      ↓
2. OAuth Flow
   ├─ Load credentials.json (from Google Cloud Console)
   ├─ Open browser for user consent
   ├─ User grants Gmail read permission
   └─ Save token.json for future use
   ↓
3. API Ready
```

#### Email Scanning Strategy

**Incremental Scanning**: Only process emails after last scan timestamp

```python
# Get last scan from database
last_scan = SELECT last_scan_date FROM scan_history ORDER BY created_at DESC LIMIT 1

# Query Gmail
query = f'from:jobs-noreply@linkedin.com after:{last_scan}'
```

**Job Board Queries**:
- `from:jobs-noreply@linkedin.com`
- `from:jobalerts-noreply@linkedin.com`
- `from:noreply@indeed.com`
- `from:alert@indeed.com`
- `from:no-reply@us.greenhouse-jobs.com`
- `from:team@hi.wellfound.com`

**Message Processing**:
1. Fetch message IDs matching query
2. For each message:
   - Get full payload with Gmail API
   - Extract HTML body (base64 decode)
   - Parse with BeautifulSoup
   - Route to appropriate parser (LinkedIn/Indeed/etc.)
   - Extract job details
3. Deduplicate by job_id
4. Pass to AI filter
5. Store results

---

### 6. Job Parsers

Each job board has a custom HTML parser due to different email formats.

#### LinkedIn Parser (`parse_linkedin_jobs()`)

**Email Format**: Job cards with title+company combined

**Parsing Strategy**:
- Find links matching `/jobs/view/\d{10}`
- Extract text from link and nearby elements
- Split "TitleCompany" using regex for camelCase boundaries
- Parse location from delimiter (`·`)

**Challenges**:
- Title and company concatenated without clear delimiter
- Must filter out UI elements ("See all jobs", "Settings")

#### Indeed Parser (`parse_indeed_jobs()`)

**Email Format**: Table-based layout

**Parsing Strategy**:
- Find links with `jk=` or `vjk=` parameter
- Extract job details from parent `<td>` or `<div>`
- Parse title, company (next line), location (line after)

#### Greenhouse/Wellfound/WWR Parsers

Similar pattern-matching approaches tailored to each platform's HTML structure.

---

### 7. Chrome Extension

**Type**: Manifest V3 side panel extension

**Components**:
- `manifest.json`: Extension config and permissions
- `sidepanel.html`: UI layout
- `sidepanel.js`: Main logic (tab switching, API calls)
- `background.js`: Service worker for side panel management
- `popup.html/js`: Simple capture extension (legacy)

#### Communication Flow

```
[Job Website] → [Extension Content] → [Side Panel UI]
                                           ↓
                                    HTTP POST to localhost:5000
                                           ↓
                                    [Flask Backend]
                                           ↓
                                    [Claude AI Analysis]
                                           ↓
                                    Response JSON
                                           ↓
                                    [Side Panel Display]
```

**Features**:
- Auto-fill job title and URL from current tab
- Instant AI analysis (no database save required)
- Cover letter generation for current job
- Interview question practice with job context
- Save to tracker with "Capture" button

---

## Design Decisions

### Why SQLite?

✅ **Pros**:
- Zero configuration, embedded database
- Perfect for single-user local application
- File-based (easy backup: copy `jobs.db`)
- ACID transactions
- Full SQL support

❌ **Cons**:
- Not suitable for multi-user deployment
- Limited concurrent writes (solved with WAL mode)
- No built-in replication

**Decision**: SQLite is ideal for local job tracking. For AWS deployment, switch to DynamoDB (see `template.yaml`).

### Why Flask over FastAPI?

✅ **Flask**:
- Simpler for rendering embedded HTML (dashboard)
- Mature ecosystem, extensive documentation
- Lower learning curve for contributors
- Built-in Jinja2 templating

**Decision**: Flask's simplicity and HTML rendering capabilities outweigh FastAPI's async benefits for this use case.

### Why Configuration File over Database?

User preferences stored in `config.yaml` rather than database.

✅ **Pros**:
- Human-readable and editable
- Version control friendly (with .example file)
- No schema migrations needed for preference changes
- Easy to share sanitized config as template

**Decision**: Config file provides better user experience for a personal tool.

### Why Claude over GPT-4?

✅ **Claude Sonnet 4 Advantages**:
- Superior instruction following (less prone to hallucination)
- Better at structured JSON outputs
- Excellent at nuanced analysis tasks
- Competitive pricing

**Decision**: Claude's accuracy and JSON reliability are critical for job analysis quality.

---

## Security Considerations

### API Keys
- ✅ Stored in `.env` (gitignored)
- ✅ Loaded via `python-dotenv`
- ❌ Never hardcoded in source
- ❌ Never logged or exposed in responses

### Gmail OAuth
- ✅ Read-only scope (can't send/delete emails)
- ✅ Token stored locally (`token.json`, gitignored)
- ✅ Credentials file user-provided (not in repo)

### Personal Data
- ✅ Resumes gitignored
- ✅ Config with personal info gitignored
- ✅ Database gitignored (contains application history)
- ✅ Template files provided for new users

### SQL Injection
- ✅ Parameterized queries used throughout
- ✅ No string concatenation for SQL

### CORS
- ✅ Enabled for localhost:5000 (extension access)
- ⚠️ Production should restrict origins

---

## Scaling Considerations

**Current Architecture**: Local single-user deployment

**For Multi-User SaaS**:

1. **Database**: SQLite → PostgreSQL or DynamoDB
2. **Authentication**: Add user auth (OAuth, JWT)
3. **Session Management**: Flask sessions or Redis
4. **API Rate Limiting**: Prevent abuse of Claude API
5. **Background Jobs**: Celery for async email scanning
6. **Caching**: Redis for AI analysis results
7. **Deployment**: Docker + Kubernetes or AWS Lambda

**Cost Optimization for Scale**:
- Cache AI analysis results (same job, multiple users)
- Batch processing for baseline filtering
- User tier limits (free: 10 jobs/day, paid: unlimited)

---

## Performance Characteristics

### Email Scanning
- **Speed**: ~2-5 seconds for 100 emails
- **Bottleneck**: Gmail API rate limits (250 quota units/user/second)
- **Optimization**: Incremental scans (only new emails)

### AI Analysis
- **Baseline Filter**: ~1-2 seconds per job
- **Full Analysis**: ~2-4 seconds per job
- **Bottleneck**: Anthropic API latency
- **Optimization**: Parallel processing for batch analysis (future)

### Database Queries
- **Job List**: <10ms for typical query (100-500 jobs)
- **Insert**: <5ms per job
- **Bottleneck**: None (SQLite is fast for this scale)

---

## Testing Strategy

**Current**: Manual testing

**Recommended for Production**:

1. **Unit Tests**:
   - Parser functions (LinkedIn, Indeed, etc.)
   - Config loader validation
   - URL cleaning logic

2. **Integration Tests**:
   - API endpoint responses
   - Database operations
   - Gmail API mocking

3. **E2E Tests**:
   - Extension → Backend → Database flow
   - Dashboard interactions (Playwright/Selenium)

4. **AI Quality Tests**:
   - Baseline scoring consistency
   - Analysis output format validation
   - Cover letter quality checks (manual review)

---

## Future Enhancements

### Phase 2 Features
- [ ] Email notifications for high-scoring jobs
- [ ] Application deadline tracking
- [ ] Salary range extraction and filtering
- [ ] Company research integration (Crunchbase API)
- [ ] Interview preparation flashcards

### Phase 3 Features
- [ ] Multi-user deployment (AWS Lambda + DynamoDB)
- [ ] Mobile app (React Native)
- [ ] Job board scraping (beyond email alerts)
- [ ] Application auto-fill browser extension
- [ ] AI-powered application follow-ups

### Infrastructure
- [ ] Docker containerization
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Automated testing
- [ ] Monitoring and observability (Sentry, DataDog)

---

## References

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Chrome Extension Manifest V3](https://developer.chrome.com/docs/extensions/mv3/)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)

---

**Last Updated**: December 2025
