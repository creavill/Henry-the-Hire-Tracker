import React, { useState, useEffect, useCallback } from 'react';
import { Search, RefreshCw, FileText, ExternalLink, ChevronDown, Filter, Briefcase, CheckCircle, XCircle, Clock, Star, Plus, Mail, Phone, User } from 'lucide-react';

const API_BASE = '/api';

const STATUS_CONFIG = {
  new: { label: 'New', color: 'bg-gray-100 text-gray-700', icon: Clock },
  interested: { label: 'Interested', color: 'bg-blue-100 text-blue-700', icon: Star },
  applied: { label: 'Applied', color: 'bg-green-100 text-green-700', icon: CheckCircle },
  interviewing: { label: 'Interviewing', color: 'bg-purple-100 text-purple-700', icon: Briefcase },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: XCircle },
  offer: { label: 'Offer', color: 'bg-yellow-100 text-yellow-700', icon: Star },
  passed: { label: 'Passed', color: 'bg-gray-100 text-gray-500', icon: XCircle },
};

function ScoreBadge({ score }) {
  let color = 'bg-gray-200 text-gray-700';
  if (score >= 80) color = 'bg-green-500 text-white';
  else if (score >= 60) color = 'bg-blue-500 text-white';
  else if (score >= 40) color = 'bg-yellow-500 text-white';
  else if (score > 0) color = 'bg-red-400 text-white';
  
  return (
    <span className={`px-2 py-1 rounded-full text-sm font-bold ${color}`}>
      {score || '—'}
    </span>
  );
}

