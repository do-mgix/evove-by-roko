
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from components.services.dial_interaction.dial_interaction import get_length

def test_get_length():
    print(f"Testing get_length('9'): {get_length('9')}")
    print(f"Testing get_length('98'): {get_length('98')}")
    print(f"Testing get_length('8'): {get_length('8')}")
    print(f"Testing get_length('2'): {get_length('2')}")
    
    assert get_length('9') != 0, "get_length('9') should not be 0!"
    assert get_length('98') == 0, "get_length('98') should be 0!"

if __name__ == "__main__":
    try:
        test_get_length()
        print("Tests passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
