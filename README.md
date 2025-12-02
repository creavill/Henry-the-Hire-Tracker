# 🎩 Henry the Hire Tracker

**AI-Powered Job Search Assistant** that automatically scans your Gmail for job alerts, analyzes opportunities against your resume using Claude AI, and helps you track applications with intelligent insights.

> **Portfolio-Ready:** Fully configurable for any user - no hardcoded personal information. Ready to showcase or share!

---

## ✨ Features

### 🤖 AI-Powered Analysis
- **Smart Filtering**: Automatically filters jobs by location preferences and experience level
- **Qualification Scoring**: Claude AI scores each job 1-100 based on your resume fit
- **Resume Matching**: Recommends which resume variant to use for each application
- **Cover Letter Generation**: Creates tailored cover letters citing actual resume experience
- **Interview Prep**: Generates practice answers to common interview questions

### 📧 Automated Job Discovery
- **Gmail Integration**: Scans LinkedIn, Indeed, Greenhouse, and Wellfound job alerts
- **WeWorkRemotely RSS**: Pulls remote job opportunities automatically
- **Smart Deduplication**: Removes tracking parameters to prevent duplicate entries
- **Follow-up Detection**: Identifies interview and offer emails (coming soon)

### 🎯 Intelligent Tracking
- **Web Dashboard**: Beautiful UI for managing your job pipeline
- **Status Management**: Track applications through "new → interested → applied → interviewing"
- **Company Watchlist**: Monitor companies not currently hiring
- **Weighted Scoring**: Jobs sorted by 70% qualification + 30% recency

