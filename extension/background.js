// Background service worker for side panel
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId });
});

// Optional: Auto-open side panel on specific sites
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    if (tab.url.includes('linkedin.com/jobs') || 
        tab.url.includes('indeed.com/viewjob') ||
        tab.url.includes('weworkremotely.com')) {
      // Could auto-open here if desired
      // chrome.sidePanel.open({ windowId: tab.windowId });
    }
  }
});