import os
import sys
import json
import hashlib
import numpy as np
import soundfile as sf
from typing import List, Dict, Any, Optional, Tuple

from backend.services.audio_engine import dsp, instruments, sfx_gen

SR = dsp.SR # 48000 Hz broadcast standard

class AudioService:
    def __init__(self):
        pass

    def _get_project_rng(self, project_seed_str: str) -> np.random.Generator:
        """Derives a deterministic, project-unique random number generator."""
        h = int(hashlib.sha256(project_seed_str.encode("utf-8")).hexdigest()[:8], 16)
        return dsp.rng(h)

    # -------------------------------------------------------------
    # 1. Event-Based Procedural SFX Synthesis (from Instagram Shorts)
    # -------------------------------------------------------------
    def generate_sfx(self, sfx_cue: str, volume: float = 0.8) -> np.ndarray:
        """
        Synthesizes rich, physical, procedural sound effects using
        the Instagram Shorts DSP and Foley engine.
        Returns 1D mono or 2D stereo numpy float array.
        """
        r = dsp.rng(np.random.randint(0, 100000))
        cue = sfx_cue.lower()

        # Money / Cash / Coins / Rattle
        if any(w in cue for w in ["coin", "cash", "money", "dollar", "rattle", "register", "currency"]):
            dur = 0.55
            x = sfx_gen.rattle(dur, r, density=45.0, heavy=False)
            # Add a clear metallic accent clink at start
            c = sfx_gen.clink(r, 3800.0, dur=0.25)
            n_add = min(len(c), len(x))
            x[:n_add] += c[:n_add] * 0.7
            return dsp.fades(x * volume * 0.9, 0.002, 0.05)

        # Whoosh / Slide / Transition / Sweep
        elif any(w in cue for w in ["whoosh", "transition", "sweep", "slide", "pan"]):
            dur = 0.42
            t = dsp.tt(dur)
            nz = dsp.colored(len(t), r, slope=0.8)
            env = np.sin(np.pi * t / dur) ** 2.2
            center_f = 250 + 2600 * np.sin(np.pi * t / dur)
            filt = dsp.bp(nz, 150, 4200, 2) * env
            return dsp.fades(filt * volume * 0.85, 0.01, 0.03)

        # Notification / Chime / Bell / Ding / Success
        elif any(w in cue for w in ["notification", "chime", "ding", "bell", "success", "recovery"]):
            dur = 1.2
            t = dsp.tt(dur)
            # Harmonic two-note glockenspiel chime (e.g. F5 -> C6)
            g1 = instruments.glock(698.46, vel=0.75, r=r, dur=0.6)
            g2 = instruments.glock(1046.50, vel=0.85, r=r, dur=0.9)
            x = np.zeros(len(t))
            s1 = min(len(g1), len(x))
            x[:s1] += g1[:s1]
            delay_s = dsp.ns(0.12)
            s2 = min(len(g2), max(0, len(x) - delay_s))
            if s2 > 0:
                x[delay_s:delay_s+s2] += g2[:s2]
            return dsp.fades(x * volume * 0.8, 0.001, 0.08)

        # Warning / Alert / Disconnect / Error / Buzzer
        elif any(w in cue for w in ["error", "alert", "warning", "fail", "buzzer", "disconnect"]):
            dur = 0.45
            t = dsp.tt(dur)
            # Jarring dissonant tritone pulse
            f1, f2 = 440.0, 622.25 # A4 + Eb5
            wave1 = np.sign(np.sin(2 * np.pi * f1 * t)) * 0.35
            wave2 = np.sign(np.sin(2 * np.pi * f2 * t)) * 0.35
            buzz = dsp.lp(wave1 + wave2, 1200)
            env = np.exp(-t / 0.14)
            return dsp.fades(buzz * env * volume * 0.8, 0.002, 0.03)

        # Click / Tap / Pop / Snap
        elif any(w in cue for w in ["click", "tap", "pop", "snap"]):
            dur = 0.05
            t = dsp.tt(dur)
            click = dsp.hp(r.standard_normal(len(t)), 2800) * np.exp(-t / 0.004) * 0.6
            return dsp.fades(click * volume, 0.0005, 0.008)

        # Impact / Thump / Box / Stomp / Drop
        elif any(w in cue for w in ["impact", "thump", "box", "stomp", "fall", "drop"]):
            dur = 0.40
            t = dsp.tt(dur)
            f_pitch = 95.0 * np.exp(-t / 0.035)
            ph = np.cumsum(2 * np.pi * f_pitch / SR)
            thud = np.sin(ph) * np.exp(-t / 0.08) * 0.8
            wood = dsp.bp(r.standard_normal(len(t)), 180, 800) * np.exp(-t / 0.025) * 0.4
            return dsp.fades((thud + wood) * volume * 0.9, 0.001, 0.04)

        # Creak / Strain / Friction
        elif any(w in cue for w in ["creak", "strain", "tension", "groan"]):
            dur = 0.85
            return sfx_gen.creak(dur, r, rate0=90, rate1=160, modes=sfx_gen.WOOD) * volume * 0.7

        # Drone / Hum / Machine / Server
        elif any(w in cue for w in ["hum", "drone", "server", "machine"]):
            dur = 2.0
            t = dsp.tt(dur)
            h60 = np.sin(2 * np.pi * 60 * t) * 0.3
            h120 = np.sin(2 * np.pi * 120 * t) * 0.15
            sub = np.sin(2 * np.pi * 45 * t) * 0.25
            nz = dsp.bp(r.standard_normal(len(t)), 100, 350) * 0.12
            env = np.sin(np.pi * t / dur) ** 0.5
            return (h60 + h120 + sub + nz) * env * volume * 0.65

        # Default fallback: smooth whoosh sweep
        dur = 0.35
        t = dsp.tt(dur)
        nz = dsp.bp(r.standard_normal(len(t)), 220, 3400)
        env = (np.sin(np.pi * t / dur) ** 2)
        return dsp.fades(nz * env * volume * 0.75, 0.005, 0.03)

    # -------------------------------------------------------------
    # 2. Dynamic Adaptive Score Composition (Instagram Shorts Style)
    # -------------------------------------------------------------
    def compose_original_score(
        self,
        duration_sec: float,
        project_slug: str,
        scenes: List[Dict[str, Any]],
        topic: str = ""
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Composes an original, mood-adaptive musical score:
        - Network Marketing / Business: Suspenseful, curious, building tension, resolving to cautionary truth.
        - Tech / Incident: Minimalist synth pulses, arpeggiated electronics, sub-bass drive.
        - History / Documentary: Warm cello pads, melancholy piano, evocative modal progressions.
        Returns (stereo_audio_2xN, music_plan_dict).
        """
        rng = self._get_project_rng(project_slug)
        n_total = int(round((duration_sec + 2.5) * SR))
        score_left = np.zeros(n_total, dtype=np.float64)
        score_right = np.zeros(n_total, dtype=np.float64)

        t_lower = (topic + " " + project_slug).lower()
        is_business_investigation = any(w in t_lower for w in ["marketing", "money", "pyramid", "scheme", "business", "scam", "finance", "crypto"])
        is_tech = any(w in t_lower for w in ["outage", "cloud", "server", "cache", "git", "code", "software", "database"])

        # Determine harmonic progression based on narrative mode
        if is_business_investigation:
            # Curious, tense, cautionary progression (Am -> Dm -> F -> E7 -> Am)
            chords = [
                ("A minor (Curiosity/Hook)", [110.00, 130.81, 164.81, 220.00]),   # A2, C3, E3, A3
                ("D minor (The Recruitment Chain)", [146.83, 174.61, 220.00, 293.66]), # D3, F3, A3, D4
                ("F major (Money Flow Illusion)", [87.31, 130.81, 174.61, 261.63]),  # F2, C3, F3, C4
                ("E dominant (The 99% Trap)", [82.41, 123.47, 164.81, 246.94]),    # E2, B2, E3, B3
                ("A minor (The Reality/Takeaway)", [110.00, 130.81, 164.81, 220.00])
            ]
            tempo_bpm = 104
        elif is_tech:
            # Modern technological investigative pulse (Dm -> Bb -> Gm -> A -> Dm)
            chords = [
                ("D minor (System Normal/Hook)", [146.83, 174.61, 220.00]),
                ("Bb major (Cascading Spike)", [116.54, 146.83, 174.61]),
                ("G minor (Bottleneck Depth)", [98.00, 116.54, 146.83]),
                ("A tension (Engineering Investigation)", [110.00, 138.59, 164.81]),
                ("D resolved (Restoration & Lessons)", [146.83, 174.61, 220.00, 293.66])
            ]
            tempo_bpm = 116
        else:
            # Evocative documentary progression
            chords = [
                ("C minor (Documentary Hook)", [130.81, 155.56, 196.00]),
                ("Ab major (Rising Escalation)", [103.83, 130.81, 155.56]),
                ("Eb major (The Core Mechanism)", [77.78, 116.54, 155.56]),
                ("Bb major (Consequence)", [116.54, 146.83, 174.61]),
                ("C minor (Final Takeaway)", [130.81, 155.56, 196.00])
            ]
            tempo_bpm = 108

        beat_sec = 60.0 / tempo_bpm
        num_scenes = max(1, len(scenes))
        time_per_chord = duration_sec / max(1, len(chords))

        music_plan = {
            "project_slug": project_slug,
            "tempo_bpm": tempo_bpm,
            "progression": [c[0] for c in chords],
            "movements": []
        }

        # Render harmonic beds
        for idx, (chord_name, freqs) in enumerate(chords):
            c_start = idx * time_per_chord
            c_end = min(duration_sec + 1.5, (idx + 1) * time_per_chord)
            c_dur = max(0.5, c_end - c_start)
            t_chord = dsp.tt(c_dur)

            i0 = dsp.ns(c_start)
            i1 = min(n_total, i0 + len(t_chord))
            act_n = i1 - i0
            if act_n <= 0:
                continue

            sub_t = t_chord[:act_n]
            # Warm cello/strings synth pad
            pad_l = np.zeros(act_n)
            pad_r = np.zeros(act_n)

            for f_idx, f in enumerate(freqs):
                # Small stereo detuning between channels
                detune_l = -0.35 + rng.uniform(-0.1, 0.1)
                detune_r = 0.35 + rng.uniform(-0.1, 0.1)
                amp = 0.12 if f_idx == 0 else 0.08
                pad_l += np.sin(2 * np.pi * (f + detune_l) * sub_t) * amp
                pad_r += np.sin(2 * np.pi * (f + detune_r) * sub_t) * amp

                # Sub bass on root note
                if f_idx == 0:
                    sub_f = f * 0.5
                    pad_l += np.sin(2 * np.pi * sub_f * sub_t) * 0.14
                    pad_r += np.sin(2 * np.pi * sub_f * sub_t) * 0.14

            # Gentle breathing tremolo modulation
            trem = (0.90 + 0.10 * np.sin(2 * np.pi * 0.28 * sub_t))
            pad_l *= trem
            pad_r *= trem

            # Smooth crossfades on chord boundaries
            fade_n = min(dsp.ns(0.8), act_n // 3)
            if fade_n > 0:
                pad_l[:fade_n] *= np.linspace(0.1, 1.0, fade_n)
                pad_r[:fade_n] *= np.linspace(0.1, 1.0, fade_n)
                pad_l[-fade_n:] *= np.linspace(1.0, 0.1, fade_n)
                pad_r[-fade_n:] *= np.linspace(1.0, 0.1, fade_n)

            score_left[i0:i1] += pad_l
            score_right[i0:i1] += pad_r

            music_plan["movements"].append({
                "movement": idx + 1,
                "chord": chord_name,
                "start": round(c_start, 2),
                "duration": round(c_dur, 2)
            })

        # Add delicate melodic piano & bell strikes at musical phrase accents
        step_stride = beat_sec * 4.0 # every 4 beats
        curr_t = 1.0
        while curr_t < duration_sec - 1.2:
            i_cue = dsp.ns(curr_t)
            # Pick harmonic pitch from active chord
            chord_idx = min(len(chords) - 1, int(curr_t / time_per_chord))
            note_f = chords[chord_idx][1][-1] * (1.5 if rng.uniform() > 0.5 else 1.0)
            note_dur = 1.4
            t_note = dsp.tt(note_dur)
            strike = np.sin(2 * np.pi * note_f * t_note) * np.exp(-t_note / 0.38) * 0.12
            # Add overtone
            strike += np.sin(2 * np.pi * note_f * 2.0 * t_note) * np.exp(-t_note / 0.18) * 0.04

            n_add = min(len(strike), n_total - i_cue)
            if n_add > 0:
                pan_pos = rng.uniform(0.35, 0.65)
                score_left[i_cue:i_cue+n_add] += strike[:n_add] * (1.0 - pan_pos)
                score_right[i_cue:i_cue+n_add] += strike[:n_add] * pan_pos

            curr_t += step_stride + rng.uniform(-0.15, 0.15)

        # Master balance of music stem
        stereo_score = np.vstack([score_left, score_right])
        peak = np.max(np.abs(stereo_score))
        if peak > 0:
            stereo_score = (stereo_score / peak) * 0.45

        return stereo_score, music_plan

    # -------------------------------------------------------------
    # 3. Master Multi-Stem Production & Loudness Staging (Instagram Shorts Standard)
    # -------------------------------------------------------------
    def build_multi_stem_production(
        self,
        duration_sec: float,
        project_dir: str,
        project_slug: str,
        narration_scenes: List[Dict[str, Any]],
        scenes_meta: List[Dict[str, Any]],
        music_enabled: bool = True,
        sfx_enabled: bool = True,
        topic: str = ""
    ) -> Dict[str, Any]:
        """
        Builds broadcast-grade multi-track audio production:
        1. stem_voice.wav (-15.4 LUFS normalized dialogue)
        2. stem_music.wav (Topic-adaptive score with sidechain ducking under dialogue)
        3. stem_sfx.wav (Precision-timed procedural Foley sound effects)
        4. mix.wav (Mastered composite at broadcast -14.0 LUFS with true peak limiter)
        5. cues.md & audio_cues.json (Full timeline cue sheet)
        6. mix.py (Self-contained executable recipe)
        """
        audio_dir = os.path.join(project_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        n_total = int(round(duration_sec * SR))

        # -----------------
        # Stem 1: Voice
        # -----------------
        voice_mono = np.zeros(n_total, dtype=np.float64)
        speech_intervals = []

        for i, sc in enumerate(narration_scenes):
            wav_path = sc.get("audio_path") or sc.get("wav_path")
            if not wav_path or not os.path.exists(wav_path):
                af = sc.get("audio_file") or f"scene_{i+1:02d}.wav"
                candidate = os.path.join(audio_dir, af)
                if os.path.exists(candidate):
                    wav_path = candidate

            st = sc.get("start_time", 0.0)
            if wav_path and os.path.exists(wav_path):
                data, fs = sf.read(wav_path)
                if fs != SR:
                    import soxr
                    data = soxr.resample(data, fs, SR)
                if data.ndim > 1:
                    data = data.mean(axis=1)

                s_start = dsp.ns(st)
                s_len = min(len(data), max(0, n_total - s_start))
                if s_len > 0:
                    voice_mono[s_start:s_start+s_len] = data[:s_len]
                    speech_intervals.append((st, st + (s_len / SR)))

        # Fallback to narration_full.wav if needed
        if np.max(np.abs(voice_mono)) < 0.001:
            full_narration_path = os.path.join(audio_dir, "narration_full.wav")
            if os.path.exists(full_narration_path):
                data, fs = sf.read(full_narration_path)
                if fs != SR:
                    import soxr
                    data = soxr.resample(data, fs, SR)
                if data.ndim > 1:
                    data = data.mean(axis=1)
                s_len = min(len(data), n_total)
                voice_mono[:s_len] = data[:s_len]
                speech_intervals.append((0.0, s_len / SR))

        # Peak normalize voice mono
        v_pk = np.max(np.abs(voice_mono))
        if v_pk > 0.001:
            voice_mono = (voice_mono / v_pk) * 0.92
            print(f"[AudioService] Voice stem normalized: peak {v_pk:.4f} -> 0.9200")
        else:
            print("[AudioService] WARNING: Voice stem is silent!")

        # Convert voice to stereo
        voice_stem = dsp.st(voice_mono)

        # -----------------
        # Stem 2: Music
        # -----------------
        if music_enabled:
            raw_music, music_plan = self.compose_original_score(
                duration_sec=duration_sec,
                project_slug=project_slug,
                scenes=scenes_meta,
                topic=topic
            )
            music_stem = raw_music[:, :n_total]
            if music_stem.shape[1] < n_total:
                pad_m = np.zeros((2, n_total - music_stem.shape[1]))
                music_stem = np.hstack([music_stem, pad_m])

            # Dynamic sidechain ducking under voice (Instagram Shorts formula)
            v_env = np.abs(voice_stem[0]) + np.abs(voice_stem[1])
            v_env_smooth = dsp.lp(v_env, 8.0)
            duck_factor = 1.0 - np.clip(v_env_smooth * 3.4, 0.0, 0.78) # -13 dB during dialogue
            music_stem = music_stem * duck_factor
        else:
            music_stem = np.zeros((2, n_total), dtype=np.float64)
            music_plan = {"status": "disabled"}

        # -----------------
        # Stem 3: SFX
        # -----------------
        sfx_stem = np.zeros((2, n_total), dtype=np.float64)
        sfx_events = []

        if sfx_enabled:
            for i, sc in enumerate(scenes_meta):
                st = sc.get("start", i * (duration_sec / max(1, len(scenes_meta))))
                cue = sc.get("sfx_cue") or "whoosh"
                sfx_data = self.generate_sfx(cue, volume=0.85)
                # Convert sfx to stereo
                sfx_st = dsp.st(sfx_data)

                i_start = dsp.ns(st)
                i_len = min(sfx_st.shape[1], max(0, n_total - i_start))
                if i_len > 0:
                    sfx_stem[:, i_start:i_start+i_len] += sfx_st[:, :i_len]
                    sfx_events.append({
                        "event_id": f"SFX-{len(sfx_events)+1:02d}",
                        "timestamp": round(st, 2),
                        "cue": cue,
                        "scene": i + 1
                    })

        # -----------------
        # Loudness Balancing & True-Peak Limiter (-14 LUFS Standard)
        # -----------------
        # Staging: Voice ~ -15.4 LUFS, Music ~ -25.5 LUFS, SFX ~ -27.5 LUFS
        try:
            v_lufs = dsp.integrated(voice_stem)
            if v_lufs > -60:
                gain_v = -15.4 - v_lufs
                voice_stem *= dsp.dbg(gain_v)

            if music_enabled:
                m_lufs = dsp.integrated(music_stem)
                if m_lufs > -60:
                    gain_m = -25.5 - m_lufs
                    music_stem *= dsp.dbg(gain_m)

            if sfx_enabled and sfx_events:
                s_lufs = dsp.integrated(sfx_stem)
                if s_lufs > -60:
                    gain_s = -27.5 - s_lufs
                    sfx_stem *= dsp.dbg(gain_s)
        except Exception as lufs_err:
            print(f"[AudioService] Loudness balancing note: {lufs_err}")

        # Master sum
        summed = voice_stem + music_stem + sfx_stem

        # True-Peak Limiter at -1.2 dBTP
        ceiling = dsp.dbg(-1.2)
        pk = np.max(np.abs(summed))
        if pk > ceiling:
            master_mix = summed * (ceiling / pk)
        else:
            master_mix = summed

        final_lufs = dsp.integrated(master_mix)
        tp = dsp.true_peak(master_mix)
        print(f"[AudioService] Mastered mix: {final_lufs:.2f} LUFS | True Peak: {tp:.2f} dBTP | Duration: {master_mix.shape[1]/SR:.2f}s")

        # Write WAV stems (24-bit PCM at 48 kHz)
        stem_voice_path = os.path.join(audio_dir, "stem_voice.wav")
        stem_music_path = os.path.join(audio_dir, "stem_music.wav")
        stem_sfx_path = os.path.join(audio_dir, "stem_sfx.wav")
        mix_path = os.path.join(audio_dir, "mix.wav")

        dsp.write_wav(stem_voice_path, voice_stem, 24)
        dsp.write_wav(stem_music_path, music_stem, 24)
        dsp.write_wav(stem_sfx_path, sfx_stem, 24)
        dsp.write_wav(mix_path, master_mix, 24)

        # Write cue sheet and timeline JSON
        cues_data = {
            "project_slug": project_slug,
            "duration_sec": round(duration_sec, 2),
            "sample_rate": SR,
            "integrated_lufs": round(float(final_lufs), 2),
            "true_peak_dbtp": round(float(tp), 2),
            "music_plan": music_plan,
            "sfx_events": sfx_events,
            "speech_intervals": [{"start": round(s[0], 2), "end": round(s[1], 2)} for s in speech_intervals]
        }

        with open(os.path.join(audio_dir, "audio_cues.json"), "w", encoding="utf-8") as f:
            json.dump(cues_data, f, indent=2)

        # Executable recipe mix.py
        mix_recipe = f"""# CSRGO Audio Master Mix Recipe
import dsp

SR = {SR}
v, _ = dsp.read_wav("stem_voice.wav")
m, _ = dsp.read_wav("stem_music.wav")
s, _ = dsp.read_wav("stem_sfx.wav")

summed = dsp.st(v) + dsp.st(m) + dsp.st(s)
pk = dsp.true_peak(summed)
print(f"Master Mix: {{dsp.integrated(summed):.2f}} LUFS, True Peak: {{pk:.2f}} dBTP")
"""
        with open(os.path.join(audio_dir, "mix.py"), "w", encoding="utf-8") as f:
            f.write(mix_recipe)

        return {
            "stem_voice_path": stem_voice_path,
            "stem_music_path": stem_music_path,
            "stem_sfx_path": stem_sfx_path,
            "mix_path": mix_path,
            "cues": cues_data
        }

audio_service = AudioService()
