#!/usr/bin/env python3
"""
Setup script for LisPendens Agent System

This script helps set up the environment and dependencies for the agent system.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description=""):
    """Run a shell command and handle errors"""
    print(f"🔧 {description or command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"   {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(f"   {e.stderr.strip()}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} OK")
    return True

def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing Python dependencies...")
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    return run_command(
        f"{sys.executable} -m pip install -r {requirements_file}",
        "Installing requirements..."
    )

def install_playwright():
    """Install Playwright browsers"""
    print("🎭 Installing Playwright browsers...")
    
    commands = [
        f"{sys.executable} -m playwright install",
        f"{sys.executable} -m playwright install-deps"
    ]
    
    for cmd in commands:
        if not run_command(cmd, f"Running: {cmd}"):
            print("⚠️  Playwright installation failed, but system may still work")
            return False
    
    return True

def check_redis():
    """Check if Redis is available"""
    print("📦 Checking Redis availability...")
    
    try:
        import redis
        # Try to connect to default Redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1)
        r.ping()
        print("✅ Redis is available and responding")
        return True
    except ImportError:
        print("⚠️  Redis Python client not installed (will use memory cache)")
        return False
    except Exception as e:
        print(f"⚠️  Redis server not accessible: {e} (will use memory cache)")
        return False

def setup_environment():
    """Set up environment variables"""
    print("🔧 Setting up environment...")
    
    env_file = Path(__file__).parent / ".env"
    env_content = """# LisPendens Agent Environment Variables

# Redis Configuration (optional - will use memory cache if not available)
# REDIS_URL=redis://localhost:6379/0

# User ID for scraping (inherited from LpH.py system)
USER_ID=agent_system

# Logging Level
LOG_LEVEL=INFO
"""
    
    if not env_file.exists():
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"✅ Created environment file: {env_file}")
    else:
        print(f"⚡ Environment file already exists: {env_file}")
    
    return True

def run_tests():
    """Run the test suite"""
    print("🧪 Running test suite...")
    
    test_file = Path(__file__).parent / "test_agent.py"
    if not test_file.exists():
        print("❌ Test file not found")
        return False
    
    return run_command(
        f"{sys.executable} {test_file}",
        "Running tests..."
    )

def main():
    """Main setup function"""
    print("🚀 LisPendens Agent System Setup")
    print("=" * 50)
    
    steps = [
        ("Python Version", check_python_version),
        ("Dependencies", install_dependencies),
        ("Playwright", install_playwright),
        ("Redis Check", check_redis),
        ("Environment", setup_environment),
        ("Tests", run_tests)
    ]
    
    results = {}
    
    for step_name, step_func in steps:
        print(f"\n📋 Step: {step_name}")
        try:
            success = step_func()
            results[step_name] = success
            if success:
                print(f"✅ {step_name} completed successfully")
            else:
                print(f"⚠️  {step_name} completed with warnings")
        except Exception as e:
            print(f"❌ {step_name} failed: {e}")
            results[step_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SETUP SUMMARY")
    print("=" * 50)
    
    for step_name, success in results.items():
        status = "✅ OK" if success else "⚠️  WARN"
        print(f"  {step_name:<20} {status}")
    
    critical_steps = ["Python Version", "Dependencies"]
    critical_passed = all(results.get(step, False) for step in critical_steps)
    
    if critical_passed:
        print("\n🎉 Setup completed! Critical components are working.")
        print("\n📚 Next steps:")
        print("   1. Review the README.md for usage examples")
        print("   2. Configure environment variables in .env if needed")
        print("   3. Test the system: python agent_core.py --help")
        print("   4. Run integration tests: python test_agent.py")
        return 0
    else:
        print("\n❌ Setup failed. Please resolve critical issues and try again.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 