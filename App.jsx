import React, { useState, useEffect, useCallback } from 'react';
import { Search, RefreshCw, FileText, ExternalLink, ChevronDown, Filter, Briefcase, CheckCircle, XCircle, Clock, Star, Plus, Mail, Phone, User, Upload, Edit2, Trash2, Sparkles, AlertCircle } from 'lucide-react';

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

function JobCard({ job, onStatusChange, onGenerateCoverLetter, onRecommendResume, expanded, onToggle }) {
  const analysis = job.analysis || {};
  const [loadingRecommendation, setLoadingRecommendation] = useState(false);

  // Parse resume recommendation if available
  let resumeRec = null;
  if (job.resume_recommendation) {
    try {
      resumeRec = typeof job.resume_recommendation === 'string'
        ? JSON.parse(job.resume_recommendation)
        : job.resume_recommendation;
    } catch (e) {
      console.error('Failed to parse resume recommendation:', e);
    }
  }

  const handleGetRecommendation = async () => {
    setLoadingRecommendation(true);
    await onRecommendResume(job.job_id);
    setLoadingRecommendation(false);
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
              <ScoreBadge score={job.score} />
              <h3 className="font-semibold text-gray-900 truncate">{job.title}</h3>
              {resumeRec && (
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-700">
                  📄 {Math.round(resumeRec.confidence * 100)}%
                </span>
              )}
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
          {/* Resume Recommendation Section */}
          {resumeRec ? (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
              <h4 className="text-sm font-semibold text-purple-900 mb-2 flex items-center gap-2">
                <FileText size={16} />
                Recommended Resume: {resumeRec.resume_name}
                <span className="ml-auto text-xs font-normal bg-purple-200 px-2 py-0.5 rounded-full">
                  {Math.round(resumeRec.confidence * 100)}% Match
                </span>
              </h4>
              <p className="text-sm text-purple-800 mb-2">{resumeRec.reasoning}</p>
              {resumeRec.resume_strengths?.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-purple-900">Your Strengths:</p>
                  <ul className="text-xs text-purple-700 space-y-0.5 ml-3">
                    {resumeRec.resume_strengths.map((s, i) => <li key={i}>✓ {s}</li>)}
                  </ul>
                </div>
              )}
              {resumeRec.resume_gaps?.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-purple-900">Gaps to Address:</p>
                  <ul className="text-xs text-purple-700 space-y-0.5 ml-3">
                    {resumeRec.resume_gaps.map((g, i) => <li key={i}>• {g}</li>)}
                  </ul>
                </div>
              )}
              {resumeRec.alternative_resumes?.length > 0 && (
                <details className="mt-2">
                  <summary className="text-xs font-semibold text-purple-900 cursor-pointer">
                    View {resumeRec.alternative_resumes.length} Alternative Resume(s)
                  </summary>
                  <div className="mt-1 space-y-1">
                    {resumeRec.alternative_resumes.map((alt, i) => (
                      <div key={i} className="text-xs text-purple-700 ml-3">
                        • {alt.resume_name} ({Math.round(alt.confidence * 100)}%) - {alt.reason}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); handleGetRecommendation(); }}
              disabled={loadingRecommendation}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 disabled:opacity-50"
            >
              <Sparkles size={16} />
              {loadingRecommendation ? 'Getting Recommendation...' : 'Get Resume Recommendation'}
            </button>
          )}

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

function ResumeCard({ resume, onEdit, onDelete, expanded, onToggle }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 mb-1">{resume.name}</h3>
            {resume.focus_areas && (
              <p className="text-sm text-gray-600 mb-1">
                <span className="font-medium">Focus:</span> {resume.focus_areas}
              </p>
            )}
            {resume.target_roles && (
              <p className="text-sm text-gray-600">
                <span className="font-medium">Target Roles:</span> {resume.target_roles}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className="px-2 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-700">
              Used {resume.usage_count || 0}x
            </span>
            <div className="flex gap-1">
              <button
                onClick={(e) => { e.stopPropagation(); onEdit(resume); }}
                className="p-1.5 text-blue-600 hover:bg-blue-50 rounded"
              >
                <Edit2 size={16} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(resume.resume_id); }}
                className="p-1.5 text-red-600 hover:bg-red-50 rounded"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t px-4 py-3 bg-gray-50 space-y-2">
          <div className="text-xs text-gray-500">
            Created: {new Date(resume.created_at).toLocaleDateString()}
          </div>
          <div className="max-h-40 overflow-y-auto">
            <p className="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-white p-2 rounded border">
              {resume.content?.substring(0, 500)}...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function ResumeUploadModal({ onClose, onSave }) {
  const [formData, setFormData] = useState({
    name: '',
    focus_areas: '',
    target_roles: '',
    content: ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!formData.name || !formData.content) {
      setError('Name and content are required');
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/resumes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        onSave();
        onClose();
      } else {
        setError(data.error || 'Failed to save resume');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-4">Add New Resume</h2>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle size={20} className="text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Resume Name *
              </label>
              <input
                type="text"
                placeholder="e.g., Backend Python AWS"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Focus Areas
              </label>
              <input
                type="text"
                placeholder="e.g., Python, AWS, FastAPI, PostgreSQL"
                value={formData.focus_areas}
                onChange={(e) => setFormData({ ...formData, focus_areas: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Roles
              </label>
              <input
                type="text"
                placeholder="e.g., Backend Engineer, API Developer"
                value={formData.target_roles}
                onChange={(e) => setFormData({ ...formData, target_roles: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Resume Content *
              </label>
              <textarea
                placeholder="Paste your resume text here..."
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg font-mono text-sm"
                rows={12}
                required
              />
            </div>

            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Resume'}
              </button>
              <button
                type="button"
                onClick={onClose}
                disabled={saving}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
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
  const [activeView, setActiveView] = useState('discovered'); // 'discovered', 'external', 'resumes', or 'companies'
  const [externalApps, setExternalApps] = useState([]);
  const [showAddExternal, setShowAddExternal] = useState(false);
  const [resumes, setResumes] = useState([]);
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [batchRecommending, setBatchRecommending] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
  const [trackedCompanies, setTrackedCompanies] = useState([]);
  const [showAddCompany, setShowAddCompany] = useState(false);
  const [editingCompany, setEditingCompany] = useState(null);
  
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
    console.log('[Frontend] Fetching external applications...');
    try {
      const res = await fetch(`${API_BASE}/external-applications`);
      const data = await res.json();
      console.log(`[Frontend] Received ${data.applications?.length || 0} external applications`);
      setExternalApps(data.applications || []);
    } catch (err) {
      console.error('[Frontend] Failed to fetch external applications:', err);
    }
  }, []);

  const fetchResumes = useCallback(async () => {
    console.log('[Frontend] Fetching resumes...');
    try {
      const res = await fetch(`${API_BASE}/resumes`);
      const data = await res.json();
      console.log(`[Frontend] Received ${data.resumes?.length || 0} resumes`);
      setResumes(data.resumes || []);
    } catch (err) {
      console.error('[Frontend] Failed to fetch resumes:', err);
    }
  }, []);

  const fetchTrackedCompanies = useCallback(async () => {
    console.log('[Frontend] Fetching tracked companies...');
    try {
      const res = await fetch(`${API_BASE}/tracked-companies`);
      const data = await res.json();
      console.log(`[Frontend] Received ${data.companies?.length || 0} tracked companies`);
      setTrackedCompanies(data.companies || []);
    } catch (err) {
      console.error('[Frontend] Failed to fetch tracked companies:', err);
    }
  }, []);

  useEffect(() => {
    console.log('[Frontend] Component mounted, fetching initial data...');
    fetchJobs();
    fetchExternalApps();
    fetchResumes();
    fetchTrackedCompanies();
  }, [fetchJobs, fetchExternalApps, fetchResumes, fetchTrackedCompanies]);

  // Separate effect for polling to avoid recreating interval
  useEffect(() => {
    // Poll for external applications every 5 seconds to catch updates from extension
    console.log('[Frontend] Setting up polling for external applications (5s interval)');
    const pollInterval = setInterval(() => {
      console.log('[Frontend] Polling for external applications updates...');
      fetchExternalApps();
    }, 5000);

    return () => {
      console.log('[Frontend] Cleaning up polling interval');
      clearInterval(pollInterval);
    };
  }, [fetchExternalApps]);

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
    console.log(`[Frontend] Updating external application ${appId} status to: ${newStatus}`);
    try {
      await fetch(`${API_BASE}/external-applications/${appId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      console.log('[Frontend] Status update successful, refreshing list...');
      fetchExternalApps();
    } catch (err) {
      console.error('[Frontend] External app status update failed:', err);
    }
  };

  const handleDeleteExternal = async (appId) => {
    console.log(`[Frontend] Deleting external application: ${appId}`);
    try {
      await fetch(`${API_BASE}/external-applications/${appId}`, { method: 'DELETE' });
      console.log('[Frontend] Delete successful, refreshing list...');
      fetchExternalApps();
    } catch (err) {
      console.error('[Frontend] Delete failed:', err);
    }
  };

  const handleAddTrackedCompany = async (companyData) => {
    console.log('[Frontend] Adding tracked company:', companyData);
    try {
      await fetch(`${API_BASE}/tracked-companies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(companyData),
      });
      console.log('[Frontend] Company added successfully, refreshing list...');
      fetchTrackedCompanies();
      setShowAddCompany(false);
    } catch (err) {
      console.error('[Frontend] Failed to add company:', err);
    }
  };

  const handleUpdateTrackedCompany = async (companyId, companyData) => {
    console.log(`[Frontend] Updating tracked company ${companyId}:`, companyData);
    try {
      await fetch(`${API_BASE}/tracked-companies/${companyId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(companyData),
      });
      console.log('[Frontend] Company updated successfully, refreshing list...');
      fetchTrackedCompanies();
      setEditingCompany(null);
    } catch (err) {
      console.error('[Frontend] Failed to update company:', err);
    }
  };

  const handleDeleteTrackedCompany = async (companyId) => {
    console.log(`[Frontend] Deleting tracked company: ${companyId}`);
    try {
      await fetch(`${API_BASE}/tracked-companies/${companyId}`, { method: 'DELETE' });
      console.log('[Frontend] Company deleted successfully, refreshing list...');
      fetchTrackedCompanies();
    } catch (err) {
      console.error('[Frontend] Failed to delete company:', err);
    }
  };

  const handleRecommendResume = async (jobId) => {
    console.log(`[Frontend] Getting resume recommendation for job: ${jobId}`);
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/recommend-resume`, {
        method: 'POST'
      });
      const data = await res.json();
      console.log('[Frontend] Recommendation received:', data);
      fetchJobs(); // Refresh to show recommendation
    } catch (err) {
      console.error('[Frontend] Resume recommendation failed:', err);
    }
  };

  const handleBatchRecommend = async () => {
    const jobIds = jobs.filter(j => !j.resume_recommendation).map(j => j.job_id);

    if (jobIds.length === 0) {
      alert('All jobs already have recommendations!');
      return;
    }

    if (!confirm(`Generate resume recommendations for ${jobIds.length} jobs? This may take a few minutes.`)) {
      return;
    }

    setBatchRecommending(true);
    setBatchProgress({ current: 0, total: jobIds.length });

    try {
      const res = await fetch(`${API_BASE}/jobs/recommend-resumes-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: jobIds })
      });
      const data = await res.json();

      console.log('[Frontend] Batch recommendation complete:', data);
      alert(`Batch complete! ${data.summary.successful} successful, ${data.summary.failed} failed`);
      fetchJobs(); // Refresh to show all recommendations
    } catch (err) {
      console.error('[Frontend] Batch recommendation failed:', err);
      alert('Batch recommendation failed: ' + err.message);
    }

    setBatchRecommending(false);
    setBatchProgress({ current: 0, total: 0 });
  };

  const handleDeleteResume = async (resumeId) => {
    if (!confirm('Are you sure you want to delete this resume?')) {
      return;
    }

    try {
      await fetch(`${API_BASE}/resumes/${resumeId}`, { method: 'DELETE' });
      fetchResumes();
    } catch (err) {
      console.error('[Frontend] Resume deletion failed:', err);
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
          <button
            onClick={() => setActiveView('resumes')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              activeView === 'resumes'
                ? 'bg-purple-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            📄 Resume Library ({resumes.length})
          </button>
          <button
            onClick={() => setActiveView('companies')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              activeView === 'companies'
                ? 'bg-green-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            🏢 Tracked Companies ({trackedCompanies.length})
          </button>
        </div>

        {activeView === 'discovered' ? (
          <>
            <StatsBar stats={stats} />

            {/* Action Bar */}
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-gray-600">
                {jobs.filter(j => j.resume_recommendation).length} of {jobs.length} jobs have resume recommendations
              </div>
              <button
                onClick={handleBatchRecommend}
                disabled={batchRecommending || jobs.every(j => j.resume_recommendation)}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                <Sparkles size={18} className={batchRecommending ? 'animate-spin' : ''} />
                {batchRecommending ? `Recommending... (${batchProgress.current}/${batchProgress.total})` : 'Batch Recommend Resumes'}
              </button>
            </div>

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
                    onRecommendResume={handleRecommendResume}
                  />
                ))}
              </div>
            )}
          </>
        ) : activeView === 'external' ? (
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
        ) : activeView === 'resumes' ? (
          <>
            {/* Resumes View */}
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Resume Library</h2>
              <button
                onClick={() => setShowResumeModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
              >
                <Plus size={18} />
                Add Resume
              </button>
            </div>

            {resumes.length === 0 ? (
              <div className="text-center py-12">
                <FileText size={48} className="mx-auto mb-4 text-gray-300" />
                <p className="text-gray-500 mb-4">No resumes in your library yet.</p>
                <p className="text-sm text-gray-400 mb-6">Add your first resume to get AI-powered job-resume matching!</p>
                <button
                  onClick={() => setShowResumeModal(true)}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                >
                  <Upload size={20} />
                  Upload Your First Resume
                </button>
              </div>
            ) : (
              <>
                <div className="mb-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                  <h3 className="font-semibold text-purple-900 mb-2">📊 Library Stats</h3>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <div className="text-2xl font-bold text-purple-600">{resumes.length}</div>
                      <div className="text-purple-700">Total Resumes</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-purple-600">
                        {resumes.reduce((sum, r) => sum + (r.usage_count || 0), 0)}
                      </div>
                      <div className="text-purple-700">Total Recommendations</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-purple-600">
                        {resumes.filter(r => r.usage_count > 0).length}
                      </div>
                      <div className="text-purple-700">Used Resumes</div>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  {resumes.map(resume => (
                    <ResumeCard
                      key={resume.resume_id}
                      resume={resume}
                      expanded={expandedJob === resume.resume_id}
                      onToggle={() => setExpandedJob(expandedJob === resume.resume_id ? null : resume.resume_id)}
                      onEdit={() => alert('Edit functionality coming soon!')}
                      onDelete={handleDeleteResume}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        ) : (
          <>
            {/* Tracked Companies View */}
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Tracked Companies</h2>
              <button
                onClick={() => setShowAddCompany(!showAddCompany)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                <Plus size={18} />
                {showAddCompany ? 'Cancel' : 'Add Company'}
              </button>
            </div>

            {showAddCompany && (
              <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
                <h3 className="font-semibold mb-4">Add Tracked Company</h3>
                <form onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.target);
                  handleAddTrackedCompany({
                    company_name: formData.get('company_name'),
                    career_page_url: formData.get('career_page_url'),
                    job_alert_email: formData.get('job_alert_email'),
                    notes: formData.get('notes'),
                  });
                  e.target.reset();
                }}>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Company Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        name="company_name"
                        required
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="e.g., Google, Microsoft, Startup Inc."
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Career Page URL
                      </label>
                      <input
                        type="url"
                        name="career_page_url"
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="https://company.com/careers"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Job Alert Email
                      </label>
                      <input
                        type="email"
                        name="job_alert_email"
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="jobs@company.com"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Notes
                      </label>
                      <textarea
                        name="notes"
                        rows="3"
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="Add any notes about this company..."
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                      >
                        Add Company
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowAddCompany(false)}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </form>
              </div>
            )}

            {trackedCompanies.length === 0 ? (
              <div className="text-center py-12">
                <Briefcase size={48} className="mx-auto mb-4 text-gray-300" />
                <p className="text-gray-500 mb-4">No tracked companies yet.</p>
                <p className="text-sm text-gray-400 mb-6">
                  Track companies you're interested in with their career pages and job alert emails.
                </p>
                <button
                  onClick={() => setShowAddCompany(true)}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  <Plus size={20} />
                  Add Your First Company
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {trackedCompanies.map(company => (
                  <div key={company.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                    {editingCompany === company.id ? (
                      <form onSubmit={(e) => {
                        e.preventDefault();
                        const formData = new FormData(e.target);
                        handleUpdateTrackedCompany(company.id, {
                          company_name: formData.get('company_name'),
                          career_page_url: formData.get('career_page_url'),
                          job_alert_email: formData.get('job_alert_email'),
                          notes: formData.get('notes'),
                        });
                      }}>
                        <div className="space-y-3">
                          <input
                            type="text"
                            name="company_name"
                            defaultValue={company.company_name}
                            required
                            className="w-full px-3 py-2 border rounded-lg font-semibold"
                            placeholder="Company Name"
                          />
                          <input
                            type="url"
                            name="career_page_url"
                            defaultValue={company.career_page_url || ''}
                            className="w-full px-3 py-2 border rounded-lg text-sm"
                            placeholder="Career Page URL"
                          />
                          <input
                            type="email"
                            name="job_alert_email"
                            defaultValue={company.job_alert_email || ''}
                            className="w-full px-3 py-2 border rounded-lg text-sm"
                            placeholder="Job Alert Email"
                          />
                          <textarea
                            name="notes"
                            defaultValue={company.notes || ''}
                            rows="2"
                            className="w-full px-3 py-2 border rounded-lg text-sm"
                            placeholder="Notes"
                          />
                          <div className="flex gap-2">
                            <button
                              type="submit"
                              className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700"
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingCompany(null)}
                              className="px-3 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </form>
                    ) : (
                      <>
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1">
                            <h3 className="font-semibold text-gray-900 text-lg mb-2">{company.company_name}</h3>
                            <div className="space-y-1 text-sm text-gray-600">
                              {company.career_page_url && (
                                <div className="flex items-center gap-2">
                                  <ExternalLink size={14} />
                                  <a
                                    href={company.career_page_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-600 hover:underline"
                                  >
                                    {company.career_page_url}
                                  </a>
                                </div>
                              )}
                              {company.job_alert_email && (
                                <div className="flex items-center gap-2">
                                  <Mail size={14} />
                                  <a
                                    href={`mailto:${company.job_alert_email}`}
                                    className="text-blue-600 hover:underline"
                                  >
                                    {company.job_alert_email}
                                  </a>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => setEditingCompany(company.id)}
                              className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                              title="Edit"
                            >
                              <Edit2 size={16} />
                            </button>
                            <button
                              onClick={() => {
                                if (confirm(`Delete ${company.company_name}?`)) {
                                  handleDeleteTrackedCompany(company.id);
                                }
                              }}
                              className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                              title="Delete"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                        {company.notes && (
                          <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                            <p className="text-sm text-gray-700">{company.notes}</p>
                          </div>
                        )}
                        <div className="mt-3 pt-3 border-t text-xs text-gray-500">
                          Added: {new Date(company.created_at).toLocaleDateString()}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {/* Resume Upload Modal */}
      {showResumeModal && (
        <ResumeUploadModal
          onClose={() => setShowResumeModal(false)}
          onSave={fetchResumes}
        />
      )}
    </div>
  );
}