### 🔧 Chrome Extension (Henry Assistant)
- **Instant Analysis**: Analyze any job posting without leaving the page
- **Side Panel UI**: Clean interface that works on LinkedIn, Indeed, and more
- **One-Click Actions**: Generate cover letters and interview answers on the fly
- **Auto-Capture**: Save jobs directly to your tracker with one click

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+ (for frontend development)
- Gmail account with job alerts enabled
- [Anthropic API key](https://console.anthropic.com/) (Claude AI)
- Google Cloud project with Gmail API enabled

### Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/Henry-the-Hire-Tracker.git
cd Henry-the-Hire-Tracker
```

#### 2. Install Python Dependencies
```bash
pip install -r requirements-local.txt
```

#### 3. Configure Your Profile
```bash
# Copy example configuration
cp config.example.yaml config.yaml

# Edit config.yaml with your information
nano config.yaml  # or use your preferred editor
```

Fill in:
- Your name, email, phone, location
- LinkedIn, GitHub, portfolio URLs
- Location preferences (cities, remote preferences)
- Experience level and job preferences

#### 4. Add Your Resumes
```bash
# Use the templates or add your own
cp resumes/templates/backend_developer_resume_template.txt resumes/backend_developer_resume.txt

# Edit with your actual experience
nano resumes/backend_developer_resume.txt
```

Update `config.yaml` to reference your resume files.

#### 5. Set Up Gmail API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the **Gmail API**
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials file as `credentials.json` in the project root

#### 6. Set Up Environment Variables
```bash
# Copy example env file
cp .env.example .env

# Add your Anthropic API key
echo "ANTHROPIC_API_KEY=your_api_key_here" > .env
```

#### 7. Run the Application
```bash
python local_app.py
```

Visit **http://localhost:5000** to see your dashboard!

---

## 📖 Usage Guide

### Dashboard Workflow

1. **Scan Gmail**
   - Click "📧 Scan Gmail" button
   - First run will ask for Gmail permissions
   - Jobs are automatically filtered by location and experience level

2. **Review Jobs**
   - Jobs appear sorted by weighted score (qualification + recency)
   - Green badges (80+): Strong matches
   - Blue badges (60-79): Good matches
   - Yellow badges (40-59): Partial matches

3. **Analyze All**
   - Click "🤖 Analyze All" for detailed AI analysis
   - Provides strengths, gaps, and recommendations
   - Auto-marks high-scoring jobs as "interested"

4. **Track Applications**
   - Update status: new → interested → applied → interviewing
   - Add notes for each application
   - Mark jobs as viewed to reduce clutter

5. **Generate Cover Letters**
   - Expand job details and click "Generate Cover Letter"
   - AI creates tailored letter based on your resume and the job requirements
   - Copy and customize as needed

### Chrome Extension Setup

1. **Install Extension**
   ```bash
   # In Chrome, go to chrome://extensions/
   # Enable "Developer mode"
   # Click "Load unpacked"
   # Select the "extension" folder
   ```

2. **Use Extension**
   - Navigate to a job posting (LinkedIn, Indeed, etc.)
   - Click the extension icon or open side panel
   - Paste job description (or it auto-fills)
   - Click "🤖 Analyze" for instant AI analysis

3. **Extension Features**
   - **Analyze Tab**: Get instant qualification scoring
   - **Apply Tab**: Generate cover letter for current job
   - **Questions Tab**: Practice common interview questions

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Chrome Ext     │──────┐
│  (Side Panel)   │      │
└─────────────────┘      │
                         │
┌─────────────────┐      │      ┌──────────────────┐
│  Gmail API      │──────┼─────▶│  Flask Backend   │
│  (Job Alerts)   │      │      │  (local_app.py)  │
└─────────────────┘      │      └──────────────────┘
                         │              │
┌─────────────────┐      │              │
│  WeWorkRemotely │──────┘              │
│  RSS Feeds      │                     │
└─────────────────┘                     │
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                   ┌────▼─────┐                  ┌──────▼───────┐
                   │ Claude AI │                  │   SQLite DB   │
                   │ Analysis  │                  │  (jobs.db)    │
                   └──────────┘                  └──────────────┘
                                                         │
                        ┌────────────────────────────────┘
                        │
                   ┌────▼─────┐
                   │  React    │
                   │ Dashboard │
                   │  (Vite)   │
                   └──────────┘
```

### Components

- **Flask Backend** (`local_app.py`): Core API server, handles Gmail scanning, AI analysis, job storage
- **Configuration System** (`config.yaml`): User preferences, location filters, resume paths
- **Chrome Extension** (`extension/`): Browser integration for instant job analysis
- **React Dashboard** (`App.jsx`, `main.jsx`): Web UI for tracking applications
- **SQLite Database** (`jobs.db`): Local storage for jobs, scans, watchlist

### Data Flow

1. **Job Discovery**: Gmail API or RSS feeds → Email parser → Job extraction
2. **AI Filtering**: Raw job data → Claude AI → Baseline score + filter decision
3. **Storage**: Filtered jobs → SQLite database → Dashboard display
4. **Analysis**: User requests → Full AI analysis → Detailed scoring + recommendations
5. **Actions**: User interaction → Cover letter generation / Status updates → Database

---

## 📂 Project Structure

```
Henry-the-Hire-Tracker/
├── local_app.py                 # Main Flask application
├── config_loader.py             # Configuration management
├── config.yaml                  # User configuration (gitignored)
├── config.example.yaml          # Configuration template
├── .env                         # API keys (gitignored)
├── .env.example                 # Environment template
├── requirements-local.txt       # Python dependencies
├── jobs.db                      # SQLite database (auto-created)
│
├── resumes/                     # Your resume files (gitignored)
│   ├── backend_developer_resume.txt
│   ├── cloud_engineer_resume.txt
│   ├── fullstack_developer_resume.txt
│   └── templates/               # Resume templates for new users
│       ├── backend_developer_resume_template.txt
│       ├── cloud_engineer_resume_template.txt
│       ├── fullstack_developer_resume_template.txt
│       └── README.md
│
├── extension/                   # Chrome extension (Henry Assistant)
│   ├── manifest.json
│   ├── sidepanel.html
│   ├── sidepanel.js
│   ├── background.js
│   ├── popup.html
│   ├── popup.js
│   └── icons/
│
├── frontend/                    # React dashboard (optional dev setup)
│   ├── App.jsx
│   ├── main.jsx
│   ├── index.html
│   └── vite.config.js
│
├── template.yaml                # AWS SAM deployment config (optional)
└── README.md                    # This file
```

---

## ⚙️ Configuration

### `config.yaml` Structure

```yaml
user:
  name: "Your Name"
  email: "you@example.com"
  location: "Your City, State"

resumes:
  files:
    - "resumes/backend_developer_resume.txt"
    - "resumes/cloud_engineer_resume.txt"
  variants:
    backend:
      focus: "Backend development, APIs, distributed systems"
      file: "resumes/backend_developer_resume.txt"

preferences:
  locations:
    primary:
      - name: "Remote"
        type: "remote"
        score_bonus: 100
      - name: "San Francisco, CA"
        type: "city"
        score_bonus: 95
        includes: ["Oakland", "Berkeley", "San Jose"]

  experience_level:
    min_years: 2
    max_years: 7
    current_level: "mid"

  filters:
    exclude_keywords: ["Director", "VP", "Chief"]
    min_baseline_score: 30
    auto_interest_threshold: 75
```

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=your_claude_api_key

# Optional
FLASK_ENV=development
DATABASE_PATH=./jobs.db
```

---

## 🤝 Contributing

This project is designed to be easily customizable! Here's how to contribute:

### Adding New Job Boards

1. Add parser function in `local_app.py`:
   ```python
   def parse_jobboard_jobs(html, email_date):
       # Extract job data
       return jobs_list
   ```

2. Add email query in `scan_emails()`:
   ```python
   f'from:jobs@jobboard.com after:{after_date}'
   ```

### Customizing AI Prompts

Edit prompts in these functions:
- `ai_filter_and_score()`: Location filtering and baseline scoring
- `analyze_job()`: Detailed qualification analysis
- `generate_cover_letter()`: Cover letter generation
- `api_generate_answer()`: Interview answer generation

### Adding Features

- **Database**: Add columns/tables in `init_db()`
- **API**: Add Flask routes in the `# ============== Flask Routes ==============` section
- **Dashboard**: Edit `DASHBOARD_HTML` or the React frontend in `frontend/`
- **Extension**: Modify `extension/sidepanel.js` for new functionality

---

## 🐛 Troubleshooting

### "Missing credentials.json"
Download OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/). Make sure Gmail API is enabled.

