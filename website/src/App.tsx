import { useState } from 'react';
import './App.css';

interface ConfigType {
  title: string;
  lang: string;
  code: string;
}

const configs: Record<string, ConfigType> = {
  claudeDesktop: {
    title: 'Claude Desktop (claude_desktop_config.json)',
    lang: 'json',
    code: `{
  "mcpServers": {
    "skills-mcp": {
      "command": "skills-mcp",
      "args": ["serve"],
      "env": {
        "SKILLS_ROOT": "/Users/<your-username>/my-skills",
        "SKILLS_RELOAD": "true"
      }
    }
  }
}`
  },
  cursor: {
    title: 'Cursor Settings (features/mcp)',
    lang: 'json',
    code: `{
  "mcpServers": {
    "skills-mcp": {
      "command": "skills-mcp",
      "args": ["serve"],
      "env": {
        "SKILLS_ROOT": "/Users/<your-username>/my-skills",
        "SKILLS_RELOAD": "true"
      }
    }
  }
}`
  },
  claudeCode: {
    title: 'Claude Code Config (~/.claude/config.json)',
    lang: 'json',
    code: `{
  "mcpServers": {
    "skills-mcp": {
      "command": "skills-mcp",
      "args": ["serve"],
      "env": {
        "SKILLS_ROOT": "/Users/<your-username>/my-skills",
        "SKILLS_RELOAD": "true"
      }
    }
  }
}`
  },
  codex: {
    title: 'Codex Config (~/.codex/config.toml)',
    lang: 'toml',
    code: `[mcp.servers.skills-mcp]
command = "skills-mcp"
args = ["serve"]

[mcp.servers.skills-mcp.env]
SKILLS_ROOT = "/Users/<your-username>/my-skills"
SKILLS_RELOAD = "true"`
  }
};

