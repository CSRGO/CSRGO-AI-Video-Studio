import os
import re
from typing import Dict, Any, Optional

# Brand definitions with official hex colors and optimized inline SVG icons
BRAND_REGISTRY: Dict[str, Dict[str, Any]] = {
    "git": {
        "name": "Git",
        "color": "#f05032",
        "svg": """<svg viewBox="0 0 24 24" fill="#f05032"><path d="M2.597 10.963 10.963 2.6a2.03 2.03 0 0 1 2.871 0l1.71 1.71-2.18 2.18a2.535 2.535 0 0 0-1.848-.282L9.61 4.298a.5.5 0 0 0-.707.707l1.91 1.91a2.532 2.532 0 0 0-.27 1.874l-2.2 2.2a2.534 2.534 0 1 0 1.414 1.414l2.16-2.16a2.53 2.53 0 0 0 1.83.27l1.91 1.91a.5.5 0 0 0 .707-.707l-1.91-1.91a2.53 2.53 0 0 0 .27-1.83l2.18-2.18 4.3 4.3a2.03 2.03 0 0 1 0 2.871l-8.366 8.366a2.03 2.03 0 0 1-2.871 0L2.597 13.834a2.03 2.03 0 0 1 0-2.871zM7.5 14.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z"/></svg>"""
    },
    "github": {
        "name": "GitHub",
        "color": "#ffffff",
        "svg": """<svg viewBox="0 0 24 24" fill="#ffffff"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/></svg>"""
    },
    "python": {
        "name": "Python",
        "color": "#3776ab",
        "svg": """<svg viewBox="0 0 24 24"><path fill="#3776ab" d="M11.91 2c-5.26 0-4.93 2.28-4.93 2.28l.01 2.36h5.02v.71H4.99s-3.23.37-3.23 5.23c0 4.87 2.82 5.09 2.82 5.09h1.69v-2.38s-.09-2.82 2.78-2.82h4.79s2.69.04 2.69-2.64V4.72S17.06 2 11.91 2zm-2.7 1.63a1.05 1.05 0 1 1 0 2.1 1.05 1.05 0 0 1 0-2.1z"/><path fill="#ffd43b" d="M12.09 22c5.26 0 4.93-2.28 4.93-2.28l-.01-2.36h-5.02v-.71h7.02s3.23-.37 3.23-5.23c0-4.87-2.82-5.09-2.82-5.09h-1.69v2.38s.09 2.82-2.78 2.82h-4.79s-2.69-.04-2.69 2.64v5.11s-1.53 2.72 3.62 2.72zm2.7-1.63a1.05 1.05 0 1 1 0-2.1 1.05 1.05 0 0 1 0 2.1z"/></svg>"""
    },
    "react": {
        "name": "React",
        "color": "#61dafb",
        "svg": """<svg viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="12" rx="11" ry="4.2" stroke="#61dafb" stroke-width="1.2" transform="rotate(0 12 12)"/><ellipse cx="12" cy="12" rx="11" ry="4.2" stroke="#61dafb" stroke-width="1.2" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="11" ry="4.2" stroke="#61dafb" stroke-width="1.2" transform="rotate(120 12 12)"/><circle cx="12" cy="12" r="2" fill="#61dafb"/></svg>"""
    },
    "docker": {
        "name": "Docker",
        "color": "#2496ed",
        "svg": """<svg viewBox="0 0 24 24" fill="#2496ed"><path d="M13.983 11.078h2.119a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186h-2.119a.185.185 0 0 0-.185.186v1.887c0 .102.083.185.185.185zm-2.954-5.43h2.118a.186.186 0 0 0 .186-.186V3.576a.186.186 0 0 0-.186-.186h-2.118a.185.185 0 0 0-.185.186v1.886c0 .102.083.186.185.186zm0 2.715h2.118a.186.186 0 0 0 .186-.186V6.29a.186.186 0 0 0-.186-.186h-2.118a.185.185 0 0 0-.185.186v1.887c0 .102.083.186.185.186zm-2.954 0h2.118a.186.186 0 0 0 .186-.186V6.29a.186.186 0 0 0-.186-.186H8.075a.185.185 0 0 0-.185.186v1.887c0 .102.083.186.185.186zm5.908 0h2.119a.186.186 0 0 0 .186-.186V6.29a.186.186 0 0 0-.186-.186h-2.119a.185.185 0 0 0-.185.186v1.887c0 .102.083.186.185.186zm-8.862 2.715h2.118a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186H5.121a.185.185 0 0 0-.185.186v1.887c0 .102.083.185.185.185zm2.954 0h2.118a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186H8.075a.185.185 0 0 0-.185.186v1.887c0 .102.083.185.185.185zm2.954 0h2.118a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186h-2.118a.185.185 0 0 0-.185.186v1.887c0 .102.083.185.185.185zm11.13 1.258c-.37-.234-1.077-.34-1.74-.15-.17-.79-.69-1.46-1.39-1.84l-.45-.24-.3.41c-.4.55-.58 1.27-.49 1.98-.36.19-.8.49-1.28.89H1.42c-.24 0-.42.22-.38.46.42 2.65 1.83 5.02 3.86 6.57 2.05 1.56 4.67 2.37 7.37 2.27 4.9-.17 9.17-3.41 10.42-8.23.08-.32-.23-.62-.56-.47z"/></svg>"""
    },
    "nvidia": {
        "name": "NVIDIA",
        "color": "#76b900",
        "svg": """<svg viewBox="0 0 24 24" fill="#76b900"><path d="M7.404 9.141c.21 2.502 2.072 4.417 4.542 4.417 2.47 0 4.332-1.915 4.542-4.417H7.404zm4.542-6.141c-4.721 0-8.683 3.633-9.066 8.283H0C.406 5.093 5.626 0 11.946 0c6.32 0 11.54 5.093 11.946 11.283h-2.88c-.383-4.65-4.345-8.283-9.066-8.283zm0 18c-3.15 0-5.836-1.985-6.848-4.783h-2.92C3.262 19.345 7.228 22 11.946 22c4.718 0 8.684-2.655 9.768-5.783h-2.92c-1.012 2.798-3.698 4.783-6.848 4.783z"/></svg>"""
    },
    "ai_agent": {
        "name": "AI Agent",
        "color": "#a78bfa",
        "svg": """<svg viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="1.8"><rect x="3" y="4" width="18" height="15" rx="3"/><circle cx="9" cy="10" r="1.5" fill="#a78bfa"/><circle cx="15" cy="10" r="1.5" fill="#a78bfa"/><path d="M8 15h8"/><line x1="12" y1="1" x2="12" y2="4"/><circle cx="12" cy="1" r="1" fill="#a78bfa"/></svg>"""
    },
    "neural_network": {
        "name": "Neural Network",
        "color": "#00f0ff",
        "svg": """<svg viewBox="0 0 24 24" fill="none" stroke="#00f0ff" stroke-width="1.5"><circle cx="4" cy="6" r="2" fill="#00f0ff"/><circle cx="4" cy="18" r="2" fill="#00f0ff"/><circle cx="12" cy="4" r="2" fill="#a78bfa"/><circle cx="12" cy="12" r="2" fill="#a78bfa"/><circle cx="12" cy="20" r="2" fill="#a78bfa"/><circle cx="20" cy="8" r="2" fill="#54d69a"/><circle cx="20" cy="16" r="2" fill="#54d69a"/><line x1="6" y1="6" x2="10" y2="4"/><line x1="6" y1="6" x2="10" y2="12"/><line x1="6" y1="18" x2="10" y2="12"/><line x1="6" y1="18" x2="10" y2="20"/><line x1="14" y1="4" x2="18" y2="8"/><line x1="14" y1="12" x2="18" y2="8"/><line x1="14" y1="12" x2="18" y2="16"/><line x1="14" y1="20" x2="18" y2="16"/></svg>"""
    },
    "database": {
        "name": "Database",
        "color": "#38bdf8",
        "svg": """<svg viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.8"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>"""
    },
    "terminal": {
        "name": "Terminal",
        "color": "#54d69a",
        "svg": """<svg viewBox="0 0 24 24" fill="none" stroke="#54d69a" stroke-width="1.8"><rect x="2" y="4" width="20" height="16" rx="3"/><polyline points="6 9 10 12 6 15"/><line x1="13" y1="15" x2="18" y2="15"/></svg>"""
    },
    "microsoft": {
        "name": "Microsoft",
        "color": "#00a4ef",
        "svg": """<svg viewBox="0 0 24 24"><rect x="2" y="2" width="9.5" height="9.5" fill="#f25022"/><rect x="12.5" y="2" width="9.5" height="9.5" fill="#7fba00"/><rect x="2" y="12.5" width="9.5" height="9.5" fill="#00a4ef"/><rect x="12.5" y="12.5" width="9.5" height="9.5" fill="#ffb900"/></svg>"""
    },
    "outlook": {
        "name": "Outlook",
        "color": "#0078d4",
        "svg": """<svg viewBox="0 0 24 24"><path fill="#0078d4" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/><path fill="#ffffff" d="M10 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm0 6a2 2 0 1 1 0-4 2 2 0 0 1 0 4z"/><rect x="15" y="6" width="7" height="12" rx="1.5" fill="#28a8ea"/><path fill="#ffffff" d="M15 8l3.5 2.5L22 8"/></svg>"""
    },
    "cloud": {
        "name": "Cloud Infrastructure",
        "color": "#00f0ff",
        "svg": """<svg viewBox="0 0 24 24" fill="none" stroke="#00f0ff" stroke-width="1.8"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>"""
    }
}