### "No resume files found"
Add `.txt` or `.md` resume files to `resumes/` and configure paths in `config.yaml`.

### "ANTHROPIC_API_KEY not set"
Add your API key to `.env`:
```bash
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

### Gmail Authentication Errors
Delete `token.json` and re-run to re-authenticate:
```bash
rm token.json
python local_app.py
```

### No Jobs Found
- Check that you have job alert emails in your inbox
- Try increasing `email.initial_scan_days` in `config.yaml`
- Verify email sources in Gmail (LinkedIn, Indeed alerts enabled)

### Extension Not Working
- Ensure local_app.py is running on port 5000
- Check browser console for errors (F12)
- Verify CORS is enabled in Flask (it should be by default)

---

## 🚀 Deployment (Optional)

### AWS Serverless Deployment

The project includes AWS SAM templates for production deployment:

```bash
# Build and deploy
sam build
sam deploy --guided
```

This creates:
- Lambda functions for email scanning and AI analysis
- DynamoDB table for job storage
- S3 bucket for resume storage
- API Gateway for web access
- CloudFront CDN for dashboard

See `template.yaml` for full infrastructure configuration.

---

## 📊 Tech Stack

### Backend
- **Python 3.12**: Core application logic
- **Flask**: Web server and API
- **SQLite**: Local database (DynamoDB for AWS)
- **Claude Sonnet 4**: AI analysis via Anthropic API
- **Gmail API**: Email scanning via Google OAuth

### Frontend
- **React 18**: Dashboard UI
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Styling
- **Vanilla JS**: Chrome extension

### Infrastructure
- **AWS SAM**: Serverless deployment (optional)
- **Docker**: Containerization (optional)
- **GitHub Actions**: CI/CD (optional)

---

## 📄 License

MIT License - feel free to use this for your own job search or fork it to add features!

---

## 🙏 Acknowledgments

- **Claude AI** by Anthropic for intelligent job analysis
- **Gmail API** for job alert scanning
- **WeWorkRemotely** for remote job RSS feeds
- Job seekers everywhere grinding through the application process 💪

---

## 📧 Contact

Questions or suggestions? Open an issue or reach out!

---

**Built with ❤️ for job seekers by job seekers**
