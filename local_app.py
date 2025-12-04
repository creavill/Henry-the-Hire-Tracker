#!/usr/bin/env python3
"""
Hammy the Hire Tracker - Local Application
AI-powered job tracking system with Gmail integration and Chrome extension support.

Go HAM on your job search! 🐷

This application:
- Scans Gmail for job alerts from LinkedIn, Indeed, and other job boards
- Uses Claude AI to analyze job fit against your resume(s)
- Provides a web dashboard for tracking applications
- Integrates with a Chrome extension for instant job analysis
- Generates tailored cover letters and interview prep answers
- Scans for follow-up emails (interviews, rejections, offers)

Configuration is loaded from config.yaml for easy personalization.
"""

import os
import json
import re
import base64
import sqlite3
import hashlib
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import urllib.request
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Configuration loader for user preferences
from config_loader import get_config

# Flask web framework for dashboard UI
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

# Google Gmail API for email scanning
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# HTML parsing for job email extraction
from bs4 import BeautifulSoup

# Anthropic Claude AI for job analysis
import anthropic

# ============== Configuration ==============
# Load user configuration from config.yaml
try:
    CONFIG = get_config()
except FileNotFoundError as e:
    print(f"\n❌ Configuration Error: {e}")
    print("📝 Copy config.example.yaml to config.yaml and fill in your information.\n")
    exit(1)

# Application directories
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "jobs.db"
RESUMES_DIR = APP_DIR / "resumes"
CREDENTIALS_FILE = APP_DIR / "credentials.json"
TOKEN_FILE = APP_DIR / "token.json"