function StatusBadge({ status, onChange, statusConfig }) {
  const config_to_use = statusConfig || STATUS_CONFIG;
  const config = config_to_use[status] || config_to_use.new || config_to_use.applied;
  const Icon = config.icon;
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-1 px-2 py-1 rounded-full text-sm ${config.color} hover:opacity-80`}
      >
        <Icon size={14} />
        {config.label}
        <ChevronDown size={14} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 bg-white border rounded-lg shadow-lg z-10 min-w-32">
          {Object.entries(config_to_use).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => { onChange(key); setIsOpen(false); }}
              className={`w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center gap-2 ${key === status ? 'bg-gray-50' : ''}`}
            >
              <cfg.icon size={14} />
              {cfg.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function JobCard({ job, onStatusChange, onGenerateCoverLetter, expanded, onToggle }) {
  const analysis = job.analysis || {};
  
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div 
        className="p-4 cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <ScoreBadge score={job.score} />
              <h3 className="font-semibold text-gray-900 truncate">{job.title}</h3>
            </div>
            <p className="text-gray-600 text-sm">{job.company || 'Unknown Company'}</p>
            <p className="text-gray-500 text-xs">{job.location || 'Location not specified'}</p>
          </div>
          
          <div className="flex items-center gap-2">
            <StatusBadge status={job.status} onChange={(s) => onStatusChange(job.job_id, s)} />
            <span className="text-xs text-gray-400 capitalize">{job.source}</span>
          </div>
        </div>
        
        {analysis.recommendation && (
          <p className="mt-2 text-sm text-gray-600 line-clamp-2">{analysis.recommendation}</p>
        )}
      </div>
      
      {expanded && (
        <div className="border-t px-4 py-3 bg-gray-50 space-y-3">
          {analysis.strengths?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-green-700 uppercase mb-1">Strengths</h4>
              <ul className="text-sm text-gray-700 space-y-1">
                {analysis.strengths.map((s, i) => <li key={i}>• {s}</li>)}
              </ul>
            </div>
          )}
          
          {analysis.gaps?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-red-700 uppercase mb-1">Gaps</h4>
              <ul className="text-sm text-gray-700 space-y-1">
                {analysis.gaps.map((g, i) => <li key={i}>• {g}</li>)}
              </ul>
            </div>
          )}
          
          {job.cover_letter && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 uppercase mb-1">Cover Letter</h4>
              <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-3 rounded border max-h-48 overflow-y-auto">
                {job.cover_letter}
              </pre>
            </div>
          )}
          
          <div className="flex items-center gap-2 pt-2">
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >
              <ExternalLink size={14} /> View Job
            </a>
            
            {!job.cover_letter && (
              <button
                onClick={(e) => { e.stopPropagation(); onGenerateCoverLetter(job.job_id); }}
                className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700"
              >
                <FileText size={14} /> Generate Cover Letter
              </button>
            )}
          </div>
          
          <div className="text-xs text-gray-400">
            Added: {new Date(job.created_at).toLocaleDateString()} • 
            Resume: {analysis.resume_to_use || 'fullstack'}
          </div>
        </div>
      )}
    </div>
  );
}

function StatsBar({ stats }) {
  return (
    <div className="grid grid-cols-5 gap-4 mb-6">
      {[
        { label: 'Total', value: stats.total, color: 'bg-gray-100' },
        { label: 'New', value: stats.new, color: 'bg-gray-100' },
        { label: 'Interested', value: stats.interested, color: 'bg-blue-100' },
        { label: 'Applied', value: stats.applied, color: 'bg-green-100' },
        { label: 'Avg Score', value: Math.round(stats.avg_score), color: 'bg-purple-100' },
      ].map(({ label, value, color }) => (
        <div key={label} className={`${color} rounded-lg p-3 text-center`}>
          <div className="text-2xl font-bold">{value}</div>
          <div className="text-xs text-gray-600">{label}</div>
        </div>
      ))}
    </div>
  );
}

function ExternalApplicationCard({ app, onStatusChange, expanded, onToggle, onDelete }) {
  const sourceLabels = {
    cold_email: 'Cold Email',
    referral: 'Referral',
    recruiter: 'Recruiter',
    company_website: 'Company Website',
    linkedin_message: 'LinkedIn',
    other: 'Other'
  };

  const EXTERNAL_STATUS_CONFIG = {
    applied: { label: 'Applied', color: 'bg-green-100 text-green-700', icon: CheckCircle },
    interviewing: { label: 'Interviewing', color: 'bg-purple-100 text-purple-700', icon: Briefcase },
    rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: XCircle },
    offer: { label: 'Offer', color: 'bg-yellow-100 text-yellow-700', icon: Star },
    withdrawn: { label: 'Withdrawn', color: 'bg-gray-100 text-gray-500', icon: XCircle },
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-700">
                EXTERNAL
              </span>
              <h3 className="font-semibold text-gray-900 truncate">{app.title}</h3>
            </div>
            <p className="text-gray-600 text-sm">{app.company}</p>
            <p className="text-gray-500 text-xs">{app.location || 'Location not specified'}</p>
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge
              status={app.status}
              onChange={(s) => onStatusChange(app.app_id, s)}
              statusConfig={EXTERNAL_STATUS_CONFIG}
            />
            <span className="text-xs text-gray-400">{sourceLabels[app.source] || app.source}</span>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t px-4 py-3 bg-gray-50 space-y-3">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500">Applied:</span>
              <span className="ml-2 font-medium">{new Date(app.applied_date).toLocaleDateString()}</span>
            </div>
            {app.application_method && (
              <div>
                <span className="text-gray-500">Method:</span>
                <span className="ml-2 font-medium capitalize">{app.application_method.replace('_', ' ')}</span>
              </div>
            )}
            {app.contact_name && (
              <div>
                <User size={14} className="inline mr-1" />
                <span className="font-medium">{app.contact_name}</span>
              </div>
            )}
            {app.contact_email && (
              <div>
                <Mail size={14} className="inline mr-1" />
                <span className="font-medium">{app.contact_email}</span>
              </div>
            )}
          </div>

          {app.notes && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 uppercase mb-1">Notes</h4>
              <p className="text-sm text-gray-700 bg-white p-3 rounded border">{app.notes}</p>
            </div>
          )}

          <div className="flex items-center gap-2 pt-2">
            {app.url && (
              <a
                href={app.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                <ExternalLink size={14} /> View Job
              </a>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(app.app_id); }}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700"
            >
              Delete
            </button>
          </div>

          <div className="text-xs text-gray-400">
            Created: {new Date(app.created_at).toLocaleDateString()}
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({ total: 0, new: 0, interested: 0, applied: 0, avg_score: 0 });
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [expandedJob, setExpandedJob] = useState(null);
  const [filter, setFilter] = useState({ status: '', minScore: 0, search: '' });
  const [activeView, setActiveView] = useState('discovered'); // 'discovered' or 'external'
  const [externalApps, setExternalApps] = useState([]);
  const [showAddExternal, setShowAddExternal] = useState(false);
  
  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.status) params.set('status', filter.status);
      if (filter.minScore) params.set('min_score', filter.minScore);
      params.set('sort', 'score');
      
      const res = await fetch(`${API_BASE}/jobs?${params}`);
      const data = await res.json();
      
      setJobs(data.jobs || []);
      setStats(data.stats || {});
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
    setLoading(false);
  }, [filter.status, filter.minScore]);
  
  const fetchExternalApps = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/external-applications`);
      const data = await res.json();
      setExternalApps(data.applications || []);
    } catch (err) {
      console.error('Failed to fetch external applications:', err);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    fetchExternalApps();
  }, [fetchJobs, fetchExternalApps]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API_BASE}/scan`, { method: 'POST' });
      // Poll for updates after a delay
      setTimeout(fetchJobs, 5000);
      setTimeout(fetchJobs, 15000);
      setTimeout(fetchJobs, 30000);
    } catch (err) {
      console.error('Scan failed:', err);
    }
    setScanning(false);
  };
  
  const handleStatusChange = async (jobId, newStatus) => {
    try {
      await fetch(`${API_BASE}/jobs/${jobId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchJobs();
    } catch (err) {
      console.error('Status update failed:', err);
    }
  };
  
  const handleGenerateCoverLetter = async (jobId) => {
    try {
      await fetch(`${API_BASE}/jobs/${jobId}/cover-letter`, { method: 'POST' });
      // Poll for completion
      setTimeout(fetchJobs, 5000);
      setTimeout(fetchJobs, 15000);
    } catch (err) {
      console.error('Cover letter generation failed:', err);
    }
  };

  const handleExternalStatusChange = async (appId, newStatus) => {
    try {
      await fetch(`${API_BASE}/external-applications/${appId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchExternalApps();
    } catch (err) {
      console.error('External app status update failed:', err);
    }
  };

  const handleDeleteExternal = async (appId) => {
    if (!confirm('Delete this external application?')) return;
    try {
      await fetch(`${API_BASE}/external-applications/${appId}`, { method: 'DELETE' });
      fetchExternalApps();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const filteredJobs = jobs.filter(job => {
    if (filter.search) {
      const search = filter.search.toLowerCase();
      const matches = 
        job.title?.toLowerCase().includes(search) ||
        job.company?.toLowerCase().includes(search);
      if (!matches) return false;
    }
    return true;
  });
  
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Job Tracker</h1>
              <p className="text-sm text-gray-500">AI-powered job matching</p>
            </div>
            
            <button
              onClick={handleScan}
              disabled={scanning}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <RefreshCw size={18} className={scanning ? 'animate-spin' : ''} />
              {scanning ? 'Scanning...' : 'Scan Emails'}
            </button>
          </div>
        </div>
      </header>
      
      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* View Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveView('discovered')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              activeView === 'discovered'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Discovered Jobs ({jobs.length})
          </button>
          <button
            onClick={() => setActiveView('external')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              activeView === 'external'
                ? 'bg-orange-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            External Applications ({externalApps.length})
          </button>
        </div>

        {activeView === 'discovered' ? (
          <>
            <StatsBar stats={stats} />

            {/* Filters */}
            <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search jobs..."
              value={filter.search}
              onChange={(e) => setFilter({ ...filter, search: e.target.value })}
              className="w-full pl-10 pr-4 py-2 border rounded-lg"
            />
          </div>
          
          <select
            value={filter.status}
            onChange={(e) => setFilter({ ...filter, status: e.target.value })}
            className="px-3 py-2 border rounded-lg"
          >
            <option value="">All Statuses</option>
            {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.label}</option>
            ))}
          </select>
          
          <select
            value={filter.minScore}
            onChange={(e) => setFilter({ ...filter, minScore: Number(e.target.value) })}
            className="px-3 py-2 border rounded-lg"
          >
            <option value="0">All Scores</option>
            <option value="80">80+ (Highly Qualified)</option>
            <option value="60">60+ (Good Match)</option>
            <option value="40">40+ (Partial Match)</option>
          </select>
        </div>
        
            {/* Jobs List */}
            {loading ? (
              <div className="text-center py-12 text-gray-500">Loading jobs...</div>
            ) : filteredJobs.length === 0 ? (
              <div className="text-center py-12">
                <Briefcase size={48} className="mx-auto mb-4 text-gray-300" />
                <p className="text-gray-500">No jobs found. Click "Scan Emails" to fetch job alerts.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredJobs.map(job => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    expanded={expandedJob === job.job_id}
                    onToggle={() => setExpandedJob(expandedJob === job.job_id ? null : job.job_id)}
                    onStatusChange={handleStatusChange}
                    onGenerateCoverLetter={handleGenerateCoverLetter}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            {/* External Applications View */}
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-gray-900">External Applications</h2>
              <button
                onClick={() => setShowAddExternal(!showAddExternal)}
                className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
              >
                <Plus size={18} />
                {showAddExternal ? 'Cancel' : 'Add External Application'}
              </button>
            </div>

            {showAddExternal && (
              <div className="bg-white rounded-lg shadow-sm border p-4 mb-6">
                <h3 className="font-semibold mb-4">Add External Application</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Use the browser extension for quick capture, or visit the extension for more options.
                </p>
                <button
                  onClick={() => setShowAddExternal(false)}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                >
                  Close
                </button>
              </div>
            )}

            {externalApps.length === 0 ? (
              <div className="text-center py-12">
                <Briefcase size={48} className="mx-auto mb-4 text-gray-300" />
                <p className="text-gray-500 mb-4">No external applications tracked yet.</p>
                <p className="text-sm text-gray-400">Use the browser extension to add applications you made outside the system.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {externalApps.map(app => (
                  <ExternalApplicationCard
                    key={app.app_id}
                    app={app}
                    expanded={expandedJob === app.app_id}
                    onToggle={() => setExpandedJob(expandedJob === app.app_id ? null : app.app_id)}
                    onStatusChange={handleExternalStatusChange}
                    onDelete={handleDeleteExternal}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
