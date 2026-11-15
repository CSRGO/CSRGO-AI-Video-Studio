# Vendored yt-script skill

Source: https://github.com/jakeschincariol/youtube-agent-skill , pinned commit `a2feb2104981a375ffd4f87ee04f4f5344ac43c6` (MIT, included).

The app uses the actual `yt-script` instructions, 21 hook formulas and Python scoring function. The upstream-tool patches are explicit UTF-8 file reading for Windows and closing the formula file after reading. Other channel-management skills are not installed or invoked.

The automated studio uses its configured narration voice and a beginner-friendly editorial profile, rather than claiming to have learned the creator's personal voice. The user's existing automatic-generation request controls workflow pauses; no video is uploaded or published to YouTube. Hook scores are English writing heuristics, not view/retention predictions. The app scores the reviewed opening and any optional model-proposed alternatives; candidates never replace the factual narration without editorial review.
