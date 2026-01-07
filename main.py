import sys
import json

sys.path.append("src")

from src.components.services.dial_interaction.dial_interaction import dial_start

def main():    
    dial_start()

if __name__ == '__main__':
    main()
