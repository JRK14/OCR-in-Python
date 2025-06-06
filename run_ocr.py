#!/usr/bin/env python3
"""
OCR Application Launcher
------------------------
This script launches the OCR application and handles any initialization requirements.
"""

import os
import sys
import subprocess

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import PIL
        import pytesseract
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install the required packages using:")
        print("pip install -r requirements.txt")
        return False

def check_tesseract():
    """Check if Tesseract OCR is installed on the system"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        print("Tesseract OCR not found or not properly configured.")
        print("Please install Tesseract OCR:")
        print("- MacOS: brew install tesseract")
        print("- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        print("- Linux: sudo apt-get install tesseract-ocr")
        return False

def main():
    """Main entry point for the application launcher"""
    if not check_dependencies():
        return 1
    
    if not check_tesseract():
        print("\nWARNING: The application may not work correctly without Tesseract OCR.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            return 1
    
    # Launch the OCR application
    try:
        from ocr_app import main
        main()
    except Exception as e:
        print(f"Error launching OCR application: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 