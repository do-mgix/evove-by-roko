
import os
import sys

# Mocking the environment for testing
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.components.services.journal_service import JournalService

def test_journal_service():
    js = JournalService()
    
    # Test 1: Adding logs
    print("Testing 1: Adding logs...")
    js.add_log("First log entry")
    js.add_log("  Second log entry with spaces  ")
    js.add_log("") # Should be ignored
    
    assert len(js.buffer) == 2
    assert js.buffer[0] == "First log entry"
    assert js.buffer[1] == "Second log entry with spaces"
    print("Test 1 passed.")

    # Test 2: Sync to cloud (Mocking filesystem and subprocess)
    print("\nTesting 2: Sync to cloud (dry run logic)...")
    # We won't actually call git push in this test to avoid side effects
    # But we can check if it tries to write to the right file
    
    test_journal_dir = "/tmp/evove_test_journal"
    os.makedirs(test_journal_dir, exist_ok=True)
    js.journal_dir = test_journal_dir
    js.journal_path = os.path.join(test_journal_dir, "evove26")
    
    # We will temporarily monkeypatch subprocess.run to avoid real git calls
    import subprocess
    original_run = subprocess.run
    
    calls = []
    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        class MockResult:
            stdout = "success"
            stderr = ""
        return MockResult()
    
    subprocess.run = mock_run
    
    result = js.sync_to_cloud()
    print(f"Sync result: {result}")
    
    assert os.path.exists(js.journal_path)
    with open(js.journal_path, "r") as f:
        content = f.read()
        assert "First log entry" in content
        assert "Second log entry with spaces" in content
    
    assert len(calls) == 3
    assert calls[0] == ["git", "add", "evove26"]
    assert calls[1][0] == "git" and calls[1][1] == "commit"
    assert calls[2] == ["git", "push"]
    
    assert len(js.buffer) == 0 # Buffer should be cleared
    
    subprocess.run = original_run
    print("Test 2 passed.")

if __name__ == "__main__":
    try:
        test_journal_service()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nTests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
