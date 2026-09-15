import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_production_settings_pass_deploy_checks():
    env = {
        **os.environ,
        "DEBUG": "False",
        "SECRET_KEY": secrets.token_urlsafe(64),
        "ALLOWED_HOSTS": "prom-products.kz",
        "CSRF_TRUSTED_ORIGINS": "https://prom-products.kz",
        "SITE_URL": "https://prom-products.kz",
        "ADMIN_URL": "panel-test/",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_deploy_files_exist_with_lf_endings():
    for name in ["Dockerfile", ".dockerignore", "deploy/entrypoint.sh", "deploy/backup.sh",
                 "deploy/Caddyfile.example", "deploy/DEPLOY.md"]:
        path = ROOT / name
        assert path.exists(), name
        if name.endswith(".sh"):
            assert b"\r\n" not in path.read_bytes(), f"{name} must use LF line endings"


def test_compose_binds_web_to_localhost_only():
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:${WEB_PORT:-8001}:8000"' in compose
    assert "5432:5432" not in compose