function App() {
  const [activeTab, setActiveTab] = useState<keyof typeof configs>('claudeDesktop');
  const [copiedInstall, setCopiedInstall] = useState(false);
  const [copiedConfig, setCopiedConfig] = useState(false);

  const installCommand = 'uv tool install git+https://github.com/anand-92/skills-mcp';

  const handleCopyInstall = () => {
    navigator.clipboard.writeText(installCommand);
    setCopiedInstall(true);
    setTimeout(() => setCopiedInstall(false), 2000);
  };

  const handleCopyConfig = () => {
    navigator.clipboard.writeText(configs[activeTab].code);
    setCopiedConfig(true);
    setTimeout(() => setCopiedConfig(false), 2000);
  };

  return (
    <>
      {/* Background Matrix/Glow */}
      <div className="bg-grid" aria-hidden="true" />

      <div className="app-container">
        {/* ============ LEFT COLUMN ============ */}
        <div className="left-column">
          <header className="header">
            <div className="header-brand">
              🧩 skills-mcp
            </div>
            <nav className="header-links">
              <a href="#problem">Problem</a>
              <a href="#features">Features</a>
              <a href="#commands">CLI</a>
              <a href="#configure">Config</a>
              <a href="https://github.com/anand-92/skills-mcp" className="btn-github" target="_blank" rel="noopener noreferrer">
                GitHub ↗
              </a>
            </nav>
          </header>

          <section className="hero-header">
            <span className="hero-badge">⚡ compatible with all mcp clients</span>
            <h1>
              YOUR SCATTERED AI SKILLS,<br />
              <span className="text-orange">ONE UNIFIED MCP SERVER</span>
            </h1>
            <p className="hero-sub">
              Stop paying the silent context tax. Point skills-mcp at any directory of Markdown <code>SKILL.md</code> files, 
              and instantly serve procedural guidelines to Claude Code, Cursor, Cline, Codex, and Claude Desktop.
            </p>

            <div className="terminal-box">
              <span>{installCommand}</span>
              <button className="btn-copy" onClick={handleCopyInstall}>
                {copiedInstall ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </section>

          {/* Glowing Animated Architecture SVG */}
          <div className="network-graphic" aria-hidden="true">
            <svg viewBox="0 0 500 200" width="100%" height="180">
              <defs>
                <filter id="glow-blue" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="glow-orange" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {/* Scattered Inputs Flowing in */}
              <g stroke="#38bdf8" strokeWidth="1" strokeDasharray="3" opacity="0.4">
                <line x1="50" y1="40" x2="250" y2="100" />
                <line x1="40" y1="100" x2="250" y2="100" />
                <line x1="60" y1="160" x2="250" y2="100" />
              </g>

              {/* Scattered Nodes */}
              <circle cx="50" cy="40" r="5" fill="#38bdf8" filter="url(#glow-blue)" />
              <text x="65" y="44" fill="#38bdf8" fontSize="10" fontFamily="monospace">~/.claude</text>

              <circle cx="40" cy="100" r="5" fill="#38bdf8" filter="url(#glow-blue)" />
              <text x="55" y="104" fill="#38bdf8" fontSize="10" fontFamily="monospace">~/.cursor</text>

              <circle cx="60" cy="160" r="5" fill="#38bdf8" filter="url(#glow-blue)" />
              <text x="75" y="164" fill="#38bdf8" fontSize="10" fontFamily="monospace">~/.factory</text>

              {/* Unified Core Server */}
              <rect x="210" y="70" width="80" height="60" rx="8" fill="#11131e" stroke="#fb923c" strokeWidth="2" filter="url(#glow-orange)" />
              <text x="250" y="104" fill="#fff" fontSize="11" fontWeight="bold" textAnchor="middle" fontFamily="sans-serif">skills-mcp</text>

              {/* Unified Flow Out */}
              <g stroke="#fb923c" strokeWidth="1.5" opacity="0.6">
                <line x1="290" y1="100" x2="430" y2="40" />
                <line x1="290" y1="100" x2="440" y2="100" />
                <line x1="290" y1="100" x2="420" y2="160" />
              </g>

              {/* Unified Active Clients */}
              <circle cx="430" cy="40" r="5" fill="#fb923c" filter="url(#glow-orange)" />
              <text x="445" y="44" fill="#fb923c" fontSize="10" fontFamily="monospace">Claude</text>

              <circle cx="440" cy="100" r="5" fill="#fb923c" filter="url(#glow-orange)" />
              <text x="455" y="104" fill="#fb923c" fontSize="10" fontFamily="monospace">Cursor</text>

              <circle cx="420" cy="160" r="5" fill="#fb923c" filter="url(#glow-orange)" />
              <text x="435" y="164" fill="#fb923c" fontSize="10" fontFamily="monospace">Codex</text>
            </svg>
          </div>

          <div id="features" className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">🧹</div>
              <div className="feature-content">
                <h3>Gather &amp; Dedupe</h3>
                <p>Scans your tool directories and consolidates them via robust content-aware SHA-256 deduplication.</p>
              </div>
            </div>
            <div className="feature-card">
              <div className="feature-icon">📥</div>
              <div className="feature-content">
                <h3>Git &amp; Local Installs</h3>
                <p>Add new verified skills packages instantly from remote git repositories or local directory paths.</p>
              </div>
            </div>
            <div className="feature-card">
              <div className="feature-icon">🚀</div>
              <div className="feature-content">
                <h3>On-Demand Discovery</h3>
                <p>Features zero system-prompt bloat—the server feeds skills to the LLM only when specifically requested.</p>
              </div>
            </div>
          </div>
        </div>

        {/* ============ RIGHT COLUMN ============ */}
        <div className="right-column">
          {/* COMPARISON PANEL */}
          <div id="problem" className="right-section">
            <h2>🚨 The Silent Context Tax</h2>
            <div className="comparison-container">
              <div className="comp-box negative">
                <h4>✕ Standard Setup</h4>
                <ul className="comp-list">
                  <li>IDEs auto-load every single skill on startup.</li>
                  <li>Wasting 1,000+ tokens on *every single turn* you send.</li>
                  <li>Skills drift completely out of sync across CLI tools.</li>
                </ul>
              </div>
              <div className="comp-box positive">
                <h4>✓ Powered by skills-mcp</h4>
                <ul className="comp-list">
                  <li>Skills live in a single centralized folder.</li>
                  <li>Files are loaded on-demand only when requested.</li>
                  <li>Clean context window reserved entirely for code.</li>
                </ul>
              </div>
            </div>
          </div>

          {/* INTERACTIVE CONFIGURATION */}
          <div id="configure" className="right-section">
            <h2>⚙️ Easy Integration</h2>
            <div className="tab-nav">
              <button className={`tab-btn ${activeTab === 'claudeDesktop' ? 'active' : ''}`} onClick={() => setActiveTab('claudeDesktop')}>Claude Desktop</button>
              <button className={`tab-btn ${activeTab === 'cursor' ? 'active' : ''}`} onClick={() => setActiveTab('cursor')}>Cursor</button>
              <button className={`tab-btn ${activeTab === 'claudeCode' ? 'active' : ''}`} onClick={() => setActiveTab('claudeCode')}>Claude Code</button>
              <button className={`tab-btn ${activeTab === 'codex' ? 'active' : ''}`} onClick={() => setActiveTab('codex')}>Codex</button>
            </div>

            <div className="config-container">
              <div className="config-header">
                <span className="config-title">{configs[activeTab].title}</span>
                <button className="btn-copy-config" onClick={handleCopyConfig}>{copiedConfig ? 'Copied!' : 'Copy'}</button>
              </div>
              <pre className="config-code"><code>{configs[activeTab].code}</code></pre>
            </div>
          </div>

          {/* DETAILED DOCUMENTATION & CLI */}
          <div id="commands" className="right-section">
            <h2>📖 CLI Guide, Env Vars &amp; Skill Anatomy</h2>
            
            <div className="doc-card">
              <h3>skills-mcp gather [options]</h3>
              <p>Consolidate folders, analyze file content-hashes, and safely dedupe redundant skills packages.</p>
              <ul style={{ fontSize: '13px', color: 'var(--text-muted)', paddingLeft: '18px', marginBottom: '14px', lineHeight: '1.6' }}>
                <li><code>--dest &lt;path&gt;</code>: Customize output directory (defaults to <code>~/my-skills</code>).</li>
                <li><code>--on-conflict [skip|newest|rename]</code>: Choose resolution when same-slug skills have different contents.</li>
                <li><code>--symlink</code>: Symlink each skill folder into the destination instead of copying.</li>
                <li><code>--delete-sources</code>: Purge original scattered dotfolders automatically after copy.</li>
              </ul>
              <pre className="doc-pre">
{`$ skills-mcp gather --on-conflict rename --delete-sources
Plan:
  [Copy] ~/.claude/skills/git-pr/SKILL.md -> ~/my-skills/git-pr/SKILL.md
  [Rename] ~/.cursor/skills/git-pr/SKILL.md -> ~/my-skills/git-pr-2/SKILL.md
Do you want to proceed? (Y/n) y
Gather completed!`}
              </pre>
            </div>

            <div className="doc-card">
              <h3>skills-mcp add [source] [options]</h3>
              <p>Resolve and install dynamic skills packs from git URLs or local files.</p>
              <ul style={{ fontSize: '13px', color: 'var(--text-muted)', paddingLeft: '18px', marginBottom: '14px', lineHeight: '1.6' }}>
                <li><code>--skill &lt;name&gt;</code>: Install only a specific skill by slug/name (repeatable).</li>
                <li><code>--list, -l</code>: Print all available skills in the package without installing.</li>
                <li><code>--force, -f</code>: Overwrite existing destination skill folders.</li>
              </ul>
              <pre className="doc-pre">
{`$ skills-mcp add git+https://github.com/someone/skills-pack --skill code-review`}
              </pre>
            </div>

            <div className="doc-card">
              <h3>🔧 Server Configuration (Environment Variables)</h3>
              <p>Customize the server execution environment by adjusting these keys in your client configs:</p>
              <ul style={{ fontSize: '13px', color: 'var(--text-muted)', paddingLeft: '18px', lineHeight: '1.7' }}>
                <li style={{ marginBottom: '6px' }}><code>SKILLS_ROOT</code>: Colon-separated (or semicolon-separated on Windows) folder paths to discover skills (defaults to <code>~/my-skills</code>).</li>
                <li style={{ marginBottom: '6px' }}><code>SKILLS_MAIN_FILE_NAME</code>: Marker filename that indexes a skill (defaults to <code>SKILL.md</code>).</li>
                <li style={{ marginBottom: '6px' }}><code>SKILLS_SERVER_NAME</code>: Custom identifier for your MCP server (defaults to <code>skills</code>).</li>
                <li><code>SKILLS_RELOAD</code>: Enable hot-reloads of files when modified (defaults to <code>false</code>).</li>
              </ul>
            </div>

            <div className="doc-card" id="docs">
              <h3>Custom Skill Anatomy</h3>
              <p>Expose custom procedures using flat YAML-ish frontmatter blocks at the top of your markdown files.</p>
              <pre className="doc-pre">
{`---
name: git-pr-workflow
description: Standardized branch, commit, and PR flow.
---
# Git Pull Request Workflow
Check out branches and stage changes safely...`}
              </pre>
            </div>
          </div>
        </div>
      </div>

      <footer className="footer">
        <p>© 2026 skills-mcp. Created by Nik Anand. Released under Apache-2.0 License.</p>
      </footer>
    </>
  );
}

export default App;
