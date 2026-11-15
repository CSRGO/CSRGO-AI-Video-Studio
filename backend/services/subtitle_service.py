from pathlib import Path


class SubtitleService:
    def _format_timestamp(self, seconds):
        millis = max(0, round(seconds * 1000))
        hours, millis = divmod(millis, 3600000)
        minutes, millis = divmod(millis, 60000)
        seconds, millis = divmod(millis, 1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'

    def generate_srt(self, narration_timing, output_srt_path):
        path = Path(output_srt_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        blocks = []
        for scene in narration_timing:
            words = scene.get('narration', '').split()
            chunks = [' '.join(words[i:i+7]) for i in range(0, len(words), 7)]
            for idx, text in enumerate(chunks):
                start = scene['start_time'] + idx / len(chunks) * (scene['end_time'] - scene['start_time'])
                end = scene['start_time'] + (idx + 1) / len(chunks) * (scene['end_time'] - scene['start_time'])
                blocks.append(f'{len(blocks)+1}\n{self._format_timestamp(start)} --> {self._format_timestamp(end)}\n{text}\n')
        path.write_text('\n'.join(blocks), encoding='utf-8')
        return str(path)

subtitle_service = SubtitleService()
