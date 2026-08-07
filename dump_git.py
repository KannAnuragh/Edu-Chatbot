import subprocess
with open("git_diff.txt", "w", encoding="utf-8") as f:
    subprocess.run(["git", "log", "-n", "15", "-p"], stdout=f, cwd=r"d:\project\trogon\admin chatbot")
