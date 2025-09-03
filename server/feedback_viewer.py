#!/usr/bin/env python3
"""
Lightweight web viewer for coach feedback JSON files.
No external dependencies - uses only Python standard library.

Usage:
    uv run feedback_viewer.py [--port PORT]
    
Access at: http://localhost:8080
"""

import json
import os
import re
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse


class FeedbackViewerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the feedback viewer."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.serve_home()
        elif path == '/api/sessions':
            self.serve_sessions_list()
        elif path == '/api/session':
            self.serve_session_data(parsed)
        else:
            self.send_error(404, "Not Found")
    
    def serve_home(self):
        """Serve the main HTML page."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Coach Feedback Viewer</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .session-list {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .session-item {
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.3s;
            background: #fafafa;
        }
        .session-item:hover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: translateX(5px);
        }
        .session-item.active {
            border-color: #764ba2;
            background: linear-gradient(135deg, #f0f4ff 0%, #e8ecff 100%);
        }
        .session-content {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .turn {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
        }
        .turn-header {
            padding: 15px;
            background: linear-gradient(135deg, #f6f8fb 0%, #e9ecef 100%);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .turn-number {
            font-weight: bold;
            font-size: 1.1em;
            color: #333;
        }
        .score {
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
        }
        .score-high { background: #4caf50; }
        .score-medium { background: #ff9800; }
        .score-low { background: #f44336; }
        .urgency {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            margin-left: 10px;
        }
        .urgency-high { background: #ffebee; color: #c62828; }
        .urgency-medium { background: #fff3e0; color: #e65100; }
        .urgency-low { background: #e8f5e9; color: #2e7d32; }
        .turn-body {
            padding: 20px;
            display: none;
        }
        .turn.expanded .turn-body {
            display: block;
        }
        .interaction {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        .speaker {
            font-weight: bold;
            color: #495057;
            margin-bottom: 8px;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 1px;
        }
        .message {
            line-height: 1.6;
            color: #212529;
        }
        .coaching-section {
            margin-top: 20px;
        }
        .coaching-item {
            margin-bottom: 15px;
        }
        .coaching-label {
            font-weight: 600;
            color: #495057;
            margin-bottom: 5px;
        }
        .coaching-value {
            padding: 10px;
            background: #f1f3f5;
            border-radius: 6px;
            line-height: 1.5;
        }
        ul {
            margin-left: 20px;
            margin-top: 5px;
        }
        li {
            margin-bottom: 5px;
            line-height: 1.6;
        }
        .compliance-pass { color: #2e7d32; }
        .compliance-warning { color: #e65100; }
        .compliance-fail { color: #c62828; }
        .timestamp {
            color: #6c757d;
            font-size: 0.85em;
            margin-left: 10px;
        }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #667eea;
        }
        .auto-refresh {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 10px 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .btn-refresh {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn-refresh:hover {
            background: #5a67d8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Coach Feedback Viewer</h1>
        
        <div class="session-list">
            <h2>Available Sessions</h2>
            <div id="sessions" class="loading">Loading sessions...</div>
        </div>
        
        <div id="content" class="session-content" style="display: none;">
            <!-- Session content will be loaded here -->
        </div>
    </div>
    
    <div class="auto-refresh">
        <button class="btn-refresh" onclick="loadSessions()">🔄 Refresh</button>
    </div>
    
    <script>
        let currentSession = null;
        let autoRefreshInterval = null;
        
        async function loadSessions() {
            try {
                const response = await fetch('/api/sessions');
                const sessions = await response.json();
                
                const container = document.getElementById('sessions');
                if (sessions.length === 0) {
                    container.innerHTML = '<div class="no-data">No feedback sessions found</div>';
                    return;
                }
                
                container.innerHTML = sessions.map(session => `
                    <div class="session-item ${session.file === currentSession ? 'active' : ''}" 
                         onclick="loadSession('${session.file}')">
                        <strong>${session.scenario || 'Unknown'}</strong> - ${session.timestamp}
                        <span class="timestamp">${session.file}</span>
                    </div>
                `).join('');
                
                // Auto-load the most recent session if none selected
                if (!currentSession && sessions.length > 0) {
                    loadSession(sessions[0].file);
                } else if (currentSession) {
                    // Refresh current session data without resetting UI state
                    refreshCurrentSession();
                }
            } catch (error) {
                console.error('Failed to load sessions:', error);
                document.getElementById('sessions').innerHTML = 
                    '<div class="no-data">Failed to load sessions</div>';
            }
        }
        
        async function refreshCurrentSession() {
            if (!currentSession) return;
            
            try {
                const response = await fetch(`/api/session?file=${encodeURIComponent(currentSession)}`);
                const data = await response.json();
                
                // Store which turns are expanded before refresh
                const expandedTurns = [];
                document.querySelectorAll('.turn.expanded').forEach(turn => {
                    const match = turn.id.match(/turn-(\\d+)/);
                    if (match) expandedTurns.push(parseInt(match[1]));
                });
                
                // Update content
                renderSessionContent(data);
                
                // Restore expanded state
                expandedTurns.forEach(index => {
                    const turn = document.getElementById(`turn-${index}`);
                    if (turn) turn.classList.add('expanded');
                });
            } catch (error) {
                console.error('Failed to refresh session:', error);
            }
        }
        
        async function loadSession(filename) {
            currentSession = filename;
            loadSessions(); // Refresh to update active state
            
            try {
                const response = await fetch(`/api/session?file=${encodeURIComponent(filename)}`);
                const data = await response.json();
                
                renderSessionContent(data);
            } catch (error) {
                console.error('Failed to load session:', error);
                document.getElementById('content').innerHTML = 
                    '<div class="no-data">Failed to load session data</div>';
            }
        }
        
        function renderSessionContent(data) {
            const content = document.getElementById('content');
            content.style.display = 'block';
            
            if (!data || data.length === 0) {
                content.innerHTML = '<div class="no-data">No turns recorded yet</div>';
                return;
            }
            
            content.innerHTML = data.map((turn, index) => {
                    const score = turn.coaching?.turn_quality_score || 0;
                    const scoreClass = score >= 7 ? 'score-high' : score >= 4 ? 'score-medium' : 'score-low';
                    const urgency = turn.coaching?.urgency_level || 'low';
                    const urgencyClass = 'urgency-' + urgency;
                    
                    return `
                        <div class="turn" id="turn-${index}">
                            <div class="turn-header" onclick="toggleTurn(${index})">
                                <div>
                                    <span class="turn-number">Turn ${turn.turn}</span>
                                    <span class="timestamp">${turn.ts}</span>
                                    <span class="urgency ${urgencyClass}">${urgency.toUpperCase()}</span>
                                </div>
                                <div>
                                    <span class="score ${scoreClass}">Score: ${score}/10</span>
                                </div>
                            </div>
                            <div class="turn-body">
                                <div class="interaction">
                                    <div class="speaker">Customer:</div>
                                    <div class="message">${escapeHtml(turn.interaction?.customer || '')}</div>
                                </div>
                                <div class="interaction">
                                    <div class="speaker">Representative:</div>
                                    <div class="message">${escapeHtml(turn.interaction?.representative || '')}</div>
                                </div>
                                
                                <div class="coaching-section">
                                    ${renderCoaching(turn.coaching)}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
                
                // Auto-expand first turn only on initial load
                if (data.length > 0 && !document.querySelector('.turn.expanded')) {
                    toggleTurn(0);
                }
        }
        
        function renderCoaching(coaching) {
            if (!coaching) return '<div class="no-data">No coaching data</div>';
            
            const compliance = coaching.compliance_check || '';
            const complianceClass = compliance.startsWith('pass') ? 'compliance-pass' : 
                                   compliance.startsWith('warning') ? 'compliance-warning' : 
                                   'compliance-fail';
            
            return `
                ${coaching.immediate_strengths?.length ? `
                    <div class="coaching-item">
                        <div class="coaching-label">✅ Strengths:</div>
                        <div class="coaching-value">
                            <ul>${coaching.immediate_strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                        </div>
                    </div>
                ` : ''}
                
                ${coaching.immediate_concerns?.length ? `
                    <div class="coaching-item">
                        <div class="coaching-label">⚠️ Areas for Improvement:</div>
                        <div class="coaching-value">
                            <ul>${coaching.immediate_concerns.map(c => `<li>${escapeHtml(c)}</li>`).join('')}</ul>
                        </div>
                    </div>
                ` : ''}
                
                ${coaching.next_turn_guidance ? `
                    <div class="coaching-item">
                        <div class="coaching-label">💡 Next Step Guidance:</div>
                        <div class="coaching-value">${escapeHtml(coaching.next_turn_guidance)}</div>
                    </div>
                ` : ''}
                
                ${compliance ? `
                    <div class="coaching-item">
                        <div class="coaching-label">📋 Compliance:</div>
                        <div class="coaching-value ${complianceClass}">${escapeHtml(compliance)}</div>
                    </div>
                ` : ''}
            `;
        }
        
        function toggleTurn(index) {
            const turn = document.getElementById(`turn-${index}`);
            turn.classList.toggle('expanded');
        }
        
        function escapeHtml(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return (text || '').replace(/[&<>"']/g, m => map[m]);
        }
        
        // Load sessions on page load
        loadSessions();
        
        // Auto-refresh every 3 seconds
        setInterval(loadSessions, 3000);
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_sessions_list(self):
        """Serve list of available feedback sessions as JSON."""
        feedback_dir = Path(__file__).parent / '.coach' / 'feedback'
        
        sessions = []
        if feedback_dir.exists():
            for file in sorted(feedback_dir.glob('per_turn_*.json'), reverse=True):
                # Extract timestamp and scenario from filename
                # Format: per_turn_HH_MM_SS_DD_MM_YYYY.json
                match = re.match(r'per_turn_(\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_\d{4})\.json', file.name)
                if match:
                    timestamp_str = match.group(1)
                    # Parse timestamp
                    parts = timestamp_str.split('_')
                    if len(parts) == 6:
                        formatted = f"{parts[3]}/{parts[4]}/{parts[5]} {parts[0]}:{parts[1]}:{parts[2]}"
                    else:
                        formatted = timestamp_str
                    
                    # Try to detect scenario from file content
                    scenario = "Unknown"
                    try:
                        with open(file, 'r') as f:
                            data = json.load(f)
                            if data and len(data) > 0:
                                # Try to detect scenario from customer message
                                first_msg = data[0].get('interaction', {}).get('customer', '')
                                if 'card' in first_msg.lower() or 'lost' in first_msg.lower():
                                    scenario = "Lost Card"
                                elif 'transfer' in first_msg.lower() or 'payment' in first_msg.lower():
                                    scenario = "Failed Transfer"
                                elif 'locked' in first_msg.lower() or 'frozen' in first_msg.lower():
                                    scenario = "Account Locked"
                    except:
                        pass
                    
                    sessions.append({
                        'file': file.name,
                        'timestamp': formatted,
                        'scenario': scenario
                    })
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(sessions).encode())
    
    def serve_session_data(self, parsed):
        """Serve specific session data as JSON."""
        params = parse_qs(parsed.query)
        filename = params.get('file', [None])[0]
        
        if not filename:
            self.send_error(400, "Missing file parameter")
            return
        
        feedback_dir = Path(__file__).parent / '.coach' / 'feedback'
        file_path = feedback_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File not found")
            return
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")
    
    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        # Only log non-200 responses
        if not (200 <= int(args[1]) < 300):
            super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description='Coach Feedback Viewer')
    parser.add_argument('--port', type=int, default=8080, help='Port to run server on')
    args = parser.parse_args()
    
    server_address = ('', args.port)
    httpd = HTTPServer(server_address, FeedbackViewerHandler)
    
    print(f"\n🎯 Coach Feedback Viewer")
    print(f"=" * 40)
    print(f"Server running at: http://localhost:{args.port}")
    print(f"Press Ctrl+C to stop")
    print(f"=" * 40)
    print(f"\nAuto-refreshes every 5 seconds")
    print(f"Serving feedback from: .coach/feedback/\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()
        sys.exit(0)


if __name__ == '__main__':
    main()