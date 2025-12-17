"""
RCL Syntax Verification Script
Checks Python syntax without importing database dependencies
"""
import ast
import sys
from pathlib import Path

def check_syntax(filepath):
    """Check Python syntax of a file"""
    try:
        with open(filepath, 'r') as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, str(e)

def verify_rcl_files():
    """Verify all RCL-related files"""
    base_path = Path(__file__).parent
    
    files_to_check = [
        base_path / "core" / "reality_check_layer.py",
        base_path / "core" / "monte_carlo_engine.py",
        base_path / "db" / "schemas" / "sim_audit.py",
        base_path / "scripts" / "init_rcl.py",
        base_path / "scripts" / "seed_league_stats.py",
        base_path / "test_rcl.py",
    ]
    
    print("🔍 RCL Syntax Verification")
    print("=" * 60)
    
    all_ok = True
    for filepath in files_to_check:
        if not filepath.exists():
            print(f"⚠️  {filepath.name}: File not found")
            all_ok = False
            continue
        
        ok, error = check_syntax(filepath)
        if ok:
            print(f"✅ {filepath.name}: Syntax OK")
        else:
            print(f"❌ {filepath.name}: Syntax Error")
            print(f"   {error}")
            all_ok = False
    
    print("=" * 60)
    
    if all_ok:
        print("✅ All RCL files have valid Python syntax!")
        return 0
    else:
        print("❌ Some files have syntax errors")
        return 1

if __name__ == "__main__":
    sys.exit(verify_rcl_files())
