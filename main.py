import sys
import json

sys.path.append("src")

from src.components.services.system import dial_start 

def main():    
   dial_start() 

if __name__ == '__main__':
    main()
