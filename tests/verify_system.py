#!/usr/bin/env python3
"""Quick verification that all modules import successfully."""

import sys
import os

# Add parent directory to path so we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def verify_imports():
    """Test that all core modules can be imported."""
    print("\n🔍 Verifying module imports...")
    
    tests = [
        ("infra.config", "ConfigManager"),
        ("infra.input_validator", "InputValidator"),
        ("infra.api_security", "APIKeyValidator"),
        ("infra.session_store", "MemorySessionStore"),
        ("infra.metrics", "MetricsCollector"),
        ("infra.token_usage_tracker", "TokenUsageTracker"),
        ("infra.diagnostic_detector", "DiagnosticDetector"),
        ("infra.request_logging", "RequestLoggingMiddleware"),
    ]
    
    failed = []
    for module_name, class_name in tests:
        try:
            # Use importlib for proper dotted module importing
            parts = module_name.split('.')
            module = __import__(module_name, fromlist=[parts[-1]])
            cls = getattr(module, class_name, None)
            if cls:
                print(f"✅ {module_name}.{class_name}")
            else:
                print(f"⚠️  {module_name} found but no {class_name}")
                failed.append(module_name)
        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            failed.append(module_name)
        except Exception as e:
            print(f"❌ {module_name}: Unexpected error: {e}")
            failed.append(module_name)
    
    print()
    if not failed:
        print("✅ All modules verified successfully!")
        return 0
    else:
        print(f"❌ Failed modules: {', '.join(failed)}")
        return 1

if __name__ == "__main__":
    sys.exit(verify_imports())
