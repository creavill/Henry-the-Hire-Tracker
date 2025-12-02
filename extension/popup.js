const API_URL = 'http://localhost:5000/api/capture';
const ANALYZE_URL = 'http://localhost:5000/api/analyze-instant';
const COVER_LETTER_URL = 'http://localhost:5000/api/generate-cover-letter';
const ANSWER_URL = 'http://localhost:5000/api/generate-answer';

let currentAnalysis = null;
let currentJobData = null;

// Auto-fill URL and title on load
chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
  if (tabs[0]) {
    const url = tabs[0].url;
    currentJobData = { url };
    
    let title = tabs[0].title || '';
    title = title
      .replace(/\| LinkedIn$/, '')
      .replace(/- Indeed\.com$/, '')
      .replace(/\| Glassdoor$/, '')
      .trim();
    
    if (title && title.length > 5) {
      document.getElementById('title').value = title;
    }
  }
});

// Tab switching
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTab = tab.getAttribute('data-tab');
      
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      
      tab.classList.add('active');
      document.getElementById(`${targetTab}-section`).classList.add('active');
    });
  });
  
  // Analyze button
  document.getElementById('analyzeBtn').addEventListener('click', analyzeJob);
  
  // Apply tab buttons
  document.getElementById('copyCoverBtn').addEventListener('click', () => {
    copyText('coverLetter');
  });
  document.getElementById('generateCoverBtn').addEventListener('click', generateCoverLetter);
  document.getElementById('markAppliedBtn').addEventListener('click', markApplied);
  
  // Questions tab
  document.querySelectorAll('.question-list li').forEach(item => {
    item.addEventListener('click', () => {
      const questionType = item.getAttribute('data-question');
      generateAnswer(questionType);
    });
  });
  document.getElementById('customQuestionBtn').addEventListener('click', () => {
    generateAnswer('custom');
  });
});

// ANALYZE TAB
async function analyzeJob() {
  const title = document.getElementById('title').value.trim();
  const company = document.getElementById('company').value.trim();
  const description = document.getElementById('description').value.trim();
  
  if (!title || !description) {
    showStatus('Title and description required', 'error', 'analyze-result');
    return;
  }
  
  if (description.length < 50) {
    showStatus('Description too short - paste the full posting', 'error', 'analyze-result');
    return;
  }
  
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true;
  btn.textContent = '🤖 Analyzing...';
  
  currentJobData = {
    title,
    company: company || 'Unknown',
    description,
    url: currentJobData?.url || ''
  };
  
  try {
    const response = await fetch(ANALYZE_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(currentJobData)
    });
    
    if (!response.ok) throw new Error('Analysis failed');
    
    const result = await response.json();
    currentAnalysis = result.analysis;
    
    displayAnalysis(result.analysis);
    
  } catch (err) {
    showStatus(`Error: ${err.message}`, 'error', 'analyze-result');
  }
  
  btn.disabled = false;
  btn.textContent = '🤖 Analyze Fit';
}

