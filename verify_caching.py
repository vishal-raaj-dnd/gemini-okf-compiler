import os
import sys
import subprocess
import time

def main():
    print("=========================================")
    print("Testing Caching / Incremental Compilation")
    print("=========================================\n")
    
    # 1. Create a temporary test folder and files
    os.makedirs("test_cache_run/docs", exist_ok=True)
    
    file1_path = "test_cache_run/docs/doc_a.md"
    file2_path = "test_cache_run/docs/doc_b.md"
    
    # Write initial content
    with open(file1_path, "w", encoding="utf-8") as f:
        f.write("# Document A\n\n## Section A\nThis is the first document section.\n")
        
    with open(file2_path, "w", encoding="utf-8") as f:
        f.write("# Document B\n\n## Section B\nThis is the second document section. Refers to Section A.\n")
        
    # 2. Run Compiler - First Run (should compile both fresh)
    print(">>> RUN 1: Compiling both documents fresh...")
    cmd = [sys.executable, "main.py", "-i", "test_cache_run/docs", "-o", "test_cache_run/output"]
    subprocess.check_call(cmd)
    
    # Check if manifest.json exists
    manifest_path = "test_cache_run/output/manifest.json"
    if os.path.exists(manifest_path):
        print(f"\n[+] Manifest file created successfully at: {manifest_path}")
    else:
        print("[-] Error: Manifest file was not created!")
        sys.exit(1)
        
    # 3. Modify Document B, keep Document A unchanged
    print("\nModifying Document B, keeping Document A unchanged...")
    time.sleep(1) # Ensure timestamps or file locks clear
    with open(file2_path, "w", encoding="utf-8") as f:
        f.write("# Document B\n\n## Section B\nThis is the UPDATED second document section.\n")
        
    # 4. Run Compiler - Second Run (should load doc_a.md from cache, and compile doc_b.md fresh!)
    print("\n>>> RUN 2: Running compiler again...")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = p.communicate()
    print(stdout)
    
    # 5. Verify caching logs in stdout
    if "doc_a.md" in stdout and "Cached" in stdout:
        print("[+] Success: Document A was loaded from cache!")
    else:
        print("[-] Error: Document A was NOT loaded from cache!")
        sys.exit(1)
        
    if "doc_b.md" in stdout and "Fresh" in stdout:
        print("[+] Success: Modified Document B was processed fresh!")
    else:
        print("[-] Error: Document B was NOT processed fresh!")
        sys.exit(1)
        
    # 6. Check Mermaid Graph in index.md
    index_path = "test_cache_run/output/index.md"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()
        print("\nVerifying Mermaid Graph in index.md:")
        if "```mermaid" in index_content and "graph TD" in index_content:
            print("[+] Success: index.md contains the Mermaid graph!")
            # Print the graph block
            lines = index_content.splitlines()
            in_mermaid = False
            for line in lines:
                if line.startswith("```mermaid"):
                    in_mermaid = True
                if in_mermaid:
                    print(line)
                if in_mermaid and line.startswith("```") and len(line) == 3:
                    break
        else:
            print("[-] Error: index.md does NOT contain the Mermaid graph!")
            sys.exit(1)
            
    print("\n[SUCCESS] All caching and graph generation tests passed successfully!")

if __name__ == "__main__":
    main()
