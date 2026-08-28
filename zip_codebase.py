import os
import zipfile

# ONLY allow safe text/code files. Block .env so your passwords don't upload!
ALLOWED_EXTS = {'.py', '.md', '.bat', '.json', '.txt', '.toml', '.css'}

# Block ALL common environment folders, backups, and Git
EXCLUDE_DIRS = {
    'venv', 'env', '.venv', '.env', 'virtualenv',
    '.git', '__pycache__', 'uploads', 'backups',
    'postgres_data', '.pytest_cache', 'node_modules'
}


def zip_codebase(output_zip="mes_codebase_safe.zip"):
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                filepath = os.path.join(root, file)

                # Exclude the zip itself, exclude .env files, limit to < 2MB
                if ext in ALLOWED_EXTS and file != output_zip and not file.endswith('.env'):
                    if os.path.getsize(filepath) < 2 * 1024 * 1024:
                        zipf.write(filepath)
                        print(f"📦 Packed: {filepath}")

    size_mb = os.path.getsize(output_zip) / (1024 * 1024)
    print(f"\n✅ Done! Created '{output_zip}' ({size_mb:.2f} MB)")


if __name__ == "__main__":
    zip_codebase()