function displayAnalysis(analysis) {
  const { qualification_score, should_apply, strengths, gaps, recommendation, resume_to_use } = analysis;
  
  let scoreColor = qualification_score >= 80 ? '#059669' : 
                   qualification_score >= 60 ? '#2563eb' : 
                   qualification_score >= 40 ? '#d97706' : '#dc2626';
  
  const html = `
    <div class="result-card" style="margin-top: 16px;">
      <div style="text-align: center; margin-bottom: 12px;">
        <span class="score-badge" style="background: ${scoreColor}; color: white;">
          ${qualification_score}/100
        </span>
        <span style="margin-left: 8px; font-weight: 600;">
          ${should_apply ? '✅ APPLY' : '⚠️ PASS'}
        </span>
      </div>
      
      <div style="padding: 10px; background: #f9fafb; border-radius: 4px; margin-bottom: 12px;">
        <strong>Recommendation:</strong>
        <p style="margin-top: 4px; font-size: 13px; line-height: 1.4;">${recommendation}</p>
      </div>
      
      ${strengths.length > 0 ? `
      <details open style="margin-bottom: 8px;">
        <summary style="cursor: pointer; font-weight: 600; color: #059669;">💪 Strengths</summary>
        <ul style="margin: 4px 0 0 20px; font-size: 12px; line-height: 1.5;">
          ${strengths.map(s => `<li>${s}</li>`).join('')}
        </ul>
      </details>
      ` : ''}
      
      ${gaps.length > 0 ? `
      <details style="margin-bottom: 8px;">
        <summary style="cursor: pointer; font-weight: 600; color: #dc2626;">⚠️ Gaps</summary>
        <ul style="margin: 4px 0 0 20px; font-size: 12px; line-height: 1.5;">
          ${gaps.map(g => `<li>${g}</li>`).join('')}
        </ul>
      </details>
      ` : ''}
      
      <div style="font-size: 11px; color: #6b7280; margin-top: 8px;">
        📄 Recommended resume: <strong>${resume_to_use}</strong>
      </div>
    </div>
  `;
  
  document.getElementById('analyze-result').innerHTML = html;
  document.getElementById('resumeRec').innerHTML = `Use <strong>${resume_to_use}</strong> resume for this application`;
}

// APPLY TAB
async function generateCoverLetter() {
  if (!currentJobData || !currentAnalysis) {
    alert('Analyze the job first');
    return;
  }
  
  const btn = document.getElementById('generateCoverBtn');
  btn.disabled = true;
  btn.textContent = '✨ Generating...';
  
  try {
    const response = await fetch(COVER_LETTER_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        job: currentJobData,
        analysis: currentAnalysis
      })
    });
    
    if (!response.ok) throw new Error('Generation failed');
    
    const result = await response.json();
    document.getElementById('coverLetter').value = result.cover_letter;
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
  
  btn.disabled = false;
  btn.textContent = '✨ Generate';
}

async function markApplied() {
  if (!currentJobData) {
    alert('Analyze job first');
    return;
  }
  
  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        ...currentJobData,
        status: 'applied',
        analysis: currentAnalysis,
        applied_date: new Date().toISOString()
      })
    });
    
    if (!response.ok) throw new Error('Save failed');
    
    alert('✅ Marked as applied!');
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// QUESTIONS TAB
async function generateAnswer(questionType) {
  if (!currentJobData) {
    alert('Analyze job first');
    return;
  }
  
  let question;
  if (questionType === 'custom') {
    question = document.getElementById('customQuestion').value.trim();
    if (!question) {
      alert('Enter a question');
      return;
    }
  } else {
    const questions = {
      'why-company': 'Why do you want to work at this company?',
      'why-you': 'Why should we hire you for this role?',
      'weakness': "What's your biggest weakness?",
      'strength': "What's your greatest strength?",
      'experience': 'Tell me about your relevant experience for this role',
      'challenge': 'Describe a technical challenge you overcame'
    };
    question = questions[questionType];
  }
  
  const resultDiv = document.getElementById('answer-result');
  resultDiv.innerHTML = '<div class="result-card">Generating answer...</div>';
  
  try {
    const response = await fetch(ANSWER_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        job: currentJobData,
        question,
        analysis: currentAnalysis
      })
    });
    
    if (!response.ok) throw new Error('Generation failed');
    
    const result = await response.json();
    
    resultDiv.innerHTML = `
      <div class="result-card">
        <h3>${question}</h3>
        <textarea class="textarea-medium" id="generatedAnswer">${result.answer}</textarea>
        <button class="btn-primary copy-btn" id="copyAnswerBtn">📋 Copy</button>
      </div>
    `;
    
    document.getElementById('copyAnswerBtn').addEventListener('click', () => {
      copyText('generatedAnswer');
    });
    
  } catch (err) {
    resultDiv.innerHTML = `<div class="status error">Error: ${err.message}</div>`;
  }
}

// UTILITIES
function copyText(elementId) {
  const el = document.getElementById(elementId);
  el.select();
  document.execCommand('copy');
  
  alert('Copied to clipboard!');
}

function showStatus(message, type, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = `<div class="status ${type}">${message}</div>`;
}