"""
🧠 NEXT LEVEL BRAIN — EXE Builder
Run this script to create a portable .exe file

Usage:  python build_exe.py
Output: dist/NEXT_LEVEL_BRAIN.exe
"""

import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

def main():
    print("=" * 60)
    print("🧠 NEXT LEVEL BRAIN — EXE Builder")
    print("=" * 60)
    print()

    # 1. Check PyInstaller
    print("📦 Checking PyInstaller...")
    try:
        import PyInstaller
        print(f"   ✅ PyInstaller {PyInstaller.__version__} installed")
    except ImportError:
        print("   ⚠️ PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"])
        print("   ✅ PyInstaller installed")

    # 2. Build command
    print()
    print("🔨 Building EXE... (ye 2-5 minutes le sakta hai)")
    print()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",                 # One directory (faster, more reliable)
        "--windowed",               # No console window (GUI app)
        "--name", "NEXT_LEVEL_BRAIN",
        "--add-data", f"config.yaml;.",         # Include config
        "--hidden-import", "customtkinter",
        "--hidden-import", "yaml",
        "--hidden-import", "MetaTrader5",
        "--hidden-import", "pandas",
        "--hidden-import", "numpy",
        "--hidden-import", "loguru",
        "--hidden-import", "dotenv",
        "--collect-all", "customtkinter",
        "--exclude-module", "torch",        # Exclude torch (not needed, can cause crashes)
        "--exclude-module", "tensorboard",
        "--exclude-module", "matplotlib",   # Not needed if only using plotly/static
        "--exclude-module", "ipython",
        "--noconfirm",              # Overwrite without asking
        "--clean",                  # Clean build
        "brain_app.py",
    ]

    # Add icon if exists
    icon = PROJECT_ROOT / "brain.ico"
    if icon.exists():
        cmd.extend(["--icon", str(icon)])
        print(f"   🎨 Icon: {icon}")

    print(f"   📁 Source: brain_app.py")
    print(f"   📁 Output: dist/NEXT_LEVEL_BRAIN/")
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode == 0:
        print()
        print("=" * 60)
        print("✅ BUILD SUCCESSFUL!")
        print("=" * 60)
        print()
        print(f"📁 EXE Location: {PROJECT_ROOT / 'dist' / 'NEXT_LEVEL_BRAIN'}")
        print()
        print("📋 Distribution Instructions:")
        print("   1. 'dist/NEXT_LEVEL_BRAIN/' folder ko ZIP karo")
        print("   2. ZIP file bhejo recipient ko")
        print("   3. Recipient extract karega aur NEXT_LEVEL_BRAIN.exe chalayega")
        print()
        print("⚠️ Requirements for recipient:")
        print("   - MetaTrader 5 installed hona chahiye")
        print("   - config.yaml aur .env files dist folder mein copy karein")
        print()

        # Copy config files to dist
        dist_dir = PROJECT_ROOT / "dist" / "NEXT_LEVEL_BRAIN"
        if dist_dir.exists():
            import shutil
            trading_files = [
                "config.yaml", ".env", "backtesting.py", "live_trading.py",
                "live_dashboard.py", "run_market_intelligence.py", "ict_concept_auditor.py",
                "debug_mt5.py", "diagnose_mt5.py", "computer_vision_analyzer.py",
                "final_verdict_system.py", "ict_evaluator.py", "ict_feature_engineer.py",
                "performance_evaluator.py"
            ]
            for f in trading_files:
                src = PROJECT_ROOT / f
                dst = dist_dir / f
                if src.exists():
                    shutil.copy2(src, dst)
                    print(f"   📋 Copied {f} to dist/")

            # Create required dirs
            for d in ["logs", "models", "backtest_results", "charts"]:
                (dist_dir / d).mkdir(exist_ok=True)

            print()
            print(f"🎉 Ready! Run: {dist_dir / 'NEXT_LEVEL_BRAIN.exe'}")
    else:
        print()
        print("❌ Build failed! Check errors above.")
        print("   Try: pip install pyinstaller --upgrade")

if __name__ == "__main__":
    main()
