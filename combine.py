import os

output_file = "combined_code.txt"
# Folders we don't want to include
ignore_dirs = {".git", "__pycache__", "venv", ".venv", "env"}
# File types to grab (add or remove as needed)
include_exts = {".py", ".json", ".md", ".csv"}

with open(output_file, "w", encoding="utf-8") as outfile:
    for root, dirs, files in os.walk("."):
        # Tell os.walk to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if any(file.endswith(ext) for ext in include_exts):
                # Don't accidentally include the output file or the script itself
                if file in [output_file, "combine.py"]:
                    continue

                filepath = os.path.join(root, file)

                # Write a clear header for each file
                outfile.write(f"\n{'=' * 50}\n")
                outfile.write(f"### {filepath} ###\n")
                outfile.write(f"{'=' * 50}\n\n")

                try:
                    with open(filepath, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read() + "\n")
                except Exception as e:
                    outfile.write(f"[Error reading file: {e}]\n")

print(f"Done! All your code is now neatly packed inside '{output_file}'")