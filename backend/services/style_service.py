import os
import json
from typing import List, Dict, Any, Optional

STYLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "lemo-opuscar", "styles"))

class StyleService:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_styles()

    def _load_styles(self):
        if not os.path.exists(STYLES_DIR):
            return

        for entry in os.listdir(STYLES_DIR):
            style_dir = os.path.join(STYLES_DIR, entry)
            if not os.path.isdir(style_dir) or entry.startswith("_") or entry.startswith("."):
                continue

            style_json = os.path.join(style_dir, "style.json")
            if os.path.exists(style_json):
                try:
                    with open(style_json, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    slug = data.get("slug", entry)
                    poster_path = os.path.join(style_dir, "poster.jpg")
                    has_poster = os.path.exists(poster_path)

                    style_info = {
                        "slug": slug,
                        "num": data.get("num", ""),
                        "name": data.get("en", slug.replace("-", " ").title()),
                        "name_cn": data.get("cn", ""),
                        "category": data.get("category_en", "General"),
                        "category_cn": data.get("category_cn", ""),
                        "film": data.get("film", ""),
                        "description": data.get("line", ""),
                        "description_cn": data.get("line_cn", ""),
                        "uses": data.get("uses", []),
                        "duration": data.get("dur", 45.0),
                        "has_poster": has_poster,
                        "poster_path": poster_path if has_poster else None,
                        "style_md_path": os.path.join(style_dir, "STYLE.md")
                    }
                    self._cache[slug] = style_info
                except Exception as err:
                    print(f"Error loading style {entry}: {err}")

    def list_styles(self, search: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._cache:
            self._load_styles()

        results = list(self._cache.values())
        if category and category.lower() != "all":
            results = [s for s in results if s["category"].lower() == category.lower()]

        if search:
            q = search.lower()
            results = [
                s for s in results
                if q in s["slug"].lower()
                or q in s["name"].lower()
                or q in s["category"].lower()
                or q in s["description"].lower()
                or any(q in u.lower() for u in s["uses"])
            ]

        results.sort(key=lambda s: int(s["num"]) if s["num"].isdigit() else 999)
        return results

    def get_style(self, slug: str) -> Optional[Dict[str, Any]]:
        if not self._cache:
            self._load_styles()
        return self._cache.get(slug)

    def get_categories(self) -> List[str]:
        if not self._cache:
            self._load_styles()
        cats = {s["category"] for s in self._cache.values() if s["category"]}
        return sorted(list(cats))

    def resolve_style_spec(self, slug: str) -> Dict[str, Any]:
        """
        Resolves complete, executable design specifications for the selected style.
        Ensures that every supported style strictly governs:
        - Palette (background, cards, borders, accents, text, grid)
        - Typography (headlines, serif accents, monospace labels)
        - Character Host design (illustrated 2D host vs blueprint drafting hand vs terminal)
        - Prop & Container styling (warm paper cards vs cyanotype blueprint vs dark glass)
        - Motion & Camera grammar
        - Audio & Music mood
        """
        s = slug.lower().strip()

        # 1. Blueprint Style (Cyanotype Engineering Drawing)
        if "blueprint" in s:
            return {
                "style_id": "blueprint",
                "name": "Cyanotype Engineering Blueprint",
                "palette": {
                    "bg": "#10264d",
                    "bg_gradient": "linear-gradient(135deg, #0e2042 0%, #17386d 100%)",
                    "card_bg": "rgba(22, 50, 96, 0.85)",
                    "card_border": "#4a7bc7",
                    "border_width": 2,
                    "primary": "#e6f0fa",
                    "secondary": "#7ba8e8",
                    "signal": "#ef4444", # Red rubber stamp ink
                    "text_primary": "#ffffff",
                    "text_secondary": "#a2c2ed",
                    "grid_type": "drafting_grid",
                    "grid_color": "rgba(255, 255, 255, 0.08)",
                    "container_radius": 6
                },
                "typography": {
                    "headline_font": "'JetBrains Mono', monospace",
                    "accent_font": "'JetBrains Mono', monospace",
                    "body_font": "'JetBrains Mono', monospace",
                    "case": "uppercase"
                },
                "character_host": {
                    "enabled": False, # Blueprint uses machine drawing / drafting hand
                    "type": "drafting_compass"
                },
                "props": {
                    "style": "technical_wireframe",
                    "shadows": False,
                    "stamp_seal": True
                },
                "camera_style": "drafting_pan",
                "music_mood": "technical_ambient"
            }

        # 2. Dark Keynote / Neon Tubes / Cyber Style
        elif any(k in s for k in ["dark", "neon", "cyber", "circuit", "terminal"]):
            return {
                "style_id": "dark-keynote",
                "name": "Dark Keynote Tech & Neon",
                "palette": {
                    "bg": "#090c15",
                    "bg_gradient": "radial-gradient(circle at 50% 30%, #11172a 0%, #080a11 100%)",
                    "card_bg": "rgba(18, 22, 36, 0.88)",
                    "card_border": "#00f0ff",
                    "border_width": 1.5,
                    "primary": "#00f0ff",
                    "secondary": "#a78bfa",
                    "signal": "#f43f5e",
                    "text_primary": "#f8fafc",
                    "text_secondary": "#94a3b8",
                    "grid_type": "cyber_dots",
                    "grid_color": "rgba(0, 240, 255, 0.07)",
                    "container_radius": 16
                },
                "typography": {
                    "headline_font": "'Space Grotesk', sans-serif",
                    "accent_font": "'JetBrains Mono', monospace",
                    "body_font": "'Space Grotesk', sans-serif",
                    "case": "normal"
                },
                "character_host": {
                    "enabled": True,
                    "type": "vector_mascot"
                },
                "props": {
                    "style": "dark_glass",
                    "shadows": True,
                    "stamp_seal": False
                },
                "camera_style": "cinematic_drift",
                "music_mood": "cyber_pulse"
            }

        # 3. Swiss Motion / Warm Editorial (Default Creative Benchmark)
        else:
            return {
                "style_id": "swiss-motion",
                "name": "Swiss Motion & Warm Editorial",
                "palette": {
                    "bg": "#f8f6f0", # Warm editorial paper
                    "bg_gradient": "linear-gradient(180deg, #faf8f3 0%, #f4f0e8 100%)",
                    "card_bg": "#ffffff",
                    "card_border": "#e8e4da",
                    "border_width": 1.5,
                    "primary": "#e03e2d", # Terracotta signal red
                    "secondary": "#1a1a1a", # Deep black ink
                    "signal": "#e03e2d",
                    "text_primary": "#141414",
                    "text_secondary": "#57534e",
                    "grid_type": "editorial_dots",
                    "grid_color": "rgba(0, 0, 0, 0.05)",
                    "container_radius": 20
                },
                "typography": {
                    "headline_font": "'Space Grotesk', sans-serif",
                    "accent_font": "'Newsreader', serif", # Italic serif for emphasis
                    "body_font": "'Space Grotesk', sans-serif",
                    "case": "normal"
                },
                "character_host": {
                    "enabled": True,
                    "type": "bearded_engineer", # Animated host in beanie & glasses
                    "color_beanie": "#1e232a",
                    "color_jacket": "#69665c",
                    "color_skin": "#f8dfd0"
                },
                "props": {
                    "style": "clean_editorial",
                    "shadows": True,
                    "stamp_seal": True
                },
                "camera_style": "snappy_beat",
                "music_mood": "warm_rhythmic"
            }

style_service = StyleService()