# Gmail API scope for read-only access
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
    """
    Remove tracking parameters from job URLs to prevent duplicate entries.

    Job boards add tracking parameters (tracking IDs, referral codes, etc.) that make
    the same job appear as different URLs. This function normalizes URLs by:
    - Extracting core job IDs from LinkedIn and Indeed
    - Removing common tracking parameters (utm_*, refId, etc.)
    - Preserving only essential query parameters

    Args:
        url: Raw job URL with potential tracking parameters

    Returns:
        Cleaned URL with tracking parameters removed

    Examples:
        LinkedIn: https://linkedin.com/jobs/view/123?refId=xyz&trk=email
                  → https://linkedin.com/jobs/view/123
        Indeed:   https://indeed.com/viewjob?jk=abc123&tk=xyz&from=email
                  → https://indeed.com/viewjob?jk=abc123
    """
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
    """
    Initialize SQLite database with required tables.

    Creates tables for:
    - jobs: Main job listings with AI analysis and scoring
    - scan_history: Track email scan timestamps to avoid re-processing
    - watchlist: Companies to monitor for future openings
    - followups: Interview and application follow-up tracking
    - external_applications: Track applications made outside the system

    Uses WAL (Write-Ahead Logging) mode for better concurrency when
    multiple processes/threads access the database.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    # Enable WAL mode for better concurrency (allows simultaneous reads during writes)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Create tables if they don't exist
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
            is_filtered INTEGER DEFAULT 0,
            viewed INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_scan_date TEXT,
            emails_found INTEGER,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            url TEXT,
            notes TEXT,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            subject TEXT,
            type TEXT,
            snippet TEXT,
            email_date TEXT,
            job_id TEXT,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS external_applications (
            app_id TEXT PRIMARY KEY,
            job_id TEXT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            url TEXT,
            source TEXT NOT NULL,
            application_method TEXT,
            applied_date TEXT NOT NULL,
            contact_name TEXT,
            contact_email TEXT,
            status TEXT DEFAULT 'applied',
            follow_up_date TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            is_linked_to_job INTEGER DEFAULT 0,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        )
    ''')

    # Migration: Add job_id column if it doesn't exist
    try:
        conn.execute("SELECT job_id FROM followups LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating database: adding 'job_id' column to followups...")
        conn.execute("ALTER TABLE followups ADD COLUMN job_id TEXT")
    
    # Migration: Add viewed column if it doesn't exist
    try:
        conn.execute("SELECT viewed FROM jobs LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating database: adding 'viewed' column...")
        conn.execute("ALTER TABLE jobs ADD COLUMN viewed INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)  # Wait up to 30s for lock
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
    """Extract LinkedIn jobs with better filtering."""
    jobs = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find job links with actual job IDs
    job_links = soup.find_all('a', href=re.compile(r'linkedin\.com.*jobs/view/\d{10}'))
    
    exclude_keywords = ['see all', 'unsubscribe', 'help', 'saved jobs', 'search jobs', 
                       'learn why', 'settings', 'preferences', 'view all', 'messaging', 
                       'mynetwork', 'games', 'notifications']
    
    seen = set()
    for link in job_links:
        url = clean_job_url(link.get('href', ''))
        if not url or url in seen:
            continue
        
        # Get title from link text or nearby heading
        title_elem = link.find(['h3', 'h4', 'span', 'div'])
        full_text = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
        
        # Skip if title is a UI element
        if any(keyword in full_text.lower() for keyword in exclude_keywords):
            continue
        
        if not full_text or len(full_text) < 5:
            continue
        
        seen.add(url)
        
        # Parse formats:
        # "Software EngineerLensa · San Diego, CA"
        # "DevOps EngineerHumana · United States (Remote)"
        title = full_text
        company = ""
        location = ""
        
        # Split on delimiter
        if '·' in full_text:
            parts = full_text.split('·', 1)
            title_company_part = parts[0].strip()
            location = parts[1].strip() if len(parts) > 1 else ""
            
            # Company is capitalized word(s) after lowercase letter
            # Match patterns like "EngineerCompanyName" or "DeveloperLensa"
            match = re.search(r'([a-z])([A-Z][A-Za-z0-9\s&.,-]+)$', title_company_part)
            if match:
                title = title_company_part[:match.start(2)].strip()
                company = match.group(2).strip()
            else:
                # Fallback: split on last capital letter sequence
                capital_match = re.search(r'^(.+?)([A-Z][A-Za-z0-9\s&.,-]+)$', title_company_part)
                if capital_match:
                    title = capital_match.group(1).strip()
                    company = capital_match.group(2).strip()
                else:
                    title = title_company_part
        
        # Fallback: check parent for more context
        if not company:
            parent = link.find_parent(['div', 'td', 'tr', 'li'])
            if parent:
                text = parent.get_text('\n', strip=True)
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                # Look for company name in next line
                for i, line in enumerate(lines):
                    if title in line and i + 1 < len(lines):
                        next_line = lines[i + 1]
                        # Company usually doesn't have symbols except &
                        if not any(c in next_line for c in ['$', '/', '(', ')', 'Easy Apply', 'Actively']):
                            company = next_line.split('·')[0].strip()[:100]
                        break
        
        raw_text = full_text
        parent = link.find_parent(['div', 'td', 'tr', 'li'])
        if parent:
            text = parent.get_text('\n', strip=True)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            raw_text = ' '.join(lines[:5])[:1000]
        
        jobs.append({
            'job_id': generate_job_id(url, title, company),
            'title': title[:200],
            'company': company[:100] if company else "Unknown",
            'location': location[:100],
            'url': url,
            'source': 'linkedin',
            'raw_text': raw_text,
            'created_at': email_date,
            'email_date': email_date
        })
    
    return jobs


def parse_indeed_jobs(html, email_date):
    """Extract Indeed jobs with better filtering."""
    jobs = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Indeed uses table cells or divs for job cards
    job_links = soup.find_all('a', href=re.compile(r'indeed\.com.*(jk=|vjk=)[a-f0-9]+'))
    
    exclude_keywords = ['unsubscribe', 'help', 'view all', 'see all', 'homepage', 
                       'messages', 'notifications', 'easily apply', 'responsive employer']
    
    seen = set()
    for link in job_links:
        url = clean_job_url(link.get('href', ''))
        if not url or url in seen:
            continue
        
        full_text = link.get_text(strip=True)
        
        # Skip UI elements
        if any(keyword in full_text.lower() for keyword in exclude_keywords):
            continue
        
        if not full_text or len(full_text) < 5:
            continue
        
        seen.add(url)
        
        title = full_text
        company = ""
        location = ""
        
        # Find parent container
        parent = link.find_parent(['td', 'div', 'li'])
        raw_text = full_text
        
        if parent:
            text = parent.get_text('\n', strip=True)
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]
            
            # Indeed format: Title / Company / Location / Salary / Description
            for i, line in enumerate(lines):
                if title in line and i + 1 < len(lines):
                    # Next line is usually company
                    potential_company = lines[i + 1]
                    # Skip ratings like "4.8 4.8/5 rating"
                    if not re.match(r'^\d+\.?\d*\s*\d', potential_company):
                        company = potential_company[:100]
                    if i + 2 < len(lines):
                        potential_location = lines[i + 2]
                        if 'remote' in potential_location.lower() or ',' in potential_location:
                            location = potential_location[:100]
                    break
            
            raw_text = ' '.join(lines[:6])[:1000]
        
        jobs.append({
            'job_id': generate_job_id(url, title, company),
            'title': title[:200],
            'company': company if company else "Unknown",
            'location': location,
            'url': url,
            'source': 'indeed',
            'raw_text': raw_text,
            'created_at': email_date,
            'email_date': email_date
        })
    
    return jobs


def parse_greenhouse_jobs(html, email_date):
    """Extract Greenhouse jobs."""
    jobs = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Greenhouse links
    job_links = soup.find_all('a', href=re.compile(r'greenhouse\.io|boards\.greenhouse\.io'))
    
    seen = set()
    for link in job_links:
        url = link.get('href', '')
        if not url or url in seen or 'unsubscribe' in url.lower():
            continue
        
        url = clean_job_url(url)
        
        # Title from link or nearby
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        
        seen.add(url)
        
        # Find company and location
        parent = link.find_parent(['div', 'td', 'tr'])
        company, location, raw_text = "", "", title
        
        if parent:
            text = parent.get_text('\n', strip=True)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Extract company from URL or nearby text
            if 'boards.greenhouse.io' in url:
                company = url.split('boards.greenhouse.io/')[-1].split('/')[0].replace('-', ' ').title()
            
            for line in lines:
                if 'engineering' in line.lower() or 'department' in line.lower():
                    continue
                if any(loc in line.lower() for loc in ['remote', 'hybrid', 'san diego', 'california']):
                    location = line[:100]
                    break
            
            raw_text = ' '.join(lines[:5])[:1000]
        
        jobs.append({
            'job_id': generate_job_id(url, title, company),
            'title': title[:200],
            'company': company,
            'location': location,
            'url': url,
            'source': 'greenhouse',
            'raw_text': raw_text,
            'created_at': email_date,
            'email_date': email_date
        })
    
    return jobs


def parse_wellfound_jobs(html, email_date):
    """Extract Wellfound (AngelList) jobs."""
    jobs = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Wellfound links
    job_links = soup.find_all('a', href=re.compile(r'wellfound\.com|angel\.co'))
    
    exclude_keywords = ['unsubscribe', 'settings', 'preferences', 'learn more']
    
    seen = set()
    for link in job_links:
        url = link.get('href', '')
        if not url or url in seen:
            continue
        
        url = clean_job_url(url)
        title = link.get_text(strip=True)
        
        if any(keyword in title.lower() for keyword in exclude_keywords):
            continue
        
        if not title or len(title) < 5:
            continue
        
        seen.add(url)
        
        # Find company and details
        parent = link.find_parent(['div', 'td', 'tr'])
        company, location, raw_text = "", "Remote", title
        
        if parent:
            text = parent.get_text('\n', strip=True)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Wellfound format includes company info nearby
            for i, line in enumerate(lines):
                if '/' in line and 'Employees' in line:
                    company = line.split('/')[0].strip()[:100]
                if any(loc in line for loc in ['Remote', 'Austin', 'San Diego', 'San Francisco']):
                    location = line[:100]
            
            raw_text = ' '.join(lines[:8])[:1000]
        
        jobs.append({
            'job_id': generate_job_id(url, title, company),
            'title': title[:200],
            'company': company,
            'location': location,
            'url': url,
            'source': 'wellfound',
            'raw_text': raw_text,
            'created_at': email_date,
            'email_date': email_date
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
                
                if title_elem is None or link_elem is None:
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
    
    # Get last scan date from DB
    conn = sqlite3.connect(DB_PATH)
    last_scan = conn.execute(
        "SELECT last_scan_date FROM scan_history ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    
    if last_scan and last_scan[0]:
        # Parse the saved date and format for Gmail
        try:
            last_date = datetime.fromisoformat(last_scan[0])
            # Add 1 second to avoid re-processing last scan's emails
            last_date = last_date + timedelta(seconds=1)
            after_date = last_date.strftime('%Y/%m/%d')
            print(f"📅 Scanning emails after last scan: {after_date}")
        except:
            # Fallback if date parsing fails
            after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
            print(f"⚠️ Date parse failed, scanning last {days_back} days: {after_date}")
    else:
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        print(f"🆕 First scan - looking back {days_back} days: {after_date}")
    
    # Query all job board emails + follow-ups
    queries = [
        # Known job alerts
        f'from:jobs-noreply@linkedin.com after:{after_date}',
        f'from:jobalerts-noreply@linkedin.com after:{after_date}',
        f'from:noreply@indeed.com after:{after_date}',
        f'from:alert@indeed.com after:{after_date}',
        f'from:no-reply@us.greenhouse-jobs.com after:{after_date}',
        f'from:team@hi.wellfound.com after:{after_date}',
        
        # Generic job board catch-all (job OR career OR position in subject)
        f'(subject:job OR subject:career OR subject:position OR subject:"now hiring") -from:linkedin.com -from:indeed.com -from:greenhouse.io -from:wellfound.com after:{after_date}',
        
        # Follow-ups for Applied tab
        f'(subject:interview OR subject:"next steps" OR subject:update OR subject:"application received" OR subject:confirmation) after:{after_date}',
        f'(subject:unfortunately OR subject:offer OR subject:congratulations OR subject:"thank you for applying") after:{after_date}',
    ]
    
    all_jobs = []
    seen_job_ids = set()  # Track job_ids to prevent duplicates
    total_emails = 0
    
    for query in queries:
        try:
            # Increased from 50 to 100
            results = service.users().messages().list(userId='me', q=query, maxResults=100).execute()
            messages = results.get('messages', [])
            total_emails += len(messages)
            
            for msg_info in messages:
                try:
                    message = service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
                    email_date = datetime.fromtimestamp(int(message.get('internalDate', 0)) / 1000).isoformat()
                    html = get_email_body(message.get('payload', {}))
                    
                    if not html:
                        continue
                    
                    # Check if follow-up email
                    subject = ''
                    for header in message.get('payload', {}).get('headers', []):
                        if header['name'].lower() == 'subject':
                            subject = header['value'].lower()
                            break
                    
                    is_followup = any(keyword in subject for keyword in [
                        'interview', 'next steps', 'unfortunately', 'offer', 
                        'congratulations', 'declined', 'application update'
                    ])
                    
                    if is_followup:
                        print(f"📧 Follow-up detected: {subject[:60]}...")
                        # TODO: Add follow-up tracking table and logic
                        continue
                    
                    # Route to appropriate parser
                    if 'linkedin' in query:
                        jobs = parse_linkedin_jobs(html, email_date)
                    elif 'indeed' in query:
                        jobs = parse_indeed_jobs(html, email_date)
                    elif 'greenhouse' in query:
                        jobs = parse_greenhouse_jobs(html, email_date)
                    elif 'wellfound' in query:
                        jobs = parse_wellfound_jobs(html, email_date)
                    else:
                        jobs = []
                    
                    # Deduplicate before adding
                    unique_jobs = []
                    for job in jobs:
                        if job['job_id'] not in seen_job_ids:
                            seen_job_ids.add(job['job_id'])
                            unique_jobs.append(job)
                    
                    all_jobs.extend(unique_jobs)
                    if unique_jobs:
                        print(f"✓ Found {len(unique_jobs)} unique jobs from {query.split('from:')[1].split()[0] if 'from:' in query else 'follow-ups'}")
                    
                except Exception as e:
                    print(f"Error parsing email {msg_info['id']}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Query failed - {query}: {e}")
            continue
    
    # Save current scan timestamp (ISO format for consistency)
    current_scan_time = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO scan_history (last_scan_date, emails_found, created_at) VALUES (?, ?, ?)",
        (current_scan_time, total_emails, current_scan_time)
    )
    conn.commit()
    conn.close()
    
    print(f"✅ Scan complete: {total_emails} emails checked, {len(all_jobs)} unique jobs extracted")
    print(f"📌 Next scan will query emails after: {current_scan_time}")
    return all_jobs

# ============== Follow-Up Email Scanning ==============
def classify_followup_email(subject: str, snippet: str) -> str:
    """
    Classify follow-up email type based on subject and snippet.

    Uses keyword matching to determine if email is:
    - interview: Interview request or scheduling
    - rejection: Application declined
    - received: Application confirmation
    - offer: Job offer
    - assessment: Coding challenge or take-home project

    Args:
        subject: Email subject line (lowercase)
        snippet: Email preview text (lowercase)

    Returns:
        Email type string
    """
    text = (subject + " " + snippet).lower()

    # Check for interview requests (highest priority)
    if any(word in text for word in ['interview', 'phone screen', 'video call', 'meet the team',
                                       'schedule a call', 'next steps', 'speak with', 'chat with']):
        return 'interview'

    # Check for offers
    if any(word in text for word in ['offer', 'congratulations', 'pleased to extend',
                                      'compensation package', 'welcome to the team']):
        return 'offer'

    # Check for assessments/challenges
    if any(word in text for word in ['assessment', 'coding challenge', 'take-home',
                                      'technical exercise', 'complete the', 'test project']):
        return 'assessment'

    # Check for rejections
    if any(word in text for word in ['unfortunately', 'not moving forward', 'other candidates',
                                      'decided to pursue', 'not selected', 'will not be moving',
                                      'unable to move forward', 'chosen to move forward with']):
        return 'rejection'

    # Check for application received confirmations
    if any(word in text for word in ['received your application', 'thank you for applying',
                                      'application has been', 'reviewing your', 'under review']):
        return 'received'

    # Default: general update
    return 'update'


def extract_company_from_email(from_email: str, subject: str) -> str:
    """
    Extract company name from email sender or subject.

    Args:
        from_email: Sender email address
        subject: Email subject line

    Returns:
        Extracted company name or 'Unknown'
    """
    # Try to extract from email domain
    if '@' in from_email:
        domain = from_email.split('@')[1].lower()

        # Remove common suffixes
        company = domain.replace('.com', '').replace('.io', '').replace('.co', '')
        company = company.replace('greenhouse', '').replace('lever', '').replace('workday', '')

        # Skip generic domains
        if company not in ['gmail', 'outlook', 'yahoo', 'hotmail', 'mail', 'email']:
            return company.title()

    # Try to extract from subject (e.g., "Your Application at Company Name")
    patterns = [
        r'at\s+([A-Z][A-Za-z0-9\s&.,-]+)',
        r'with\s+([A-Z][A-Za-z0-9\s&.,-]+)',
        r'from\s+([A-Z][A-Za-z0-9\s&.,-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, subject)
        if match:
            company = match.group(1).strip()
            # Remove common trailing words
            company = re.sub(r'\s+(team|recruiting|talent|careers)$', '', company, flags=re.IGNORECASE)
            return company[:50]  # Limit length

    return 'Unknown'


def fuzzy_match_company(email_company: str, conn) -> Optional[str]:
    """
    Find matching job in database by fuzzy company name matching.

    Args:
        email_company: Company name extracted from email
        conn: Database connection

    Returns:
        job_id if match found, None otherwise
    """
    # Try exact match first
    result = conn.execute(
        "SELECT job_id FROM jobs WHERE LOWER(company) = ? AND status IN ('applied', 'interviewing')",
        (email_company.lower(),)
    ).fetchone()

    if result:
        return result[0]

    # Try partial match (company name contains or is contained in email company)
    applied_jobs = conn.execute(
        "SELECT job_id, company FROM jobs WHERE status IN ('applied', 'interviewing')"
    ).fetchall()

    for job in applied_jobs:
        job_id, job_company = job[0], job[1].lower()
        email_comp_lower = email_company.lower()

        # Check if one contains the other
        if job_company in email_comp_lower or email_comp_lower in job_company:
            return job_id

        # Check for common abbreviations (e.g., "Meta" vs "Facebook")
        company_map = {
            'meta': 'facebook',
            'google': 'alphabet',
            'aws': 'amazon',
        }

        for key, value in company_map.items():
            if (key in job_company and value in email_comp_lower) or \
               (value in job_company and key in email_comp_lower):
                return job_id

    return None


def scan_followup_emails(days_back: int = 30) -> List[Dict]:
    """
    Scan Gmail for follow-up emails (interviews, rejections, offers).

    Checks both inbox and spam folders for responses to job applications.
    Automatically classifies emails and matches them to jobs in database.

    Args:
        days_back: How many days back to scan (default: 30)

    Returns:
        List of follow-up email dictionaries
    """
    service = get_gmail_service()
    after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

    # Queries for different types of follow-ups
    queries = [
        # Interview requests
        f'(subject:interview OR subject:"phone screen" OR subject:"next steps" OR subject:"schedule") after:{after_date}',

        # Rejections (check spam too!)
        f'(subject:unfortunately OR subject:"not selected" OR subject:"other candidates" OR subject:"decided to pursue") after:{after_date}',

        # Offers
        f'(subject:offer OR subject:congratulations OR subject:"pleased to extend") after:{after_date}',

        # Assessments
        f'(subject:assessment OR subject:"coding challenge" OR subject:"take-home") after:{after_date}',

        # Application confirmations
        f'(subject:"received your application" OR subject:"thank you for applying") after:{after_date}',
    ]

    followups = []
    seen_message_ids = set()

    # Scan both INBOX and SPAM
    for folder in ['INBOX', '[Gmail]/Spam']:
        for query in queries:
            try:
                # Modify query to search in specific folder
                if folder == '[Gmail]/Spam':
                    search_query = f'in:spam {query}'
                else:
                    search_query = query

                results = service.users().messages().list(userId='me', q=search_query, maxResults=50).execute()
                messages = results.get('messages', [])

                for msg_info in messages:
                    msg_id = msg_info['id']

                    # Skip duplicates
                    if msg_id in seen_message_ids:
                        continue
                    seen_message_ids.add(msg_id)

                    try:
                        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

                        # Extract email details
                        headers = message.get('payload', {}).get('headers', [])
                        subject = ''
                        from_email = ''

                        for header in headers:
                            if header['name'].lower() == 'subject':
                                subject = header['value']
                            elif header['name'].lower() == 'from':
                                from_email = header['value']

                        snippet = message.get('snippet', '')
                        email_date = datetime.fromtimestamp(int(message.get('internalDate', 0)) / 1000).isoformat()

                        # Classify email type
                        email_type = classify_followup_email(subject, snippet)

                        # Extract company name
                        company = extract_company_from_email(from_email, subject)

                        # Try to match to a job in database
                        conn = get_db()
                        job_id = fuzzy_match_company(company, conn)
                        conn.close()

                        followups.append({
                            'company': company,
                            'subject': subject[:200],
                            'type': email_type,
                            'snippet': snippet[:500],
                            'email_date': email_date,
                            'job_id': job_id,
                            'in_spam': folder == '[Gmail]/Spam'
                        })

                        print(f"📧 {email_type.upper()}: {company} - {subject[:50]}... (spam: {folder == '[Gmail]/Spam'})")

                    except Exception as e:
                        print(f"Error parsing follow-up email {msg_id}: {e}")
                        continue

            except Exception as e:
                print(f"Query failed - {search_query}: {e}")
                continue

    print(f"\n✅ Follow-up scan complete: {len(followups)} emails found")
    return followups

# ============== AI Filtering & Scoring ==============
def load_resumes() -> str:
    """
    Load all resume files from configured paths.

    Reads resume files specified in config.yaml and concatenates them
    with separators for AI analysis. Supports both .txt and .md formats.

    Returns:
        Combined resume text from all configured files

    Raises:
        FileNotFoundError: If configured resume files don't exist
    """
    resumes = []

    # Load resumes from configured file paths
    for resume_path in CONFIG.resume_files:
        full_path = APP_DIR / resume_path
        if full_path.exists():
            resumes.append(full_path.read_text())
        else:
            print(f"⚠️  Warning: Resume file not found: {resume_path}")

    if not resumes:
        raise FileNotFoundError(
            "No resume files found! Add resume files to the resumes/ directory "
            "and configure them in config.yaml"
        )

    return "\n\n---\n\n".join(resumes)


def ai_filter_and_score(job: Dict, resume_text: str) -> Tuple[bool, int, str]:
    """
    AI-based job filtering and baseline scoring using Claude.

    Uses Claude AI to:
    1. Filter jobs by location preferences (from config.yaml)
    2. Filter overly senior/junior roles based on experience level
    3. Generate a baseline score (1-100) based on location, seniority, company, and tech stack

    Jobs that don't match location preferences or are way outside experience level
    are filtered out to reduce noise.

    Args:
        job: Job dictionary with title, company, location, and raw_text
        resume_text: Combined text from all user's resumes

    Returns:
        Tuple of (should_keep, baseline_score, reason):
        - should_keep: Boolean indicating if job passes filters
        - baseline_score: Integer score from 1-100
        - reason: String explanation of filtering decision

    Example:
        keep, score, reason = ai_filter_and_score(job, resume_text)
        if keep:
            print(f"Job scored {score}/100: {reason}")
    """
    client = anthropic.Anthropic()

    # Generate location filter prompt from user's config
    location_filter = CONFIG.get_location_filter_prompt()

    # Get experience level preferences
    exp_level = CONFIG.experience_level
    exclude_keywords = CONFIG.exclude_keywords

    # Build exclusion keyword string for prompt
    exclude_str = ", ".join(exclude_keywords) if exclude_keywords else "None"

    prompt = f"""Analyze this job for filtering and baseline scoring.

