import sys
import subprocess
import os
from pathlib import Path

def check_venv():
    """Check if in virtual environment"""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def create_venv():
    """Create virtual environment"""
    venv_path = Path("venv")
    print(f"Creating virtual environment: {venv_path.absolute()}")
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True, capture_output=False)
        print("✓ Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create virtual environment: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def install_dependencies():
    """Install dependencies"""
    requirements = Path("requirements.txt")
    if not requirements.exists():
        print("✗ requirements.txt does not exist")
        return False
    
    print("Installing dependencies...")
    print("This may take a while, please wait...")
    
    if os.name == 'nt':
        pip_path = Path("venv/Scripts/pip.exe")
    else:
        pip_path = Path("venv/bin/pip")
    
    if not pip_path.exists():
        print("✗ pip does not exist, please check virtual environment")
        return False
    
    try:
        # Use --no-cache-dir to avoid cache issues
        # Use -i to use pip mirror if needed
        result = subprocess.run(
            [str(pip_path), "install", "-r", "requirements.txt", "--no-cache-dir"],
            check=False,
            capture_output=False,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            print("✓ Dependencies installed successfully")
            return True
        else:
            print("✗ Some packages failed to install")
            print("Trying alternative installation method...")
            
            # Try installing one by one
            requirements_file = Path("requirements.txt")
            with open(requirements_file, 'r', encoding='utf-8') as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            for package in packages:
                print(f"Installing {package}...")
                result = subprocess.run(
                    [str(pip_path), "install", package, "--no-cache-dir"],
                    check=False,
                    capture_output=False
                )
                if result.returncode != 0:
                    print(f"✗ Failed to install {package}")
            
            print("✓ Installation completed (some packages may have failed)")
            return True
            
    except subprocess.TimeoutExpired:
        print("✗ Installation timeout, please check your network connection")
        return False
    except Exception as e:
        print(f"✗ Installation error: {e}")
        return False

def main():
    print("=" * 50)
    print("Starrain-BOT Setup")
    print("=" * 50)
    print()
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print(f"✗ Python 3.8+ required, current version: {sys.version}")
        print("Please upgrade Python to 3.8 or higher")
        return
    
    print(f"✓ Python version: {sys.version.split()[0]}")
    print()
    
    if check_venv():
        print("✓ Already in virtual environment")
        
        if not Path("venv").exists():
            install_dependencies()
    else:
        if Path("venv").exists():
            print("✓ Virtual environment detected")
            # Install dependencies if needed
            install_dependencies()
        else:
            # Create virtual environment
            if create_venv():
                install_dependencies()
            else:
                print("✗ Setup failed")
                return
    
    print()
    print("=" * 50)
    print("Setup Complete!")
    print("Run the bot using the startup script:")
    print("Windows: start.bat")
    print("Linux/Mac: bash start.sh")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
