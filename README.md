# OCR-in-Python
A desktop application for extracting text from images using Optical Character Recognition. Built with Python, Tkinter, and Tesseract OCR.

A  Python application for Optical Character Recognition (OCR) that allows users to upload and scan images to extract text.

## Features

- Upload image files (.jpg, .jpeg, .png)
- Preview uploaded images
- Extract text from images using OCR
- Image preprocessing options to improve OCR accuracy
- Save extracted text to a file
- Simple and intuitive interface

## Prerequisites

- Python 3.6 or higher
- Tesseract OCR engine (must be installed separately)

## Installation

1. **IMPORTANT**: Install Tesseract OCR on your system:
   - For MacOS: 
     ```
     brew install tesseract
     ```
     If you don't have Homebrew installed, visit [https://brew.sh/](https://brew.sh/) first.
   
   - For Windows: Download and install from [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
   
   - For Linux: 
     ```
     sudo apt-get install tesseract-ocr
     ```

   **Note**: The OCR functionality will not work without Tesseract installed.

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Make sure the path to Tesseract executable is properly set:
   - For Windows, you might need to add the following line to the code:
     ```python
     pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
     ```

## Usage

1. Run the application using the launcher script:
   ```
   python run_ocr.py
   ```
   
   The launcher will check if all dependencies are properly installed before starting the application.

   Alternatively, you can run the application directly:
   ```
   python ocr_app.py
   ```

2. Use the "Upload File" button (red box) to select an image file (.jpg, .jpeg, or .png).

3. The selected image will be displayed in the preview area (blue box).

4. Click the "Scan Image" button (black box) to extract text from the image.
   - You can select a preprocessing option (None, Enhance Contrast, Sharpen, or Grayscale) to improve OCR results for different types of images.

5. The extracted text will appear in the text box at the bottom of the application.

6. Click the "Save Text" button to save the extracted text to a file.

## Layout

- Red region: File upload functionality
- Black region: Scan functionality
- Blue region: Image preview area 
