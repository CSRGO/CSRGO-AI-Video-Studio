import os
from typing import List, Dict, Any

class SubtitleService:
    def __init__(self):
        pass

    def _format_timestamp(self, seconds: float) -> str:
        """Converts float seconds to SRT timestamp: HH:MM:SS,mmm"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def generate_srt(self, narration_timing: List[Dict[str, Any]], output_srt_path: str) -> str:
        """Generates an SRT subtitle file from scene narration timings."""
        os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
        srt_lines = []

        for i, sc in enumerate(narration_timing, 1):
            start_t = sc.get("start_time", 0.0)
            end_t = sc.get("end_time", start_t + 2.0)
            text = sc.get("narration", "").strip()

            if not text:
                continue

            srt_lines.append(str(i))
            srt_lines.append(f"{self._format_timestamp(start_t)} --> {self._format_timestamp(end_t)}")
            srt_lines.append(text)
            srt_lines.append("") # Blank line separator

        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        return output_srt_path

subtitle_service = SubtitleService()

