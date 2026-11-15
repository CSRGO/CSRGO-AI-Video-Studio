import os
import json
import re
from typing import Dict, Any, List, Optional

LEMO_STYLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "lemo-opuscar", "styles"))

class LemoLoader:
    def __init__(self, styles_dir: str = LEMO_STYLES_DIR):
        self.styles_dir = styles_dir
        self._cache: Dict[str, Dict[str, Any]] = {}

    def list_styles(self) -> List[Dict[str, Any]]:
        styles = []
        if not os.path.exists(self.styles_dir):
            return styles

        for item in sorted(os.listdir(self.styles_dir)):
            item_path = os.path.join(self.styles_dir, item)
            if os.path.isdir(item_path) and not item.startswith(("_", ".")):
                json_path = os.path.join(item_path, "style.json")
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            styles.append({
                                "slug": data.get("slug", item),
                                "name": data.get("en", item.replace("-", " ").title()),
                                "category": data.get("category_en", "Visual"),
                                "description": data.get("line", ""),
                                "has_style_md": os.path.exists(os.path.join(item_path, "STYLE.md"))
                            })
                    except Exception:
                        pass
        return styles

    def load_style_rule(self, style_slug: str) -> Dict[str, Any]:
        """Loads and extracts token-optimized instruction card for a Lemo style."""
        if style_slug in self._cache:
            return self._cache[style_slug]

        style_path = os.path.join(self.styles_dir, style_slug)
        json_path = os.path.join(style_path, "style.json")
        md_path = os.path.join(style_path, "STYLE.md")

        metadata: Dict[str, Any] = {"slug": style_slug, "name": style_slug.replace("-", " ").title()}
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass

        raw_md = ""
        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    raw_md = f.read()
            except Exception:
                pass

        # Extract compact sections: essence, colors, motion
        essence = self._extract_section(raw_md, ["Essence", "1. Essence"])
        color_logic = self._extract_section(raw_md, ["Colour logic", "Color logic", "3. Colour logic"])
        motion_quality = self._extract_section(raw_md, ["Motion quality", "5. Motion quality"])
        camera_grammar = self._extract_section(raw_md, ["Camera grammar", "6. Camera grammar"])

        # Construct concise director prompt card
        compact_instructions = f"""STYLE: {metadata.get('en', metadata.get('name', style_slug))} ({style_slug})
{metadata.get('line', '')}

ESSENCE & RULES:
{essence[:350] if essence else 'Clean graphic precision with strict grid alignment.'}

COLOR LOGIC:
{color_logic[:250] if color_logic else 'Primary brand palette with one saturated signal color.'}

MOTION & CAMERA:
{motion_quality[:250] if motion_quality else 'Snappy ease cubic-bezier(0.7,0,0.2,1), clean wipes, no jitter.'}
"""

        res = {
            "slug": style_slug,
            "name": metadata.get("en", metadata.get("name", style_slug)),
            "line": metadata.get("line", ""),
            "metadata": metadata,
            "raw_md_path": md_path if os.path.exists(md_path) else None,
            "compact_instructions": compact_instructions.strip()
        }
        self._cache[style_slug] = res
        return res

    def _extract_section(self, text: str, header_candidates: List[str]) -> str:
        if not text:
            return ""
        for h in header_candidates:
            pattern = rf"#+\s*{re.escape(h)}.*?\n(.*?)(?=\n#+ |\Z)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                clean = re.sub(r"\s+", " ", match.group(1)).strip()
                return clean
        return ""

lemo_loader = LemoLoader()

