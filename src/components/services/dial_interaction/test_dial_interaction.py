
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

from src.components.services.dial_interaction.dial_interaction import get_length, parse_buffer, format_visual_buffer, OBJECTS, INTERACTIONS, SINGLE_COMMANDS

def test_get_length():
    print("Testing get_length...")
    # Shortcuts
    assert get_length("9") == 1 # Prefix of 98, 95
    assert get_length("98") == 0 # Complete
    assert get_length("25") == 2 # Needs 2 more for payload
    assert get_length("2501") == 0 # Complete
    
    # Dynamic
    assert get_length("8") == 2 # Attr needs 2
    assert get_length("801") == 1 # Needs more digits to form a phrase or continue
    assert get_length("8012") == 1 # Attr + Add, needs next identifier (5 or 8)
    assert get_length("80125") == 2 # 801 (attr) 2 (add) 5 (action) -> needs 2 more for payload
    assert get_length("8012501") == 0 # Complete

    print("get_length passed!")

def test_parse_buffer():
    print("Testing parse_buffer...")
    # Single command
    phrase, payloads, is_single = parse_buffer("98")
    assert phrase == "list_attributes"
    assert payloads == []
    assert is_single == True

    phrase, payloads, is_single = parse_buffer("2501")
    assert phrase == "create_action"
    assert payloads == ["01"]
    assert is_single == True

    # Cascade
    phrase, payloads, is_single = parse_buffer("8012502")
    assert phrase == "attr add action"
    assert payloads == ["01", "02"]
    assert is_single == False

    print("parse_buffer passed!")

def test_format_visual_buffer():
    print("Testing format_visual_buffer...")
    # This function returns ANSI colored strings, so we check content
    res = format_visual_buffer("8012502")
    assert "801 - 2 - 502" in res

    res = format_visual_buffer("2501")
    assert "25 - 01" in res

    print("format_visual_buffer passed!")

if __name__ == "__main__":
    try:
        test_get_length()
        test_parse_buffer()
        test_format_visual_buffer()
        print("\nALL CORE TESTS PASSED!")
    except AssertionError as e:
        print(f"\nTEST FAILED!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
