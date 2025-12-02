#!/usr/bin/env python3
"""
Job Tracker - Local Version
Enhanced with AI-based filtering and baseline scoring
"""

import os
import json
import re
import base64
import sqlite3
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import urllib.request
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Flask for web UI
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

# Google API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# HTML parsing
from bs4 import BeautifulSoup

# Anthropic
import anthropic

# ============== Configuration ==============
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "jobs.db"
RESUMES_DIR = APP_DIR / "resumes"
CREDENTIALS_FILE = APP_DIR / "credentials.json"
TOKEN_FILE = APP_DIR / "token.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# WeWorkRemotely RSS Feeds
WWR_FEEDS = [
    'https://weworkremotely.com/categories/remote-programming-jobs.rss',
    'https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss',
    'https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss',
]

app = Flask(__name__)
CORS(app)

# ============== URL Cleaning ==============
def clean_job_url(url: str) -> str:
    """Remove tracking parameters from job URLs."""
    if not url:
        return url
    
    parsed = urlparse(url)
    
    # LinkedIn: keep only essential params
    if 'linkedin.com' in parsed.netloc:
        # Extract job ID from path or params
        if '/jobs/view/' in parsed.path:
            job_id = parsed.path.split('/jobs/view/')[-1].split('?')[0].split('/')[0]
            return f"https://www.linkedin.com/jobs/view/{job_id}"
        elif 'currentJobId=' in parsed.query:
            params = parse_qs(parsed.query)
            job_id = params.get('currentJobId', [''])[0]
            if job_id:
                return f"https://www.linkedin.com/jobs/view/{job_id}"
    
    # Indeed: keep only jk param
    elif 'indeed.com' in parsed.netloc:
        params = parse_qs(parsed.query)
        if 'jk' in params:
            return f"https://www.indeed.com/viewjob?jk={params['jk'][0]}"
        elif 'vjk' in params:
            return f"https://www.indeed.com/viewjob?jk={params['vjk'][0]}"
    
    # Remove common tracking params
    if parsed.query:
        params = parse_qs(parsed.query)
        tracking_params = [
            'trackingId', 'refId', 'lipi', 'midToken', 'midSig', 'trk', 
            'trkEmail', 'eid', 'otpToken', 'utm_source', 'utm_medium', 
            'utm_campaign', 'ref', 'source'
        ]
        cleaned_params = {k: v for k, v in params.items() if k not in tracking_params}
        
        if cleaned_params:
            new_query = urlencode(cleaned_params, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))
        else:
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    
    return url

# ============== Database ==============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            source TEXT,
            status TEXT DEFAULT 'new',
            score INTEGER DEFAULT 0,
            baseline_score INTEGER DEFAULT 0,
            analysis TEXT,
            cover_letter TEXT,
            notes TEXT,
            raw_text TEXT,
            created_at TEXT,
            updated_at TEXT,
            email_date TEXT,
            is_filtered INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============== Gmail ==============
def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE}. Download from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def get_email_body(payload):
    body = ""
    if 'body' in payload and payload['body'].get('data'):
        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    elif 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/html' and 'data' in part.get('body', {}):
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                break
            elif 'parts' in part:
                body = get_email_body(part)
                if body:
                    break
    return body

def generate_job_id(url, title, company):
    # Use cleaned URL for consistent ID generation
    clean_url = clean_job_url(url)
    content = f"{clean_url}:{title}:{company}".lower()
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def parse_linkedin_jobs(html, email_date):
    jobs = []
    soup = BeautifulSoup(html, 'html.parser')
    job_links = soup.find_all('a', href=re.compile(r'linkedin\.com.*jobs'))
    
    seen = set()
    for link in job_links:
        url = clean_job_url(link.get('href', ''))
        if not url or url in seen:
            continue
        seen.add(url)
        
        title_elem = link.find(['h2', 'h3', 'strong', 'span'])
        title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        
        parent = link.find_parent(['td', 'div', 'tr'])
        company, location, raw_text = "", "", title
        if parent:
            raw_text = parent.get_text(' ', strip=True)
            parts = raw_text.split('·')
            company = parts[1].strip()[:100] if len(parts) > 1 else ""
            location = parts[2].strip()[:100] if len(parts) > 2 else ""
        
        jobs.append({
            'job_id': generate_job_id(url, title, company),
            'title': title[:200], 'company': company, 'location': location,
            'url': url, 'source': 'linkedin', 'raw_text': raw_text[:1000],
            'created_at': email_date, 'email_date': email_date
        })
    return jobs

