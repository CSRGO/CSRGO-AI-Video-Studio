import os
import re
import shutil
import subprocess
from typing import Dict, Any, Optional
from backend.services.ollama_service import ollama_service
from backend.core.config import settings

class GitHubService:
    def __init__(self):
        pass

    def validate_url(self, url: str) -> bool:
        pattern = r'^https?://github\.com/[\w\.-]+/[\w\.-]+/?$'
        return bool(re.match(pattern, url.strip()))

    def analyze_repository(self, repo_url: str, work_dir: str) -> Dict[str, Any]:
        """
        Clones repository with --depth 1, reads README and code manifests,
        and uses qwen2.5-coder:3b to extract real architecture and facts.
        """
        if not self.validate_url(repo_url):
            raise ValueError(f"Invalid GitHub repository URL: {repo_url}")

        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        clone_dest = os.path.join(work_dir, "repo_clone")
        os.makedirs(clone_dest, exist_ok=True)

        # Remove previous clone if exists
        target_clone_dir = os.path.join(clone_dest, repo_name)
        if os.path.exists(target_clone_dir):
            shutil.rmtree(target_clone_dir, ignore_errors=True)

        try:
            # Safe shallow clone using argument array
            cmd = ["git", "clone", "--depth", "1", repo_url, target_clone_dir]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode != 0:
                raise RuntimeError(f"Git clone failed: {res.stderr}")

            # Inspect directory structure
            tree_summary = []
            readme_content = ""
            manifest_summary = ""

            for root, dirs, files in os.walk(target_clone_dir):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "__pycache__", "dist", "build")]
                rel_root = os.path.relpath(root, target_clone_dir)
                for f in files:
                    rel_file = os.path.join(rel_root, f) if rel_root != "." else f
                    tree_summary.append(rel_file)

                    if f.lower() == "readme.md" and not readme_content:
                        try:
                            with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as r_f:
                                readme_content = r_f.read()[:4000]
                        except Exception:
                            pass

                    if f in ("package.json", "requirements.txt", "Cargo.toml", "go.mod", "pyproject.toml"):
                        try:
                            with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as m_f:
                                manifest_summary += f"\n--- {f} ---\n" + m_f.read()[:1000]
                        except Exception:
                            pass

            tree_str = "\n".join(tree_summary[:35])

            # Analyze using Qwen2.5-Coder:3B
            system_prompt = (
                "You are an expert software architect and technical educator. "
                "You analyze real GitHub projects and extract verified factual summaries. "
                "Never hallucinate or invent features not present in the code or README."
            )

            prompt = f"""
Analyze this GitHub project ({repo_name}):

REPOSITORY TREE (Sample):
{tree_str}

PROJECT MANIFESTS:
{manifest_summary}

README EXCERPT:
{readme_content}

TASK:
Provide a concise, factual summary formatted as:
1. WHAT IT IS: (One clear sentence explaining the project's purpose)
2. KEY FEATURES: (3-4 bullet points based strictly on the README and code)
3. TECH STACK: (Languages, frameworks, and core libraries)
4. HOW IT WORKS: (Brief 2-sentence architecture explanation)
5. TARGET AUDIENCE: (Who should care about this project)
"""

            analysis = ollama_service.generate(
                prompt=prompt,
                model=settings.ollama_code_model, # qwen2.5-coder:3b
                system=system_prompt, purpose="coding"
            )

            return {
                "repository": repo_name,
                "url": repo_url,
                "analysis": analysis,
                "file_count": len(tree_summary),
                "readme_found": bool(readme_content),
                "files_sample": tree_summary[:15]
            }

        finally:
            # Clean up cloned files to conserve disk space
            if os.path.exists(target_clone_dir):
                shutil.rmtree(target_clone_dir, ignore_errors=True)

github_service = GitHubService()

