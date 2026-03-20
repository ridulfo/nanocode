#!/usr/bin/env python3
"""Python rewrite of nanocode-llamacpp shell script"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="nanocode-llamacpp - specialized script for llama.cpp provider",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "work_dir",
        nargs="?",
        default=".",
        help="Working directory to mount as /workspace"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Rebuild the container image"
    )
    
    args = parser.parse_args()
    
    # Set defaults
    image_name = "nanocode:latest"
    work_dir = args.work_dir
    rebuild = args.clean
    
    # Rebuild container if --clean flag is set
    if rebuild:
        print("Rebuilding nanocode container image...")
        script_dir = Path(__file__).parent
        subprocess.run([
            "podman", "build", "-t", image_name, 
            "-f", str(script_dir / "Containerfile"),
            str(script_dir)
        ], check=True)
    
    print("Starting nanocode with llama.cpp provider...")
    
    # Build podman command
    cmd = [
        "podman", "run", "-it", "--rm",
        "--network", "host",
        "-v", f"{work_dir}:/workspace:z",
        "-e", f"PROVIDER=llamacpp",
        "-e", f"LLAMACPP_MODEL={os.environ.get('LLAMACPP_MODEL', 'default')}",
        "-e", f"LLAMACPP_URL={os.environ.get('LLAMACPP_URL', 'http://localhost:8079')}",
        "-e", f"GIT_USER_NAME={os.environ.get('GIT_USER_NAME', 'Nanocode Agent')}",
        "-e", f"GIT_USER_EMAIL={os.environ.get('GIT_USER_EMAIL', 'nanocode@local')}",
        image_name
    ]
    
    # Execute the command
    os.execvp("podman", cmd)

if __name__ == "__main__":
    main()