def parse_indeed_jobs(html, email_date):
    jobs = []
    soup = BeautifulSoup(html, 'html.parser')
    job_links = soup.find_all('a', href=re.compile(r'indeed\.com.*(jk=|vjk=)'))
    
    seen = set()
    for link in job_links:
        url = clean_job_url(link.get('href', ''))
        if not url or url in seen:
            continue
        seen.add(url)
        
        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        
        parent = link.find_parent(['td', 'div', 'tr'])
        company, location, raw_text = "", "", title
        if parent:
            raw_text = parent.get_text(' ', strip=True)
            lines = [l.strip() for l in parent.get_text('\n').split('\n') if l.strip()]
            company = lines[1][:100] if len(lines) > 1 else ""
            location = lines[2][:100] if len(lines) > 2 else ""
        
        jobs.append({
            'job_id': generate_job_id(url, title, company),
            'title': title[:200], 'company': company, 'location': location,
            'url': url, 'source': 'indeed', 'raw_text': raw_text[:1000],
            'created_at': email_date, 'email_date': email_date
        })
    return jobs

def fetch_wwr_jobs(days_back=7):
    """Fetch jobs from WeWorkRemotely RSS feeds."""
    jobs = []
    cutoff = datetime.now() - timedelta(days=days_back)
    
    for feed_url in WWR_FEEDS:
        try:
            req = urllib.request.Request(feed_url, headers={'User-Agent': 'JobTracker/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
            
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')
                pub_date_elem = item.find('pubDate')
                
                if not title_elem or not link_elem:
                    continue
                
                title = title_elem.text or ''
                url = clean_job_url(link_elem.text or '')
                description = desc_elem.text if desc_elem is not None else ''
                
                company = ''
                job_title = title
                if ':' in title:
                    parts = title.split(':', 1)
                    company = parts[0].strip()
                    job_title = parts[1].strip()
                
                pub_date = datetime.now().isoformat()
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date_elem.text)
                        if dt < cutoff:
                            continue
                        pub_date = dt.isoformat()
                    except:
                        pass
                
                if description:
                    soup = BeautifulSoup(description, 'html.parser')
                    description = soup.get_text(' ', strip=True)[:2000]
                
                job_id = generate_job_id(url, job_title, company)
                
                jobs.append({
                    'job_id': job_id,
                    'title': job_title[:200],
                    'company': company[:100],
                    'location': 'Remote',
                    'url': url,
                    'source': 'weworkremotely',
                    'raw_text': description or title,
                    'description': description,
                    'created_at': pub_date,
                    'email_date': pub_date
                })
                
        except Exception as e:
            print(f"WWR feed error ({feed_url}): {e}")
    
    return jobs

def scan_emails(days_back=7):
    service = get_gmail_service()
    after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
    
    # Updated queries with alert@indeed.com
    queries = [
        f'from:jobs-noreply@linkedin.com after:{after_date}',
        f'from:jobalerts-noreply@linkedin.com after:{after_date}',
        f'from:noreply@indeed.com after:{after_date}',
        f'from:alert@indeed.com after:{after_date}',
    ]
    
    all_jobs = []
    for query in queries:
        try:
            results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
            for msg_info in results.get('messages', []):
                message = service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
                email_date = datetime.fromtimestamp(int(message.get('internalDate', 0)) / 1000).isoformat()
                html = get_email_body(message.get('payload', {}))
                
                if 'linkedin' in query:
                    all_jobs.extend(parse_linkedin_jobs(html, email_date))
                else:
                    all_jobs.extend(parse_indeed_jobs(html, email_date))
        except Exception as e:
            print(f"Query error: {e}")
    
    return all_jobs

# ============== AI Filtering & Scoring ==============
def load_resumes():
    resumes = []
    if RESUMES_DIR.exists():
        for f in RESUMES_DIR.glob('*.txt'):
            resumes.append(f.read_text())
        for f in RESUMES_DIR.glob('*.md'):
            resumes.append(f.read_text())
    return "\n\n---\n\n".join(resumes)

def ai_filter_and_score(job, resume_text):
    """
    AI-based filtering and baseline scoring.
    Returns: (should_keep: bool, baseline_score: int, reason: str)
    """
    client = anthropic.Anthropic()
    
    prompt = f"""Analyze this job for filtering and baseline scoring.

CANDIDATE'S RESUME:
{resume_text}

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Brief Description: {job['raw_text'][:500]}

INSTRUCTIONS:
1. LOCATION FILTER: Keep ONLY if location is:
   - Remote (anywhere)
   - California Remote / CA Remote
   - San Diego (any arrangement: onsite, hybrid, remote)
   - Hybrid with San Diego option
   
2. SKILL LEVEL FILTER: Keep ONLY if skill level matches resume:
   - Not too junior (e.g., "intern", "entry-level" when candidate is mid-level)
   - Not too senior (e.g., "20+ years", "VP", "Director" when candidate is early career)
   - Tech stack has reasonable overlap with resume

3. BASELINE SCORE (1-100) based on:
   - Title match to candidate's background
   - Company reputation/fit
   - Location convenience (Remote=100, San Diego=95, CA Remote=90, Hybrid SD=85)
   - Seniority alignment

Return JSON only:
{{
    "keep": <bool>,
    "baseline_score": <1-100>,
    "filter_reason": "kept: good location and skill match" OR "filtered: requires 15+ years",
    "location_match": "remote|san_diego|ca_remote|hybrid_sd|other",
    "skill_level_match": "too_junior|good_fit|too_senior"
}}
"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        match = re.search(r'\{[\s\S]*\}', response.content[0].text)
        if match:
            result = json.loads(match.group())
            return (
                result.get('keep', False),
                result.get('baseline_score', 0),
                result.get('filter_reason', 'unknown')
            )
    except Exception as e:
        print(f"AI filter error: {e}")
    
    # Default: keep but low score
    return (True, 30, "filter error - kept by default")

def analyze_job(job, resume_text):
    """Full job analysis (called after baseline)."""
    client = anthropic.Anthropic()
    
    prompt = f"""Analyze job fit. Respond ONLY with valid JSON.

RESUME:
{resume_text}

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Details: {job['raw_text']}

Return JSON:
{{"qualification_score": <1-100>, "should_apply": <bool>, "strengths": ["..."], "gaps": ["..."], "recommendation": "...", "resume_to_use": "backend|cloud|fullstack"}}
"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        match = re.search(r'\{[\s\S]*\}', response.content[0].text)
        return json.loads(match.group()) if match else {}
    except Exception as e:
        print(f"Analysis error: {e}")
        return {"qualification_score": 0, "should_apply": False, "recommendation": str(e)}

def generate_cover_letter(job, resume_text):
    client = anthropic.Anthropic()
    analysis = json.loads(job['analysis']) if job['analysis'] else {}
    
    prompt = f"""Write a tailored cover letter (3-4 paragraphs, under 350 words).

JOB: {job['title']} at {job['company']}
Details: {job['raw_text']}

CANDIDATE RESUME:
{resume_text}

STRENGTHS: {', '.join(analysis.get('strengths', []))}

Write the cover letter now:"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Error: {e}"

# ============== Sorting ==============
def calculate_weighted_score(baseline_score, email_date):
    """70% qualification + 30% recency"""
    # Recency score: 100 for today, decay over 30 days
    try:
        date_obj = datetime.fromisoformat(email_date)
        days_old = (datetime.now() - date_obj).days
        recency_score = max(0, 100 - (days_old * 3.33))  # Linear decay over 30 days
    except:
        recency_score = 0
    
    weighted = (baseline_score * 0.7) + (recency_score * 0.3)
    return round(weighted, 2)

# ============== Flask Routes ==============
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>HireTrack - Job Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="max-w-6xl mx-auto p-6">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold">🎯 HireTrack</h1>
                <p class="text-gray-600">AI-Filtered Job Tracker</p>
            </div>
            <div class="space-x-2">
                <button onclick="scanEmails()" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                    📧 Scan Gmail
                </button>
                <button onclick="scanWWR()" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                    🌐 Scan WWR
                </button>
                <button onclick="analyzeAll()" class="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700">
                    🤖 Analyze All
                </button>
            </div>
        </div>
        
        <div id="stats" class="grid grid-cols-5 gap-4 mb-6"></div>
        
        <div class="mb-4 flex gap-4">
            <input type="text" id="search" placeholder="Search..." 
                   class="flex-1 px-4 py-2 border rounded" onkeyup="filterJobs()">
            <select id="statusFilter" class="px-4 py-2 border rounded" onchange="loadJobs()">
                <option value="">All Statuses</option>
                <option value="new">New</option>
                <option value="interested">Interested</option>
                <option value="applied">Applied</option>
                <option value="passed">Passed</option>
            </select>
            <select id="minScore" class="px-4 py-2 border rounded" onchange="loadJobs()">
                <option value="0">All Scores</option>
                <option value="80">80+</option>
                <option value="60">60+</option>
                <option value="40">40+</option>
            </select>
        </div>
        
        <div id="jobs" class="space-y-3"></div>
    </div>
    
    <script>
        let allJobs = [];
        
        function formatDate(dateStr) {
            if (!dateStr) return '';
            try {
                const d = new Date(dateStr);
                return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            } catch {
                return '';
            }
        }
        
        async function loadJobs() {
            const status = document.getElementById('statusFilter').value;
            const minScore = document.getElementById('minScore').value;
            const params = new URLSearchParams({status, min_score: minScore});
            
            const res = await fetch('/api/jobs?' + params);
            const data = await res.json();
            allJobs = data.jobs;
            renderJobs(allJobs);
            renderStats(data.stats);
        }
        
        function renderStats(stats) {
            document.getElementById('stats').innerHTML = `
                <div class="bg-white p-4 rounded shadow text-center">
                    <div class="text-2xl font-bold">${stats.total}</div>
                    <div class="text-gray-500 text-sm">Total</div>
                </div>
                <div class="bg-blue-50 p-4 rounded shadow text-center">
                    <div class="text-2xl font-bold">${stats.new}</div>
                    <div class="text-gray-500 text-sm">New</div>
                </div>
                <div class="bg-yellow-50 p-4 rounded shadow text-center">
                    <div class="text-2xl font-bold">${stats.interested}</div>
                    <div class="text-gray-500 text-sm">Interested</div>
                </div>
                <div class="bg-green-50 p-4 rounded shadow text-center">
                    <div class="text-2xl font-bold">${stats.applied}</div>
                    <div class="text-gray-500 text-sm">Applied</div>
                </div>
                <div class="bg-purple-50 p-4 rounded shadow text-center">
                    <div class="text-2xl font-bold">${Math.round(stats.avg_score)}</div>
                    <div class="text-gray-500 text-sm">Avg Score</div>
                </div>
            `;
        }
        
        function filterJobs() {
            const search = document.getElementById('search').value.toLowerCase();
            const filtered = allJobs.filter(j => 
                j.title.toLowerCase().includes(search) || 
                (j.company || '').toLowerCase().includes(search)
            );
            renderJobs(filtered);
        }
        
        function renderJobs(jobs) {
            const container = document.getElementById('jobs');
            container.innerHTML = jobs.map(job => {
                const analysis = job.analysis ? JSON.parse(job.analysis) : {};
                const scoreColor = job.baseline_score >= 80 ? 'bg-green-500' : 
                                   job.baseline_score >= 60 ? 'bg-blue-500' : 
                                   job.baseline_score >= 40 ? 'bg-yellow-500' : 'bg-gray-300';
                return `
                <div class="bg-white rounded-lg shadow p-4">
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="${scoreColor} text-white px-2 py-1 rounded-full text-sm font-bold">
                                    ${job.baseline_score || '—'}
                                </span>
                                <h3 class="font-semibold">${job.title}</h3>
                            </div>
                            <p class="text-gray-600 text-sm">${job.company || 'Unknown'} • ${job.location || ''}</p>
                            <p class="text-gray-400 text-xs">${job.source} • ${formatDate(job.email_date)}</p>
                            ${analysis.recommendation ? `<p class="text-gray-500 text-sm mt-2">${analysis.recommendation}</p>` : ''}
                        </div>
                        <div class="flex items-center gap-2">
                            <select onchange="updateStatus('${job.job_id}', this.value)" 
                                    class="text-sm border rounded px-2 py-1">
                                ${['new','interested','applied','interviewing','passed','rejected'].map(s => 
                                    `<option value="${s}" ${job.status === s ? 'selected' : ''}>${s}</option>`
                                ).join('')}
                            </select>
                            <a href="${job.url}" target="_blank" class="text-blue-600 hover:underline text-sm">View</a>
                        </div>
                    </div>
                    ${analysis.strengths ? `
                    <details class="mt-3">
                        <summary class="cursor-pointer text-sm text-gray-500">Details</summary>
                        <div class="mt-2 grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <h4 class="font-semibold text-green-700">Strengths</h4>
                                <ul class="list-disc list-inside">${analysis.strengths.map(s => `<li>${s}</li>`).join('')}</ul>
                            </div>
                            <div>
                                <h4 class="font-semibold text-red-700">Gaps</h4>
                                <ul class="list-disc list-inside">${(analysis.gaps || []).map(g => `<li>${g}</li>`).join('')}</ul>
                            </div>
                        </div>
                        ${job.cover_letter ? `
                        <div class="mt-3">
                            <h4 class="font-semibold">Cover Letter</h4>
                            <pre class="bg-gray-50 p-3 rounded text-sm whitespace-pre-wrap mt-1">${job.cover_letter}</pre>
                        </div>
                        ` : `
                        <button onclick="generateCoverLetter('${job.job_id}')" 
                                class="mt-2 bg-purple-600 text-white px-3 py-1 rounded text-sm">
                            Generate Cover Letter
                        </button>
                        `}
                    </details>
                    ` : ''}
                </div>
                `;
            }).join('');
        }
        
        async function scanWWR() {
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Scanning...';
            await fetch('/api/wwr', {method: 'POST'});
            await loadJobs();
            btn.disabled = false;
            btn.textContent = '🌐 Scan WWR';
        }
        
        async function scanEmails() {
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Scanning...';
            await fetch('/api/scan', {method: 'POST'});
            await loadJobs();
            btn.disabled = false;
            btn.textContent = '📧 Scan Gmail';
        }
        
        async function analyzeAll() {
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Analyzing...';
            await fetch('/api/analyze', {method: 'POST'});
            await loadJobs();
            btn.disabled = false;
            btn.textContent = '🤖 Analyze All';
        }
        
        async function updateStatus(jobId, status) {
            await fetch(`/api/jobs/${jobId}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status})
            });
            loadJobs();
        }
        
        async function generateCoverLetter(jobId) {
            event.target.disabled = true;
            event.target.textContent = 'Generating...';
            await fetch(`/api/jobs/${jobId}/cover-letter`, {method: 'POST'});
            loadJobs();
        }
        
        loadJobs();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/jobs')
def get_jobs():
    status = request.args.get('status', '')
    min_score = int(request.args.get('min_score', 0))
    
    conn = get_db()
    query = "SELECT * FROM jobs WHERE is_filtered = 0"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    if min_score:
        query += " AND baseline_score >= ?"
        params.append(min_score)
    
    # Fetch all matching jobs
    jobs = [dict(row) for row in conn.execute(query, params).fetchall()]
    
    # Calculate weighted scores and sort
    for job in jobs:
        job['weighted_score'] = calculate_weighted_score(
            job.get('baseline_score', 0), 
            job.get('email_date', job.get('created_at', ''))
        )
    
    jobs.sort(key=lambda x: x['weighted_score'], reverse=True)
    
    # Stats
    all_jobs = [dict(row) for row in conn.execute("SELECT status, baseline_score FROM jobs WHERE is_filtered = 0").fetchall()]
    stats = {
        'total': len(all_jobs),
        'new': len([j for j in all_jobs if j['status'] == 'new']),
        'interested': len([j for j in all_jobs if j['status'] == 'interested']),
        'applied': len([j for j in all_jobs if j['status'] == 'applied']),
        'avg_score': sum(j['baseline_score'] or 0 for j in all_jobs) / len(all_jobs) if all_jobs else 0
    }
    
    conn.close()
    return jsonify({'jobs': jobs, 'stats': stats})

@app.route('/api/jobs/<job_id>', methods=['PATCH'])
def update_job(job_id):
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
        (data.get('status'), datetime.now().isoformat(), job_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Scan emails with AI filtering and baseline scoring."""
    jobs = scan_emails()
    resume_text = load_resumes()
    
    if not resume_text:
        return jsonify({'error': 'No resumes found. Add .txt/.md files to resumes/ folder'}), 400
    
    conn = get_db()
    new_count = 0
    filtered_count = 0
    
    for job in jobs:
        existing = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job['job_id'],)).fetchone()
        if existing:
            continue
        
        # AI filter and baseline score
        keep, baseline_score, reason = ai_filter_and_score(job, resume_text)
        
        if keep:
            conn.execute('''
                INSERT INTO jobs (job_id, title, company, location, url, source, raw_text, 
                                 baseline_score, created_at, updated_at, email_date, is_filtered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (job['job_id'], job['title'], job['company'], job['location'], 
                  job['url'], job['source'], job['raw_text'], baseline_score,
                  job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at'])))
            new_count += 1
            print(f"✓ Kept: {job['title']} - Score {baseline_score} - {reason}")
        else:
            # Store filtered jobs but mark them
            conn.execute('''
                INSERT INTO jobs (job_id, title, company, location, url, source, raw_text, 
                                 baseline_score, created_at, updated_at, email_date, is_filtered, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ''', (job['job_id'], job['title'], job['company'], job['location'], 
                  job['url'], job['source'], job['raw_text'], baseline_score,
                  job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at']), reason))
            filtered_count += 1
            print(f"✗ Filtered: {job['title']} - {reason}")
    
    conn.commit()
    conn.close()
    return jsonify({
        'found': len(jobs), 
        'new': new_count, 
        'filtered': filtered_count
    })

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Full analysis on jobs that passed baseline filter."""
    resume_text = load_resumes()
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    conn = get_db()
    jobs = [dict(row) for row in conn.execute(
        "SELECT * FROM jobs WHERE is_filtered = 0 AND (score = 0 OR score IS NULL)"
    ).fetchall()]
    
    for job in jobs:
        print(f"Analyzing: {job['title']}")
        analysis = analyze_job(job, resume_text)
        conn.execute(
            "UPDATE jobs SET score = ?, analysis = ?, status = ?, updated_at = ? WHERE job_id = ?",
            (analysis.get('qualification_score', 0), json.dumps(analysis),
             'interested' if analysis.get('should_apply') else 'new',
             datetime.now().isoformat(), job['job_id'])
        )
        conn.commit()
    
    conn.close()
    return jsonify({'analyzed': len(jobs)})

@app.route('/api/jobs/<job_id>/cover-letter', methods=['POST'])
def api_cover_letter(job_id):
    resume_text = load_resumes()
    conn = get_db()
    job = dict(conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone())
    
    cover_letter = generate_cover_letter(job, resume_text)
    conn.execute(
        "UPDATE jobs SET cover_letter = ?, updated_at = ? WHERE job_id = ?",
        (cover_letter, datetime.now().isoformat(), job_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'cover_letter': cover_letter})

@app.route('/api/capture', methods=['POST'])
def api_capture():
    """Receive job from browser extension."""
    data = request.json
    
    url = clean_job_url(data.get('url', ''))
    title = data.get('title', '')
    company = data.get('company', '')
    location = data.get('location', 'Remote')
    description = data.get('description', '')
    source = data.get('source', 'extension')
    
    # Auto-detect source from URL
    if 'linkedin.com' in url:
        source = 'linkedin'
    elif 'indeed.com' in url:
        source = 'indeed'
    elif 'weworkremotely.com' in url:
        source = 'weworkremotely'
    
    if not url or not title:
        return jsonify({'error': 'url and title required'}), 400
    
    job_id = generate_job_id(url, title, company)
    
    conn = get_db()
    existing = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    
    if existing:
        conn.execute('''
            UPDATE jobs SET description = ?, raw_text = ?, updated_at = ?
            WHERE job_id = ? AND (description IS NULL OR description = '')
        ''', (description[:5000], description[:2000], datetime.now().isoformat(), job_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'updated', 'job_id': job_id})
    
    # New job from extension - add with baseline score
    resume_text = load_resumes()
    baseline_score = 50  # Default
    
    if resume_text:
        temp_job = {
            'title': title, 'company': company, 'location': location,
            'raw_text': description[:500] if description else title
        }
        keep, baseline_score, reason = ai_filter_and_score(temp_job, resume_text)
    
    conn.execute('''
        INSERT INTO jobs (job_id, title, company, location, url, source, description, raw_text, 
                         baseline_score, created_at, updated_at, is_filtered)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', (job_id, title[:200], company[:100], location[:100], url, source, 
          description[:5000], description[:2000], baseline_score,
          datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'created', 'job_id': job_id, 'baseline_score': baseline_score})

