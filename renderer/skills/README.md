# Production skill sources

Remotion guidance is copied from the official remotion-dev/skills repository, commit `7e541aa4d7361dfaca0780a565a47307eb7bdfbb`, corresponding to Remotion 4.0.543. Original source: https://github.com/remotion-dev/skills/tree/7e541aa4d7361dfaca0780a565a47307eb7bdfbb/skills/remotion-best-practices . Apply the upstream Remotion license: https://github.com/remotion-dev/remotion/blob/main/LICENSE.md . The application's prompt loader combines the router, markup and timing references; repository-relative links in the original documents point to their upstream references.

Hyperframes guidance is read from the pinned `hyperframes@0.9.52` package's `dist/skills/hyperframes` directory (Apache-2.0), including its SKILL.md and deterministic runtime contract. It is installed with `npm ci` under renderer, not fetched during a production. The selected Lemo style remains the visual authority; these skills define the implementation/timeline contracts.