class BrandService:
    def __init__(self):
        pass

    def detect_brands_in_text(self, text: str) -> Dict[str, Any]:
        """Detects mentioned technologies or brands in topic or narration."""
        lower = text.lower()
        found = {}

        keywords = {
            "git": ["git", "version control", "commit", "branch", "repository"],
            "github": ["github", "pull request", "repo"],
            "python": ["python", "pip", "django", "fastapi"],
            "react": ["react", "frontend", "jsx", "vite"],
            "docker": ["docker", "container", "dockerfile"],
            "nvidia": ["nvidia", "gpu", "cuda", "gtx", "rtx"],
            "ai_agent": ["agent", "agents", "tool use", "autonomous", "reasoning"],
            "neural_network": ["neural network", "deep learning", "neurons", "weights", "backpropagation", "gradient descent"],
            "database": ["database", "sqlite", "sql", "postgres", "nosql"],
            "terminal": ["cli", "terminal", "command line", "bash", "shell"],
            "microsoft": ["microsoft", "m365", "azure", "office"],
            "outlook": ["outlook", "exchange", "mailbox", "email", "owa"],
            "cloud": ["cloud", "infrastructure", "outage", "datacenter", "cluster", "traffic"]
        }

        for brand_key, triggers in keywords.items():
            if any(re.search(r'\b' + re.escape(tr) + r'\b', lower) for tr in triggers):
                found[brand_key] = BRAND_REGISTRY[brand_key]

        return found

    def get_brand_svg(self, brand_key: str, size: int = 48) -> str:
        """Returns the SVG string for a given brand with specified dimensions."""
        b = BRAND_REGISTRY.get(brand_key.lower())
        if not b:
            return ""
        svg = b["svg"]
        # Replace or insert width and height attributes
        svg = svg.replace('<svg ', f'<svg width="{size}" height="{size}" ')
        return svg

brand_service = BrandService()