@app.route('/api/analyze-instant', methods=['POST'])
def api_analyze_instant():
    """Instant analysis for browser extension."""
    data = request.json
    
    title = data.get('title', '')
    company = data.get('company', 'Unknown')
    description = data.get('description', '')
    
    if not title or not description:
        return jsonify({'error': 'title and description required'}), 400
    
    resume_text = load_resumes()
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    temp_job = {
        'title': title, 'company': company,
        'location': data.get('location', ''),
        'raw_text': description[:2000], 'description': description
    }
    
    analysis = analyze_job(temp_job, resume_text)
    
    return jsonify({'analysis': analysis, 'job': temp_job})

@app.route('/api/wwr', methods=['POST'])
def api_scan_wwr():
    """Scan WWR with AI filtering."""
    jobs = fetch_wwr_jobs()
    resume_text = load_resumes()
    
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    conn = get_db()
    new_count = 0
    filtered_count = 0
    
    for job in jobs:
        existing = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job['job_id'],)).fetchone()
        if existing:
            continue
        
        keep, baseline_score, reason = ai_filter_and_score(job, resume_text)
        
        if keep:
            conn.execute('''
                INSERT INTO jobs (job_id, title, company, location, url, source, description, raw_text, 
                                 baseline_score, created_at, updated_at, email_date, is_filtered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (job['job_id'], job['title'], job['company'], job['location'], 
                  job['url'], job['source'], job.get('description', ''), job['raw_text'], baseline_score,
                  job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at'])))
            new_count += 1
        else:
            conn.execute('''
                INSERT INTO jobs (job_id, title, company, location, url, source, description, raw_text, 
                                 baseline_score, created_at, updated_at, email_date, is_filtered, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ''', (job['job_id'], job['title'], job['company'], job['location'], 
                  job['url'], job['source'], job.get('description', ''), job['raw_text'], baseline_score,
                  job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at']), reason))
            filtered_count += 1
    
    conn.commit()
    conn.close()
    return jsonify({'found': len(jobs), 'new': new_count, 'filtered': filtered_count})

@app.route('/api/generate-cover-letter', methods=['POST'])
def api_generate_cover_letter():
    """Generate cover letter for extension."""
    data = request.json
    job = data.get('job', {})
    analysis = data.get('analysis', {})
    
    resume_text = load_resumes()
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    client = anthropic.Anthropic()
    
    strengths = ', '.join(analysis.get('strengths', []))
    
    prompt = f"""Write a tailored cover letter (3-4 paragraphs, under 350 words).

JOB:
Title: {job.get('title')}
Company: {job.get('company')}
Description: {job.get('description', '')[:1000]}

CANDIDATE RESUME:
{resume_text}

KEY STRENGTHS TO HIGHLIGHT:
{strengths}

Write a professional, enthusiastic cover letter. Include:
1. Strong opening expressing interest
2. 2 paragraphs highlighting relevant experience and achievements
3. Closing with call to action

Write only the cover letter text (no subject line, no extra formatting):"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        cover_letter = response.content[0].text.strip()
        return jsonify({'cover_letter': cover_letter})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-answer', methods=['POST'])
def api_generate_answer():
    """Generate interview answer for extension."""
    data = request.json
    job = data.get('job', {})
    question = data.get('question')
    analysis = data.get('analysis', {})
    
    if not question:
        return jsonify({'error': 'Question required'}), 400
    
    resume_text = load_resumes()
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    client = anthropic.Anthropic()
    
    prompt = f"""Generate a strong interview answer for this question.

QUESTION: {question}

JOB CONTEXT:
Title: {job.get('title')}
Company: {job.get('company')}
Description: {job.get('description', '')[:500]}

CANDIDATE RESUME:
{resume_text}

ANALYSIS INSIGHTS:
Strengths: {', '.join(analysis.get('strengths', []))}
Gaps: {', '.join(analysis.get('gaps', []))}

Generate a compelling 2-3 paragraph answer that:
1. Directly answers the question
2. Uses specific examples from the resume
3. Connects to the job requirements
4. Sounds natural and conversational (not rehearsed)
5. Is honest but strategic about any weaknesses

Write only the answer (2-3 paragraphs, 150-200 words):"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.content[0].text.strip()
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    RESUMES_DIR.mkdir(exist_ok=True)
    print(f"\n📁 Put resumes in: {RESUMES_DIR}")
    print(f"📁 Put credentials.json in: {APP_DIR}")
    print(f"\n🚀 Starting HireTrack at http://localhost:5000\n")
    app.run(debug=True, port=5000)