CANDIDATE'S RESUME:
{resume_text}

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Brief Description: {job['raw_text'][:500]}

INSTRUCTIONS:
1. LOCATION FILTER:
{location_filter}

2. TITLE FILTER: Auto-reject if title contains: {exclude_str}

3. SKILL LEVEL: Keep ALL levels but score appropriately:
   - Entry-level/Junior roles: Give lower score (30-50) but KEEP if candidate has {exp_level.get('min_years', 1)}+ years
   - Mid-level matching candidate's {exp_level.get('current_level', 'mid')} level: High score (60-85)
   - Senior roles slightly above resume: Keep with moderate score (50-70)
   - ONLY filter if extremely mismatched: VP/Director/C-level roles, or requires {exp_level.get('max_years', 10)}+ more years than candidate has

4. BASELINE SCORE (1-100):
   - Location: Use score bonuses from location preferences (Remote=100, primary city=95, etc.)
   - Seniority: Perfect match=+20, Entry-level=-15, Slightly senior=+0, Too senior=-30
   - Company: Top tier (FAANG/unicorn)=+10, Well-known=+5, Startup=+3, Unknown=+0
   - Tech stack overlap: High=+15, Medium=+5, Low=-10

Return JSON only:
{{
    "keep": <bool>,
    "baseline_score": <1-100>,
    "filter_reason": "kept: good location match" OR "filtered: outside target location",
    "location_match": "remote|primary_location|secondary_location|excluded",
    "skill_level_match": "entry_level|good_fit|slightly_senior|too_senior"
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

def analyze_job(job: Dict, resume_text: str) -> Dict:
    """
    Perform detailed job qualification analysis using Claude AI.

    This is the "full analysis" that runs after a job passes baseline filtering.
    Provides:
    - Detailed qualification score (1-100)
    - Specific strengths that match the role
    - Gaps or missing requirements
    - Honest recommendation on whether to apply
    - Which resume variant to use

    Args:
        job: Job dictionary with title, company, location, and details
        resume_text: Combined text from all user's resumes

    Returns:
        Dictionary containing:
        - qualification_score: Detailed score from 1-100
        - should_apply: Boolean recommendation
        - strengths: List of matching skills/experience
        - gaps: List of missing requirements
        - recommendation: 2-3 sentence honest assessment
        - resume_to_use: Which resume variant to submit (backend|cloud|fullstack)
    """
    client = anthropic.Anthropic()
    
    prompt = f"""Analyze job fit with strict accuracy. Respond ONLY with valid JSON.

CANDIDATE'S RESUME:
{resume_text}

JOB LISTING:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Details: {job['raw_text']}

CRITICAL INSTRUCTIONS:
1. ONLY mention job titles/roles the candidate has ACTUALLY held (check resume carefully)
2. ONLY cite technologies/skills explicitly listed in resume
3. should_apply = true ONLY if qualification_score >= 65 AND no major dealbreakers
4. Dealbreakers: wrong tech stack, requires 5+ years when candidate has 2, senior leadership role

SCORING RUBRIC:
- 80-100: Strong match, most requirements met, similar past roles
- 60-79: Good match, can do the job with minor gaps
- 40-59: Partial match, significant skill gaps but learnable
- 1-39: Weak match, wrong seniority/stack/domain

Return JSON:
{{
    "qualification_score": <1-100>,
    "should_apply": <bool>,
    "strengths": ["actual skills from resume that match", "relevant past experience"],
    "gaps": ["missing requirements", "areas to improve"],
    "recommendation": "2-3 sentence honest assessment",
    "resume_to_use": "backend|cloud|fullstack"
}}
"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        match = re.search(r'\{[\s\S]*\}', response.content[0].text)
        return json.loads(match.group()) if match else {}
    except Exception as e:
        print(f"Analysis error: {e}")
        return {"qualification_score": 0, "should_apply": False, "recommendation": str(e)}

def generate_cover_letter(job: Dict, resume_text: str) -> str:
    """
    Generate a tailored cover letter using Claude AI.

    Creates a personalized cover letter based on:
    - Job requirements and company
    - Candidate's resume and verified experience
    - Previous AI analysis strengths

    The cover letter follows professional best practices:
    - 3-4 paragraphs, under 350 words
    - Only cites actual resume content (no extrapolation)
    - Includes specific examples and metrics
    - Professional but enthusiastic tone

    Args:
        job: Job dictionary with title, company, location, and analysis
        resume_text: Combined text from all user's resumes

    Returns:
        Formatted cover letter text ready to use
    """
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

# ============== Scoring & Sorting ==============
def calculate_weighted_score(baseline_score: int, email_date: str) -> float:
    """
    Calculate weighted score combining qualification and recency.

    Jobs are sorted by a weighted score that considers both:
    - How well you qualify (70% weight)
    - How recent the posting is (30% weight)

    This ensures high-quality matches rise to the top, while still
    prioritizing newer opportunities over old ones.

    Recency scoring:
    - Posted today: 100 points
    - Linear decay: Loses ~3.33 points per day
    - After 30 days: 0 recency points

    Args:
        baseline_score: AI-generated qualification score (1-100)
        email_date: ISO format date string when job was posted/received

    Returns:
        Weighted score as a float (e.g., 85.67)

    Example:
        - Job with score 90 posted today: 90*0.7 + 100*0.3 = 93.0
        - Job with score 90 posted 10 days ago: 90*0.7 + 66.7*0.3 = 83.0
    """
    # Calculate recency score: 100 for today, linear decay to 0 over 30 days
    try:
        date_obj = datetime.fromisoformat(email_date)
        days_old = (datetime.now() - date_obj).days
        recency_score = max(0, 100 - (days_old * 3.33))  # ~3.33 points lost per day
    except:
        recency_score = 0  # Default to 0 if date parsing fails

    # 70% qualification, 30% recency
    weighted = (baseline_score * 0.7) + (recency_score * 0.3)
    return round(weighted, 2)

# ============== Flask Routes ==============
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Hammy the Hire Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="max-w-6xl mx-auto p-6">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold">🐷 Hammy the Hire Tracker</h1>
                <p class="text-gray-600">Go HAM on your job search!</p>
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
                <button onclick="scanFollowups()" class="bg-orange-600 text-white px-4 py-2 rounded hover:bg-orange-700">
                    📬 Scan Follow-Ups
                </button>
            </div>
        </div>
        
        <div class="mb-6 border-b">
            <button onclick="showTab('jobs')" id="tab-jobs" class="px-4 py-2 font-semibold border-b-2 border-blue-600">
                Jobs
            </button>
            <button onclick="showTab('followups')" id="tab-followups" class="px-4 py-2 font-semibold text-gray-600">
                📧 Follow-Ups
            </button>
            <button onclick="showTab('watchlist')" id="tab-watchlist" class="px-4 py-2 font-semibold text-gray-600">
                Watchlist
            </button>
        </div>
        
        <div id="jobs-tab">
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

        <div id="followups-tab" class="hidden">
            <div id="followup-stats" class="grid grid-cols-5 gap-4 mb-6"></div>
            <div id="followups" class="space-y-3"></div>
        </div>

        <div id="watchlist-tab" class="hidden">
            <div class="bg-white rounded-lg shadow p-6 mb-4">
                <h2 class="text-xl font-bold mb-4">Add Company to Watchlist</h2>
                <div class="space-y-3">
                    <input type="text" id="watch-company" placeholder="Company name" 
                           class="w-full px-4 py-2 border rounded">
                    <input type="url" id="watch-url" placeholder="Careers page URL" 
                           class="w-full px-4 py-2 border rounded">
                    <textarea id="watch-notes" placeholder="Notes (e.g., 'Not hiring now, check Q2')" 
                              class="w-full px-4 py-2 border rounded" rows="3"></textarea>
                    <button onclick="addToWatchlist()" class="bg-blue-600 text-white px-4 py-2 rounded">
                        Add to Watchlist
                    </button>
                </div>
            </div>
            
            <div id="watchlist-items" class="space-y-3"></div>
        </div>
    </div>
    
    <script>
        let allJobs = [];
        let currentTab = 'jobs';
        
        function showTab(tab) {
            currentTab = tab;
            document.getElementById('jobs-tab').classList.toggle('hidden', tab !== 'jobs');
            document.getElementById('followups-tab').classList.toggle('hidden', tab !== 'followups');
            document.getElementById('watchlist-tab').classList.toggle('hidden', tab !== 'watchlist');

            document.getElementById('tab-jobs').className = tab === 'jobs'
                ? 'px-4 py-2 font-semibold border-b-2 border-blue-600'
                : 'px-4 py-2 font-semibold text-gray-600';
            document.getElementById('tab-followups').className = tab === 'followups'
                ? 'px-4 py-2 font-semibold border-b-2 border-blue-600'
                : 'px-4 py-2 font-semibold text-gray-600';
            document.getElementById('tab-watchlist').className = tab === 'watchlist'
                ? 'px-4 py-2 font-semibold border-b-2 border-blue-600'
                : 'px-4 py-2 font-semibold text-gray-600';

            if (tab === 'followups') loadFollowups();
            if (tab === 'watchlist') loadWatchlist();
        }
        
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
                
                // Status colors
                const statusColors = {
                    'new': 'bg-gray-100 border-gray-300',
                    'interested': 'bg-blue-50 border-blue-300',
                    'applied': 'bg-green-50 border-green-400',
                    'interviewing': 'bg-purple-50 border-purple-300',
                    'passed': 'bg-gray-50 border-gray-200',
                    'rejected': 'bg-red-50 border-red-200'
                };
                
                const statusColor = statusColors[job.status] || statusColors['new'];
                const viewedStyle = job.viewed ? 'opacity-90 bg-gray-100' : '';
                
                return `
                <div class="bg-white ${viewedStyle} rounded-lg shadow p-4 border-l-4 ${statusColor}">
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
                            
                            ${analysis.recommendation ? `
                            <div class="mt-2 p-2 bg-blue-50 border-l-2 border-blue-400 rounded text-sm">
                                <strong class="text-blue-900">AI Insight:</strong>
                                <p class="text-gray-700 mt-1">${analysis.recommendation}</p>
                            </div>
                            ` : ''}
                        </div>
                        <div class="flex items-center gap-2">
                            <select onchange="updateStatus('${job.job_id}', this.value)" 
                                    class="text-sm border rounded px-2 py-1">
                                ${['new','interested','applied','interviewing','passed','rejected'].map(s => 
                                    `<option value="${s}" ${job.status === s ? 'selected' : ''}>${s}</option>`
                                ).join('')}
                            </select>
                            <button onclick="addToWatchlistFromJob('${job.company}', '${job.url}')" 
                                    class="text-yellow-600 hover:text-yellow-700 p-1" title="Add to Watchlist">
                                ⭐
                            </button>
                            <button onclick="hideJob('${job.job_id}')" 
                                    class="text-gray-400 hover:text-red-600 p-1" title="Hide">
                                ✕
                            </button>
                            <a href="${job.url}" target="_blank" class="text-blue-600 hover:underline text-sm"
                               onclick="markViewed('${job.job_id}')">View</a>
                        </div>
                    </div>
                    
                    ${analysis.strengths ? `
                    <details class="mt-3">
                        <summary class="cursor-pointer text-sm text-gray-500">Full Analysis</summary>
                        
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
        
        async function loadWatchlist() {
            const res = await fetch('/api/watchlist');
            const data = await res.json();
            
            const container = document.getElementById('watchlist-items');
            if (data.items.length === 0) {
                container.innerHTML = '<p class="text-gray-500 text-center py-8">No companies on watchlist yet</p>';
                return;
            }
            
            container.innerHTML = data.items.map(item => `
                <div class="bg-white rounded-lg shadow p-4">
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <h3 class="font-semibold text-lg">${item.company}</h3>
                            <a href="${item.url}" target="_blank" class="text-blue-600 hover:underline text-sm">
                                ${item.url}
                            </a>
                            ${item.notes ? `<p class="text-gray-600 text-sm mt-2">${item.notes}</p>` : ''}
                            <p class="text-gray-400 text-xs mt-1">Added ${formatDate(item.created_at)}</p>
                        </div>
                        <button onclick="removeFromWatchlist(${item.id})" 
                                class="text-red-600 hover:text-red-700">
                            Remove
                        </button>
                    </div>
                </div>
            `).join('');
        }
        
        async function addToWatchlist() {
            const company = document.getElementById('watch-company').value.trim();
            const url = document.getElementById('watch-url').value.trim();
            const notes = document.getElementById('watch-notes').value.trim();
            
            if (!company) {
                alert('Company name required');
                return;
            }
            
            await fetch('/api/watchlist', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({company, url, notes})
            });
            
            document.getElementById('watch-company').value = '';
            document.getElementById('watch-url').value = '';
            document.getElementById('watch-notes').value = '';
            
            loadWatchlist();
        }
        
        function addToWatchlistFromJob(company, url) {
            document.getElementById('watch-company').value = company;
            document.getElementById('watch-url').value = url;
            showTab('watchlist');
        }
        
        async function removeFromWatchlist(id) {
            if (!confirm('Remove from watchlist?')) return;
            await fetch(`/api/watchlist/${id}`, {method: 'DELETE'});
            loadWatchlist();
        }
        
        async function scanWWR() {
            const btn = event.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Scanning WWR...';
            
            try {
                await fetch('/api/wwr', {method: 'POST'});
                // Poll for updates
                setTimeout(loadJobs, 3000);
                setTimeout(loadJobs, 10000);
                setTimeout(loadJobs, 20000);
            } catch (err) {
                console.error('WWR scan failed:', err);
            }
            
            btn.disabled = false;
            btn.textContent = originalText;
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
        
        async function markViewed(jobId) {
            await fetch(`/api/jobs/${jobId}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({viewed: 1})
            });
            setTimeout(() => loadJobs(), 500);
        }
        
        async function hideJob(jobId) {
            if (!confirm('Hide this job?')) return;
            await fetch(`/api/jobs/${jobId}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: 'hidden'})
            });
            loadJobs();
        }
        
        async function generateCoverLetter(jobId) {
            event.target.disabled = true;
            event.target.textContent = 'Generating...';
            await fetch(`/api/jobs/${jobId}/cover-letter`, {method: 'POST'});
            loadJobs();
        }

        async function scanFollowups() {
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Scanning Follow-Ups...';
            try {
                const res = await fetch('/api/scan-followups', {method: 'POST'});
                const data = await res.json();
                alert(`Found ${data.found} follow-ups!\\n${data.new} new\\n${data.updated_jobs} jobs updated`);
                await loadFollowups();
                await loadJobs();
            } finally {
                btn.disabled = false;
                btn.textContent = '📬 Scan Follow-Ups';
            }
        }

        async function loadFollowups() {
            const res = await fetch('/api/followups');
            const data = await res.json();

            // Display statistics
            const stats = data.stats;
            document.getElementById('followup-stats').innerHTML = `
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <div class="text-2xl font-bold">${stats.total}</div>
                    <div class="text-sm text-gray-600">Total Responses</div>
                </div>
                <div class="bg-green-100 rounded-lg shadow p-4 text-center">
                    <div class="text-2xl font-bold text-green-700">🎉 ${stats.interviews}</div>
                    <div class="text-sm text-gray-600">Interviews</div>
                </div>
                <div class="bg-blue-100 rounded-lg shadow p-4 text-center">
                    <div class="text-2xl font-bold text-blue-700">🎁 ${stats.offers}</div>
                    <div class="text-sm text-gray-600">Offers</div>
                </div>
                <div class="bg-red-100 rounded-lg shadow p-4 text-center">
                    <div class="text-2xl font-bold text-red-700">😞 ${stats.rejections}</div>
                    <div class="text-sm text-gray-600">Rejections</div>
                </div>
                <div class="bg-purple-100 rounded-lg shadow p-4 text-center">
                    <div class="text-2xl font-bold text-purple-700">${stats.response_rate}%</div>
                    <div class="text-sm text-gray-600">Response Rate</div>
                </div>
            `;

            // Display follow-ups
            const followupsHTML = data.followups.map(f => {
                const typeIcons = {
                    'interview': '🎉',
                    'rejection': '😞',
                    'offer': '🎁',
                    'assessment': '📋',
                    'received': '✅',
                    'update': '📧'
                };
                const typeColors = {
                    'interview': 'bg-green-100 border-green-300',
                    'rejection': 'bg-red-100 border-red-300',
                    'offer': 'bg-blue-100 border-blue-300',
                    'assessment': 'bg-purple-100 border-purple-300',
                    'received': 'bg-gray-100 border-gray-300',
                    'update': 'bg-yellow-100 border-yellow-300'
                };

                const icon = typeIcons[f.type] || '📧';
                const color = typeColors[f.type] || 'bg-gray-100 border-gray-300';
                const matchBadge = f.job_id ? '<span class="text-xs bg-blue-500 text-white px-2 py-1 rounded">Matched</span>' : '';
                const spamBadge = f.in_spam ? '<span class="text-xs bg-red-500 text-white px-2 py-1 rounded">Was in Spam!</span>' : '';

                return `
                    <div class="bg-white rounded-lg shadow border-l-4 ${color} p-4">
                        <div class="flex justify-between items-start mb-2">
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="text-2xl">${icon}</span>
                                    <h3 class="font-bold text-lg">${f.type.toUpperCase()}: ${f.company}</h3>
                                    ${matchBadge}
                                    ${spamBadge}
                                </div>
                                <p class="text-sm text-gray-600">${f.subject}</p>
                            </div>
                            <div class="text-right">
                                <div class="text-sm text-gray-500">${formatDate(f.email_date)}</div>
                                ${f.title ? `<div class="text-xs text-blue-600 mt-1">${f.title}</div>` : ''}
                            </div>
                        </div>
                        <p class="text-sm text-gray-700 mt-2">${f.snippet}</p>
                        ${f.url ? `<a href="${f.url}" target="_blank" class="text-blue-600 text-sm hover:underline mt-2 inline-block">View Job →</a>` : ''}
                    </div>
                `;
            }).join('');

            document.getElementById('followups').innerHTML = followupsHTML ||
                '<div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">No follow-ups yet. Click "📬 Scan Follow-Ups" to check your email!</div>';
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
    show_hidden = request.args.get('show_hidden', 'false') == 'true'
    
    conn = get_db()
    query = "SELECT * FROM jobs WHERE is_filtered = 0"
    params = []
    
    if not show_hidden:
        query += " AND status != 'hidden'"
    
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
    all_jobs = [dict(row) for row in conn.execute("SELECT status, baseline_score FROM jobs WHERE is_filtered = 0 AND status != 'hidden'").fetchall()]
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
    
    # Build update query dynamically
    allowed_fields = ['status', 'notes', 'viewed', 'applied_date', 'interview_date']
    updates = []
    params = []
    
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(job_id)
        
        query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
        conn.execute(query, params)
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
    duplicate_count = 0
    
    try:
        for job in jobs:
            # Check if job already exists in DB
            existing = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job['job_id'],)).fetchone()
            if existing:
                duplicate_count += 1
                print(f"⏭️  Skipping duplicate: {job['title'][:50]}")
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
                conn.commit()  # Commit immediately
                new_count += 1
                print(f"✓ Kept: {job['title'][:50]} - Score {baseline_score} - {reason}")
            else:
                # Store filtered jobs but mark them
                conn.execute('''
                    INSERT INTO jobs (job_id, title, company, location, url, source, raw_text, 
                                     baseline_score, created_at, updated_at, email_date, is_filtered, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ''', (job['job_id'], job['title'], job['company'], job['location'], 
                      job['url'], job['source'], job['raw_text'], baseline_score,
                      job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at']), reason))
                conn.commit()  # Commit immediately
                filtered_count += 1
                print(f"✗ Filtered: {job['title'][:50]} - {reason}")
    finally:
        conn.close()
    
    print(f"\n📊 Scan Summary:")
    print(f"   - Found: {len(jobs)} jobs")
    print(f"   - New & kept: {new_count}")
    print(f"   - Filtered: {filtered_count}")
    print(f"   - Duplicates skipped: {duplicate_count}")
    
    return jsonify({
        'found': len(jobs), 
        'new': new_count, 
        'filtered': filtered_count,
        'duplicates': duplicate_count
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
        
        # Only change status if it's still 'new', otherwise preserve user's choice
        new_status = job['status']
        if job['status'] == 'new':
            new_status = 'interested' if analysis.get('should_apply') else 'new'
        
        conn.execute(
            "UPDATE jobs SET score = ?, analysis = ?, status = ?, updated_at = ? WHERE job_id = ?",
            (analysis.get('qualification_score', 0), json.dumps(analysis),
             new_status,
             datetime.now().isoformat(), job['job_id'])
        )
        conn.commit()
    
    conn.close()
    return jsonify({'analyzed': len(jobs)})

@app.route('/api/scan-followups', methods=['POST'])
def api_scan_followups():
    """
    Scan Gmail for follow-up emails (interviews, rejections, offers).
    Automatically updates job statuses and stores follow-ups in database.
    """
    followups = scan_followup_emails(days_back=30)

    conn = get_db()
    new_count = 0
    updated_jobs = 0

    try:
        for followup in followups:
            # Check if this follow-up already exists
            existing = conn.execute(
                "SELECT id FROM followups WHERE company = ? AND subject = ? AND email_date = ?",
                (followup['company'], followup['subject'], followup['email_date'])
            ).fetchone()

            if existing:
                continue  # Skip duplicates

            # Insert follow-up into database
            conn.execute(
                '''INSERT INTO followups (company, subject, type, snippet, email_date, job_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (followup['company'], followup['subject'], followup['type'],
                 followup['snippet'], followup['email_date'], followup['job_id'],
                 datetime.now().isoformat())
            )
            conn.commit()
            new_count += 1

            # Auto-update job status if matched
            if followup['job_id']:
                job = conn.execute("SELECT status FROM jobs WHERE job_id = ?", (followup['job_id'],)).fetchone()

                if job:
                    current_status = job[0]
                    new_status = current_status

                    # Update status based on follow-up type
                    if followup['type'] == 'rejection' and current_status != 'rejected':
                        new_status = 'rejected'
                    elif followup['type'] == 'interview' and current_status not in ['interviewing', 'offered', 'accepted']:
                        new_status = 'interviewing'
                    elif followup['type'] == 'offer' and current_status not in ['offered', 'accepted']:
                        new_status = 'offered'

                    if new_status != current_status:
                        conn.execute(
                            "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                            (new_status, datetime.now().isoformat(), followup['job_id'])
                        )
                        conn.commit()
                        updated_jobs += 1
                        print(f"✓ Updated {followup['company']} → {new_status}")

    finally:
        conn.close()

    return jsonify({
        'found': len(followups),
        'new': new_count,
        'updated_jobs': updated_jobs
    })

@app.route('/api/followups', methods=['GET'])
def api_get_followups():
    """Get all follow-up emails with associated job info."""
    conn = get_db()

    followups = conn.execute('''
        SELECT f.*, j.title, j.company as job_company, j.url
        FROM followups f
        LEFT JOIN jobs j ON f.job_id = j.job_id
        ORDER BY f.email_date DESC
        LIMIT 100
    ''').fetchall()

    # Calculate statistics
    stats = {
        'total': len(followups),
        'interviews': len([f for f in followups if f['type'] == 'interview']),
        'rejections': len([f for f in followups if f['type'] == 'rejection']),
        'offers': len([f for f in followups if f['type'] == 'offer']),
        'assessments': len([f for f in followups if f['type'] == 'assessment']),
    }

    # Calculate response rate
    applied_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('applied', 'interviewing', 'offered', 'rejected')").fetchone()[0]
    if applied_count > 0:
        stats['response_rate'] = round((stats['total'] / applied_count) * 100, 1)
    else:
        stats['response_rate'] = 0

    conn.close()

    return jsonify({
        'followups': [dict(row) for row in followups],
        'stats': stats
    })

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
    """Instant analysis for browser extension with strict accuracy."""
    data = request.json
    
    title = data.get('title', '')
    company = data.get('company', 'Unknown')
    description = data.get('description', '')
    
    if not title or not description:
        return jsonify({'error': 'title and description required'}), 400
    
    resume_text = load_resumes()
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    client = anthropic.Anthropic()
    
    prompt = f"""Analyze job fit with STRICT ACCURACY. Only mention roles/skills candidate ACTUALLY has.

CANDIDATE'S RESUME:
{resume_text}

JOB LISTING:
Title: {title}
Company: {company}
Description: {description[:2000]}

CRITICAL RULES:
1. ONLY cite job titles the candidate has held (check resume carefully)
2. ONLY mention technologies/tools explicitly in resume
3. Do NOT invent experience or extrapolate skills
4. should_apply = true ONLY if score >= 65 AND no major red flags
5. Red flags: requires 5+ years when candidate has 2, wrong tech stack entirely, senior leadership position

SCORING:
- 80-100: Strong match, candidate has done similar work
- 60-79: Good match, meets most requirements with minor gaps
- 40-59: Partial match, missing key skills but could learn
- 20-39: Weak match, significant gaps in experience/skills
- 1-19: Very poor match, wrong level or domain entirely

Return ONLY valid JSON:
{{
    "qualification_score": <1-100>,
    "should_apply": <bool>,
    "strengths": ["actual matching skills from resume", "relevant experience candidate has"],
    "gaps": ["specific missing requirements", "areas to develop"],
    "recommendation": "Honest 2-3 sentence assessment based on actual resume fit",
    "resume_to_use": "backend|cloud|fullstack"
}}
"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text
        match = re.search(r'\{[\s\S]*\}', response_text)
        
        if match:
            analysis = json.loads(match.group())
        else:
            raise ValueError("No JSON in response")
        
        return jsonify({'analysis': analysis, 'job': {'title': title, 'company': company}})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wwr', methods=['POST'])
def api_scan_wwr():
    """Scan WWR with AI filtering."""
    print("🌐 Starting WWR scan...")
    jobs = fetch_wwr_jobs()
    print(f"📥 Fetched {len(jobs)} jobs from RSS feeds")
    
    resume_text = load_resumes()
    
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    conn = get_db()
    new_count = 0
    filtered_count = 0
    duplicate_count = 0
    
    try:
        for i, job in enumerate(jobs, 1):
            print(f"Processing {i}/{len(jobs)}: {job['title'][:50]}...")
            
            existing = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job['job_id'],)).fetchone()
            if existing:
                duplicate_count += 1
                print(f"  ⏭️  Duplicate")
                continue
            
            keep, baseline_score, reason = ai_filter_and_score(job, resume_text)
            
            if keep:
                conn.execute('''
                    INSERT INTO jobs (job_id, title, company, location, url, source, raw_text, 
                                     baseline_score, created_at, updated_at, email_date, is_filtered)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ''', (job['job_id'], job['title'], job['company'], job['location'], 
                      job['url'], job['source'], job.get('description', job['raw_text']), baseline_score,
                      job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at'])))
                conn.commit()
                new_count += 1
                print(f"  ✓ Kept - Score {baseline_score}")
            else:
                conn.execute('''
                    INSERT INTO jobs (job_id, title, company, location, url, source, raw_text, 
                                     baseline_score, created_at, updated_at, email_date, is_filtered, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ''', (job['job_id'], job['title'], job['company'], job['location'], 
                      job['url'], job['source'], job.get('description', job['raw_text']), baseline_score,
                      job['created_at'], datetime.now().isoformat(), job.get('email_date', job['created_at']), reason))
                conn.commit()
                filtered_count += 1
                print(f"  ✗ Filtered - {reason[:50]}")
    finally:
        conn.close()
    
    print(f"\n✅ WWR Scan Complete: {new_count} new, {filtered_count} filtered, {duplicate_count} duplicates")
    return jsonify({'found': len(jobs), 'new': new_count, 'filtered': filtered_count, 'duplicates': duplicate_count})

@app.route('/api/generate-cover-letter', methods=['POST'])
def api_generate_cover_letter():
    """Generate cover letter for extension with accurate resume matching."""
    data = request.json
    job = data.get('job', {})
    analysis = data.get('analysis', {})
    
    resume_text = load_resumes()
    if not resume_text:
        return jsonify({'error': 'No resumes found'}), 400
    
    client = anthropic.Anthropic()
    
    strengths = ', '.join(analysis.get('strengths', []))
    
    prompt = f"""Write a tailored cover letter (3-4 paragraphs, under 350 words).

CRITICAL: Only mention experience and skills the candidate ACTUALLY has from their resume.

CANDIDATE'S RESUME:
{resume_text}

JOB:
Title: {job.get('title')}
Company: {job.get('company')}
Description: {job.get('description', '')[:1000]}

KEY STRENGTHS (verified from resume):
{strengths}

INSTRUCTIONS:
1. ONLY cite projects, roles, and technologies from the resume
2. Use specific examples and metrics from resume
3. Do NOT invent experience or extrapolate skills
4. Keep professional but enthusiastic tone
5. 3-4 paragraphs: opening, 2 body (experience/fit), closing

Write only the cover letter text (no subject line):"""
    
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
    """Generate interview answer with accurate resume references."""
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
    
    prompt = f"""Generate a strong interview answer using ONLY actual resume content.

QUESTION: {question}

JOB CONTEXT:
Title: {job.get('title')}
Company: {job.get('company')}
Description: {job.get('description', '')[:500]}

CANDIDATE'S RESUME:
{resume_text}

VERIFIED ANALYSIS:
Strengths: {', '.join(analysis.get('strengths', []))}
Gaps: {', '.join(analysis.get('gaps', []))}

CRITICAL RULES:
1. ONLY cite projects, roles, metrics from the actual resume
2. Do NOT invent experience or extrapolate skills
3. Use specific examples with concrete details
4. Be honest about gaps but frame positively
5. Natural, conversational tone (not rehearsed)

Generate 2-3 paragraph answer (150-200 words):"""
    
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

@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    conn = get_db()
    items = [dict(row) for row in conn.execute(
        "SELECT * FROM watchlist ORDER BY created_at DESC"
    ).fetchall()]
    conn.close()
    return jsonify({'items': items})

@app.route('/api/watchlist', methods=['POST'])
def add_watchlist():
    data = request.json
    company = data.get('company', '').strip()
    url = data.get('url', '').strip()
    notes = data.get('notes', '').strip()
    
    if not company:
        return jsonify({'error': 'Company required'}), 400
    
    conn = get_db()
    conn.execute(
        "INSERT INTO watchlist (company, url, notes, created_at) VALUES (?, ?, ?, ?)",
        (company, url, notes, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/watchlist/<int:watch_id>', methods=['DELETE'])
def delete_watchlist(watch_id):
    conn = get_db()
    conn.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============== External Applications ==============
@app.route('/api/external-applications', methods=['GET'])
def get_external_applications():
    """
    Get all external applications with optional filtering.
    Query params: status, company, source
    """
    conn = get_db()

    # Build query with optional filters
    query = "SELECT * FROM external_applications WHERE 1=1"
    params = []

    if request.args.get('status'):
        query += " AND status = ?"
        params.append(request.args.get('status'))

    if request.args.get('company'):
        query += " AND company LIKE ?"
        params.append(f"%{request.args.get('company')}%")

    if request.args.get('source'):
        query += " AND source = ?"
        params.append(request.args.get('source'))

    query += " ORDER BY applied_date DESC"

    applications = [dict(row) for row in conn.execute(query, params).fetchall()]
    conn.close()

    return jsonify({'applications': applications})

@app.route('/api/external-applications', methods=['POST'])
def create_external_application():
    """
    Create a new external application.
    Required fields: title, company, applied_date, source
    """
    data = request.json

    # Validate required fields
    required_fields = ['title', 'company', 'applied_date', 'source']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Generate unique ID
    app_id = str(uuid.uuid4())[:16]

    # Get optional fields
    job_id = data.get('job_id')
    location = data.get('location', '')
    url = data.get('url', '')
    application_method = data.get('application_method', '')
    contact_name = data.get('contact_name', '')
    contact_email = data.get('contact_email', '')
    status = data.get('status', 'applied')
    follow_up_date = data.get('follow_up_date')
    notes = data.get('notes', '')
    is_linked_to_job = 1 if job_id else 0

    now = datetime.now().isoformat()

    conn = get_db()
    conn.execute('''
        INSERT INTO external_applications (
            app_id, job_id, title, company, location, url, source,
            application_method, applied_date, contact_name, contact_email,
            status, follow_up_date, notes, created_at, updated_at, is_linked_to_job
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        app_id, job_id, data['title'], data['company'], location, url, data['source'],
        application_method, data['applied_date'], contact_name, contact_email,
        status, follow_up_date, notes, now, now, is_linked_to_job
    ))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'app_id': app_id})

@app.route('/api/external-applications/<app_id>', methods=['GET'])
def get_external_application(app_id):
    """Get details of a specific external application."""
    conn = get_db()
    app = conn.execute(
        "SELECT * FROM external_applications WHERE app_id = ?",
        (app_id,)
    ).fetchone()
    conn.close()

    if not app:
        return jsonify({'error': 'Application not found'}), 404

    return jsonify({'application': dict(app)})

@app.route('/api/external-applications/<app_id>', methods=['PATCH'])
def update_external_application(app_id):
    """Update an external application."""
    data = request.json
    conn = get_db()

    # Build update query dynamically
    allowed_fields = [
        'title', 'company', 'location', 'url', 'source', 'application_method',
        'applied_date', 'contact_name', 'contact_email', 'status',
        'follow_up_date', 'notes', 'job_id', 'is_linked_to_job'
    ]
    updates = []
    params = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(app_id)

        query = f"UPDATE external_applications SET {', '.join(updates)} WHERE app_id = ?"
        conn.execute(query, params)
        conn.commit()

    conn.close()
    return jsonify({'success': True})

@app.route('/api/external-applications/<app_id>', methods=['DELETE'])
def delete_external_application(app_id):
    """Delete an external application."""
    conn = get_db()
    conn.execute("DELETE FROM external_applications WHERE app_id = ?", (app_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    # Initialize database
    init_db()
    RESUMES_DIR.mkdir(exist_ok=True)

    # Display startup info
    print("\n" + "="*60)
    print("🐷 Hammy the Hire Tracker - Go HAM on Your Job Search!")
    print("="*60)
    print(f"\n👤 User: {CONFIG.user_name}")
    print(f"📧 Email: {CONFIG.user_email}")
    print(f"📄 Resumes loaded: {len(CONFIG.resume_files)}")
    print(f"\n📁 Configuration: {APP_DIR / 'config.yaml'}")
    print(f"📁 Database: {DB_PATH}")
    print(f"📁 Gmail credentials: {CREDENTIALS_FILE}")
    print(f"\n💡 Hammy's Quick Start Guide:")
    print(f"   1. Click '📧 Scan Gmail' to import job alerts")
    print(f"   2. Click '🤖 Analyze All' for AI analysis")
    print(f"   3. Click '📬 Scan Follow-Ups' to track responses")
    print(f"   4. Use the Chrome extension for instant analysis")
    print(f"\n🚀 Dashboard running at: http://localhost:5000")
    print("="*60 + "\n")

    # Start Flask app
    app.run(debug=True, port=5000)