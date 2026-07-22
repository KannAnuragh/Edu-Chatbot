import subprocess

try:
    result = subprocess.run(["docker", "compose", "logs", "--tail", "20", "backend"], capture_output=True, text=True, cwd="d:\\project\\trogon\\admin chatbot")
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
except Exception as e:
    print(f"Error: {e}")
