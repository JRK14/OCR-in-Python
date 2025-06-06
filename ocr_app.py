import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageFilter
import pytesseract
from tkinter import ttk
import platform
import subprocess
import numpy as np
import cv2
import threading
import time
import re
import concurrent.futures

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR Application")
        self.root.geometry("1200x800")
        self.root.configure(bg="#f5f5f5")
        
        # Set minimum window size to prevent shrinking
        self.root.minsize(1000, 700)
        
        # Configure tesseract path based on OS
        self.configure_tesseract()
        
        # Check if tesseract is installed and configured properly
        self.tesseract_installed, self.tesseract_message = self.check_tesseract_installed()
        if not self.tesseract_installed:
            messagebox.showwarning(
                "Tesseract Configuration Issue", 
                f"There was an issue with Tesseract OCR configuration:\n\n{self.tesseract_message}\n\n"
                "The OCR functionality may not work properly without Tesseract correctly configured.\n\n"
                "Recommended fixes:\n"
                "- MacOS: brew install tesseract\n"
                "- Windows: Download from github.com/UB-Mannheim/tesseract/wiki\n"
                "- Linux: sudo apt-get install tesseract-ocr"
            )
        
        self.current_image = None
        self.current_image_path = None
        self.extracted_text = ""
        
        # Create main content frame to hold everything
        self.main_content = tk.Frame(root, bg="#f5f5f5")
        self.main_content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Create top section for controls and preview
        self.top_section = tk.Frame(self.main_content, bg="#f5f5f5")
        self.top_section.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create bottom section with fixed height for extracted text
        self.bottom_section = tk.Frame(self.main_content, bg="#f5f5f5", height=150)
        self.bottom_section.pack(fill=tk.X, expand=False, padx=20, pady=10, side=tk.BOTTOM)
        self.bottom_section.pack_propagate(False)  # Prevent shrinking
        
        # Title label
        self.title_label = tk.Label(self.top_section, text="File Format accepted:", font=("Arial", 18, "bold"), bg="#f5f5f5")
        self.title_label.pack(anchor=tk.W, pady=(0, 5))
        
        # File formats label
        self.formats_label = tk.Label(self.top_section, text=".jpg, .jpeg, .png", font=("Arial", 12), bg="#f5f5f5")
        self.formats_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Create two main columns
        self.left_column = tk.Frame(self.top_section, bg="#f5f5f5", width=400)
        self.left_column.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        self.right_column = tk.Frame(self.top_section, bg="#f5f5f5")
        self.right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Right panel - Preview area with title
        self.preview_title = tk.Label(self.right_column, text="Input Image Preview", font=("Arial", 14), bg="#f5f5f5")
        self.preview_title.pack(anchor=tk.N, pady=(0, 5))
        
        # Add side loading bar frame
        self.side_loading_frame = tk.Frame(self.right_column, bg="#f5f5f5", width=30)
        self.side_loading_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        # Create side loading bar (vertical progress bar)
        self.side_progress_var = tk.DoubleVar()
        self.side_progress_var.set(0)
        
        self.side_progress = ttk.Progressbar(
            self.side_loading_frame, 
            mode="determinate", 
            length=600,
            variable=self.side_progress_var,
            maximum=100,
            orient=tk.VERTICAL
        )
        self.side_progress.pack(fill=tk.Y, expand=True, padx=5, pady=10)
        
        # Create a container for the preview with fixed dimensions
        self.preview_container = tk.Frame(self.right_column, bg="white", highlightbackground="#aaaaaa", 
                                    highlightthickness=1, bd=0)
        self.preview_container.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbars for the preview canvas
        self.preview_hscroll = tk.Scrollbar(self.preview_container, orient=tk.HORIZONTAL)
        self.preview_hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.preview_vscroll = tk.Scrollbar(self.preview_container)
        self.preview_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create inner frame for the image preview with scroll capability
        self.preview_canvas = tk.Canvas(self.preview_container, bg="white", highlightthickness=0,
                                     xscrollcommand=self.preview_hscroll.set,
                                     yscrollcommand=self.preview_vscroll.set,
                                     width=600, height=400)
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Connect scrollbars to canvas
        self.preview_hscroll.config(command=self.preview_canvas.xview)
        self.preview_vscroll.config(command=self.preview_canvas.yview)
        
        # Create frame inside canvas
        self.preview_frame = tk.Frame(self.preview_canvas, bg="white")
        self.preview_frame_window = self.preview_canvas.create_window((0, 0), window=self.preview_frame, anchor="nw")
        
        # Image preview with fixed size
        self.preview_label = tk.Label(self.preview_frame, bg="white")
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Configure canvas when frame size changes
        self.preview_frame.bind("<Configure>", self._on_preview_frame_configure)
        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure)
        
        # Add processing indicator to the preview frame
        self.processing_indicator = tk.Label(self.preview_frame, text="PROCESSING IMAGE...", 
                                          font=("Arial", 24, "bold"), bg="white", fg="#FF4500",
                                          bd=2, relief=tk.RAISED)
        self.processing_indicator.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.processing_indicator.place_forget()  # Hide initially
        
        # Create hashtag loading bar frame
        self.hashtag_frame = tk.Frame(self.preview_frame, bg="white", bd=1, relief=tk.SUNKEN)
        self.hashtag_frame.place(relx=0.5, rely=0.5, width=300, height=50, anchor=tk.CENTER)
        self.hashtag_frame.place_forget()  # Hide initially
        
        # Create label for hashtag progress
        self.hashtag_label = tk.Label(self.hashtag_frame, text="", font=("Courier", 20, "bold"), 
                                   bg="white", fg="#0066CC")
        self.hashtag_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add pulsating animation flag
        self.pulsating = False
        self.hashtag_count = 0
        
        # Add status text on preview area
        self.preview_status = tk.Label(self.preview_frame, text="", font=("Arial", 12),
                                     bg="white", fg="#0066CC")
        self.preview_status.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        # Left panel - Controls
        # Upload button with icon-like appearance
        self.upload_frame = tk.Frame(self.left_column, bg="#f5f5f5", bd=0, padx=10, pady=10)
        self.upload_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.upload_btn = tk.Button(self.upload_frame, text="Open File", font=("Arial", 12),
                                  bg="#f0f0f0", relief=tk.GROOVE, borderwidth=2,
                                  padx=20, pady=10, command=self.upload_file)
        self.upload_btn.pack(fill=tk.X, padx=50)
        
        # Scan button and preprocessing options in a black-bordered frame
        self.scan_frame = tk.Frame(self.left_column, bg="white", highlightbackground="black", 
                                 highlightthickness=2, bd=0)
        self.scan_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.scan_btn = tk.Button(self.scan_frame, text="Scan Image", font=("Arial", 12),
                                bg="white", relief=tk.GROOVE, command=self.scan_image)
        self.scan_btn.pack(fill=tk.X, padx=20, pady=10)
        
        # Add preprocessing options
        self.preproc_label = tk.Label(self.scan_frame, text="Preprocessing:", font=("Arial", 11), bg="white")
        self.preproc_label.pack(anchor=tk.W, padx=20, pady=(5, 5))
        
        self.preproc_var = tk.StringVar(value="none")
        preproc_options = [
            ("None", "none"),
            ("Enhance Contrast", "contrast"),
            ("Sharpen", "sharpen"),
            ("Grayscale", "grayscale")
        ]
        
        for text, value in preproc_options:
            rb = tk.Radiobutton(self.scan_frame, text=text, value=value, 
                              variable=self.preproc_var, bg="white", font=("Arial", 10))
            rb.pack(anchor=tk.W, padx=30, pady=2)
        
        # Add AI-enhanced OCR option
        self.ai_frame = tk.Frame(self.scan_frame, bg="white")
        self.ai_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.ai_var = tk.BooleanVar(value=False)
        self.ai_cb = tk.Checkbutton(self.ai_frame, text="Use AI Enhancement for unclear images", 
                                  variable=self.ai_var, bg="white",
                                  font=("Arial", 10))
        self.ai_cb.pack(anchor=tk.W)
        
        # Add info button next to AI option
        self.info_btn = tk.Button(self.ai_frame, text="?", font=("Arial", 8), 
                                width=2, height=1, command=self.show_ai_info)
        self.info_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Add language selection
        lang_frame = tk.Frame(self.scan_frame, bg="white")
        lang_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        lang_label = tk.Label(lang_frame, text="OCR Language:", font=("Arial", 10), bg="white")
        lang_label.pack(anchor=tk.W)
        
        self.lang_var = tk.StringVar(value="eng")
        langs = [
            ("English", "eng"),
            ("English + Numbers", "eng+osd"),
        ]
        
        for text, value in langs:
            rb = tk.Radiobutton(lang_frame, text=text, value=value, 
                             variable=self.lang_var, bg="white", font=("Arial", 10))
            rb.pack(anchor=tk.W, padx=20)
        
        # Add OCR mode selection
        mode_frame = tk.Frame(self.scan_frame, bg="white")
        mode_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        mode_label = tk.Label(mode_frame, text="OCR Mode:", font=("Arial", 10), bg="white")
        mode_label.pack(anchor=tk.W)
        
        self.mode_var = tk.StringVar(value="auto")
        modes = [
            ("Auto Detect", "auto"),
            ("Text Document", "document"),
            ("Screenshot", "screenshot"),
            ("Single Line/Button", "single")
        ]
        
        for text, value in modes:
            rb = tk.Radiobutton(mode_frame, text=text, value=value, 
                             variable=self.mode_var, bg="white", font=("Arial", 10))
            rb.pack(anchor=tk.W, padx=20)
        
        # Add auto-scan option
        self.auto_scan_var = tk.BooleanVar(value=True)
        self.auto_scan_cb = tk.Checkbutton(self.left_column, text="Auto-scan on upload", 
                                         variable=self.auto_scan_var, bg="#f5f5f5",
                                         font=("Arial", 10))
        self.auto_scan_cb.pack(anchor=tk.W, pady=(10, 20))
        
        # Save button with icon-like appearance
        self.save_frame = tk.Frame(self.left_column, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        self.save_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.save_btn = tk.Button(self.save_frame, text="Save File", font=("Arial", 12),
                               bg="#f0f0f0", padx=20, pady=10, command=self.save_text)
        self.save_btn.pack(fill=tk.X, padx=50)
        
        # Add debug button to view processed image
        self.debug_frame = tk.Frame(self.left_column, bg="#f5f5f5")
        self.debug_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.view_processed_btn = tk.Button(self.debug_frame, text="View Processed Image", 
                                         font=("Arial", 11), bg="#f0f0f0", 
                                         command=self.view_processed_image)
        self.view_processed_btn.pack(fill=tk.X, padx=20, pady=5)
        self.view_processed_btn.config(state=tk.DISABLED)  # Initially disabled
        
        # Text output section in bottom section
        self.text_frame = tk.Frame(self.bottom_section, bg="#f5f5f5")
        self.text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a frame for the heading
        self.text_header_frame = tk.Frame(self.text_frame, bg="#f5f5f5")
        self.text_header_frame.pack(fill=tk.X, expand=False, pady=(0, 5))
        
        # Text label
        self.text_label = tk.Label(self.text_header_frame, text="Extracted Text:", font=("Arial", 14, "bold"), bg="#f5f5f5", fg="#0066CC")
        self.text_label.pack(side=tk.LEFT)
        
        # Create a container frame with fixed height for the text box
        self.text_container = tk.Frame(self.text_frame, bg="white", height=100)
        self.text_container.pack(fill=tk.BOTH, expand=True)
        self.text_container.pack_propagate(False)  # Prevent shrinking
        
        # Add a frame for text box with simple border
        self.text_box_frame = tk.Frame(self.text_container, bg="white", bd=1, relief=tk.SOLID, highlightthickness=0)
        self.text_box_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Add vertical scrollbar
        self.text_scrollbar_y = tk.Scrollbar(self.text_box_frame)
        self.text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add horizontal scrollbar
        self.text_scrollbar_x = tk.Scrollbar(self.text_box_frame, orient=tk.HORIZONTAL)
        self.text_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Add text box with scrollbar connections
        self.text_box = tk.Text(self.text_box_frame, wrap=tk.NONE, height=5, font=("Arial", 11), 
                             yscrollcommand=self.text_scrollbar_y.set,
                             xscrollcommand=self.text_scrollbar_x.set,
                             bg="white", fg="black", padx=10, pady=5,
                             relief=tk.FLAT, borderwidth=0)
        self.text_box.pack(fill=tk.BOTH, expand=True)
        
        # Connect scrollbars to text box
        self.text_scrollbar_y.config(command=self.text_box.yview)
        self.text_scrollbar_x.config(command=self.text_box.xview)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Hide side loading bar initially
        self.side_progress.pack_forget()

    def configure_tesseract(self):
        """Configure tesseract executable path based on OS"""
        system = platform.system()
        
        # For Windows, we often need to set the path explicitly
        if system == 'Windows':
            # Default install location, can be configured via settings later
            default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        
        # For macOS, check if it's installed via homebrew
        elif system == 'Darwin':  # macOS
            tesseract_paths = [
                '/usr/local/bin/tesseract',
                '/opt/homebrew/bin/tesseract',
                '/usr/bin/tesseract'
            ]
            
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    print(f"Using Tesseract from: {path}")
                    break
                    
            # Set TESSDATA_PREFIX environment variable if not already set
            if 'TESSDATA_PREFIX' not in os.environ:
                for prefix in ['/usr/local/share/tessdata', '/opt/homebrew/share/tessdata']:
                    if os.path.exists(prefix):
                        os.environ['TESSDATA_PREFIX'] = prefix
                        print(f"Setting TESSDATA_PREFIX to: {prefix}")
                        break
                        
        # For Linux
        elif system == 'Linux':
            # Usually installed via package manager
            if os.path.exists('/usr/bin/tesseract'):
                pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
            
            # Set TESSDATA_PREFIX environment variable if not already set
            if 'TESSDATA_PREFIX' not in os.environ and os.path.exists('/usr/share/tesseract-ocr/4.00/tessdata'):
                os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'
                
    def check_tesseract_installed(self):
        """Check if tesseract is installed and available in PATH"""
        try:
            # Try to get tesseract version
            version = pytesseract.get_tesseract_version()
            print(f"Tesseract version: {version}")
            return True, f"Tesseract version {version} detected"
        except Exception as e:
            error_message = str(e)
            print(f"Tesseract error: {error_message}")
            
            # Check if the error is related to missing data files
            if "tessdata" in error_message or "TESSDATA_PREFIX" in error_message:
                return False, "Tesseract language data files not found. Please install language data or set TESSDATA_PREFIX correctly."
            else:
                return False, f"Tesseract not properly installed or configured: {error_message}"
    
    def upload_file(self):
        filetypes = [
            ("Image files", "*.jpg *.jpeg *.png"),
        ]
        
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        
        if file_path:
            if self.validate_file(file_path):
                # Reset state for new image
                self.current_image_path = file_path
                self.current_image = None  # Clear previous image
                self.extracted_text = ""   # Clear previous text
                self.text_box.delete(1.0, tk.END)  # Clear text box
                
                # Load and display the new image
                self.display_image(file_path)
                self.status_var.set(f"File loaded: {os.path.basename(file_path)}")
                
                # Auto-scan if enabled
                if self.auto_scan_var.get():
                    self.root.after(500, self.scan_image)  # Slight delay to ensure image is loaded
            else:
                messagebox.showerror("Invalid File", "Please select a file with .jpg, .jpeg, or .png extension.")
                self.status_var.set("Error: Invalid file format")
    
    def validate_file(self, file_path):
        valid_extensions = ('.jpg', '.jpeg', '.png')
        return file_path.lower().endswith(valid_extensions)
    
    def display_image(self, image_path):
        # Open the image and resize for display
        try:
            img = Image.open(image_path)
            
            # Store the original image for OCR processing
            self.current_image = img.copy()
            
            # Get original image dimensions
            width, height = img.size
            
            # Calculate size for display - set reasonable limits for preview
            max_display_width = 580  # Slightly less than canvas width to account for padding
            max_display_height = 380  # Slightly less than canvas height to account for padding
            
            # Calculate the scaling factor to maintain aspect ratio
            scale_factor = min(max_display_width / width, max_display_height / height)
            
            # If the image is already smaller than our max dimensions, don't scale it up
            if scale_factor > 1:
                scale_factor = 1.0
                
            # Calculate new dimensions
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Resize the image
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to PhotoImage for display
            photo = ImageTk.PhotoImage(img_resized)
            
            # Update the preview label
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo  # Keep a reference
            
            # Update the canvas scrollregion
            self.preview_frame.update_idletasks()  # Ensure the frame has been laid out
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
            
            # Ensure the text area maintains its size
            if hasattr(self, 'bottom_section'):
                self.bottom_section.config(height=150)
                self.bottom_section.pack_propagate(False)
                
            # Reset scroll position to top-left
            self.preview_canvas.xview_moveto(0)
            self.preview_canvas.yview_moveto(0)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not display image: {str(e)}")
            self.status_var.set("Error displaying image")
    
    def show_ai_info(self):
        """Show information about the AI-enhanced OCR option"""
        messagebox.showinfo(
            "AI Enhancement Information",
            "AI Enhancement uses advanced image processing techniques to improve text recognition "
            "for unclear or low-quality images. This includes:\n\n"
            "• Adaptive thresholding\n"
            "• Noise reduction\n"
            "• Perspective correction\n"
            "• Advanced OCR parameters\n\n"
            "This option may take longer to process but can significantly improve results for "
            "difficult images."
        )
    
    def preprocess_image(self, image):
        """Apply advanced preprocessing to the image for optimal OCR accuracy"""
        preproc_type = self.preproc_var.get()
        ocr_mode = self.mode_var.get()
        
        # Detect image type for optimal processing
        detected_type = self._detect_image_type(image)
        self.detected_type = detected_type
        print(f"Detected image type: {detected_type}")
        
        # If auto detect mode is selected, override with the detected type
        if ocr_mode == "auto":
            ocr_mode = detected_type
            print(f"Auto-detection: Using {detected_type} processing mode")
        
        # Apply specialized processing based on detected or selected type
        if detected_type == "certificate" and self._is_likely_certificate(image):
            print("Detected certificate-like document - applying specialized processing")
            return self._enhance_certificate(image)
        elif ocr_mode == "screenshot" or (ocr_mode == "auto" and detected_type == "screenshot"):
            print("Detected screenshot - applying specialized screenshot processing")
            return self._enhance_screenshot(image)
        elif ocr_mode == "document" or (ocr_mode == "auto" and detected_type == "document"):
            print("Detected text document - applying document optimization")
            return self._enhance_document(image)
        elif ocr_mode == "single" or (ocr_mode == "auto" and detected_type == "single"):
            print("Detected single line text - applying text optimization")
            return self._enhance_single_line(image)
        
        # If no specialized handling or user explicitly chose processing type, 
        # continue with standard processing
        
        # Skip preprocessing for screenshots if not explicitly requested
        if preproc_type == "none" and not self.ai_var.get():
            # Always apply minimal noise reduction
            try:
                img_np = np.array(image)
                if len(img_np.shape) == 3:  # Color image
                    img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                    # Apply very light bilateral filter for noise reduction without losing edges
                    img_filtered = cv2.bilateralFilter(img_gray, 9, 10, 10)
                    # Convert back to PIL
                    return Image.fromarray(img_filtered)
                else:
                    return image  # Already grayscale, return as is
            except:
                return image  # If processing fails, return original
        
        # Special handling for screenshots to improve speed and accuracy
        if ocr_mode == "screenshot" and preproc_type == "none":
            # For screenshots, optimize for crisp text
            processed_img = image.copy()
            
            # Convert to numpy for advanced processing
            try:
                img_np = np.array(processed_img)
                if len(img_np.shape) == 3:  # Color image
                    # Convert to grayscale
                    img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                    
                    # Optimize contrast with CLAHE (Contrast Limited Adaptive Histogram Equalization)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    img_contrast = clahe.apply(img_gray)
                    
                    # Apply threshold to make text sharper
                    _, img_thresh = cv2.threshold(img_contrast, 150, 255, cv2.THRESH_BINARY)
                    
                    # Convert back to PIL
                    processed_img = Image.fromarray(img_thresh)
                
                # If AI enhancement is enabled, apply additional processing
                if self.ai_var.get():
                    processed_img = self.apply_ai_enhancement(processed_img)
            except:
                # If processing fails, use original
                if self.ai_var.get():
                    processed_img = self.apply_ai_enhancement(processed_img)
                
            return processed_img
        
        # Create a copy to avoid modifying the original
        processed_img = image.copy()
        
        # Convert to numpy for advanced processing
        try:
            img_np = np.array(processed_img)
            
            # Apply specific preprocessing based on selected option
            if preproc_type == "contrast":
                # Enhanced contrast processing
                if len(img_np.shape) == 3:  # Color image
                    # Convert to grayscale
                    img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    img_gray = img_np
                
                # Apply CLAHE for advanced contrast enhancement
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                img_contrast = clahe.apply(img_gray)
                
                # Denoise
                img_denoised = cv2.fastNlMeansDenoising(img_contrast, None, 10, 7, 21)
                
                # Convert back to PIL
                processed_img = Image.fromarray(img_denoised)
                
            elif preproc_type == "sharpen":
                # Advanced sharpening
                if len(img_np.shape) == 3:  # Color image
                    # Convert to grayscale
                    img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    img_gray = img_np
                
                # Apply unsharp mask for better sharpening
                gaussian = cv2.GaussianBlur(img_gray, (0, 0), 3.0)
                img_sharp = cv2.addWeighted(img_gray, 1.5, gaussian, -0.5, 0)
                
                # Enhance contrast after sharpening
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img_final = clahe.apply(img_sharp)
                
                # Convert back to PIL
                processed_img = Image.fromarray(img_final)
                
            elif preproc_type == "grayscale":
                # Optimized grayscale with adaptive threshold
                if len(img_np.shape) == 3:  # Color image
                    # Convert to grayscale
                    img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    img_gray = img_np
                
                # Apply CLAHE for better contrast
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img_contrast = clahe.apply(img_gray)
                
                # Apply adaptive threshold
                img_thresh = cv2.adaptiveThreshold(
                    img_contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 11, 2
                )
                
                # Convert back to PIL
                processed_img = Image.fromarray(img_thresh)
            
            else:
                # If no specific processing but numpy conversion succeeded, convert back to PIL
                if len(img_np.shape) == 3:  # Color image
                    processed_img = Image.fromarray(img_np)
                else:
                    processed_img = Image.fromarray(img_np)
                    
        except Exception as e:
            print(f"Advanced preprocessing error: {str(e)}")
            # Fall back to PIL-based processing if numpy/OpenCV fails
            
            if preproc_type == "contrast":
                # Enhance contrast
                enhancer = ImageEnhance.Contrast(processed_img)
                processed_img = enhancer.enhance(1.8)  # Increase contrast by 80%
                
                # Also enhance brightness slightly
                enhancer = ImageEnhance.Brightness(processed_img)
                processed_img = enhancer.enhance(1.2)  # Increase brightness by 20%
                
            elif preproc_type == "sharpen":
                # Apply multiple sharpening passes
                processed_img = processed_img.filter(ImageFilter.SHARPEN)
                processed_img = processed_img.filter(ImageFilter.SHARPEN)
                
                # Also enhance contrast slightly
                enhancer = ImageEnhance.Contrast(processed_img)
                processed_img = enhancer.enhance(1.3)
                
            elif preproc_type == "grayscale":
                # Convert to grayscale with enhanced contrast
                processed_img = processed_img.convert('L')
                enhancer = ImageEnhance.Contrast(processed_img)
                processed_img = enhancer.enhance(1.5)
        
        # Apply AI enhancement if selected
        if self.ai_var.get():
            processed_img = self.apply_ai_enhancement(processed_img)
        
        return processed_img
    
    def _detect_image_type(self, image):
        """Auto-detect the type of image for optimal processing"""
        try:
            # Convert to numpy for analysis
            img_np = np.array(image)
            
            # Initialize scores for each type
            scores = {
                "screenshot": 0,
                "document": 0, 
                "certificate": 0,
                "single": 0
            }
            
            # Get image dimensions
            h, w = img_np.shape[:2] if len(img_np.shape) == 3 else img_np.shape
            
            # Convert to grayscale for analysis if needed
            if len(img_np.shape) == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
                
            # 1. Check aspect ratio
            aspect_ratio = w / h
            
            # Single line text tends to be very wide or very small
            if aspect_ratio > 3 or (w < 300 and h < 100):
                scores["single"] += 10
            # Documents and certificates tend to have portrait orientation
            elif aspect_ratio < 0.9:
                scores["document"] += 5
                scores["certificate"] += 5
            # Screenshots often have landscape orientation
            elif aspect_ratio > 1.2:
                scores["screenshot"] += 5
                
            # 2. Analyze color distribution
            if len(img_np.shape) == 3:
                # Calculate average color variance (more variance = more likely a screenshot)
                color_var = np.mean([np.var(img_np[:,:,i]) for i in range(3)])
                if color_var > 2500:
                    scores["screenshot"] += 8
                else:
                    scores["document"] += 5
                    
                # Check for mostly white background (common in documents/certificates)
                white_pixels = np.sum((img_np > 200).all(axis=2))
                total_pixels = h * w
                white_ratio = white_pixels / total_pixels
                
                if white_ratio > 0.7:
                    scores["document"] += 7
                    scores["certificate"] += 5
                elif white_ratio > 0.5:
                    scores["document"] += 3
                else:
                    scores["screenshot"] += 3
                    
            # 3. Edge analysis
            edges = cv2.Canny(gray, 50, 150)
            edge_ratio = np.sum(edges > 0) / (h * w)
            
            # Screenshots often have more distinct edges
            if 0.05 < edge_ratio < 0.2:
                scores["screenshot"] += 6
            # Documents have moderate edges
            elif 0.02 < edge_ratio < 0.05:
                scores["document"] += 6
            # Certificates often have decorative borders
            elif 0.01 < edge_ratio < 0.03:
                scores["certificate"] += 8
            # Single line text has very few edges
            elif edge_ratio < 0.01:
                scores["single"] += 8
                
            # 4. Text density estimation (use edge density as a proxy)
            # Calculate histogram to estimate text density regions
            hist_y = np.sum(edges, axis=1) / w
            hist_x = np.sum(edges, axis=0) / h
            
            # Calculate variance of histogram to detect text patterns
            var_y = np.var(hist_y)
            var_x = np.var(hist_x)
            
            # High variance indicates structured text (like paragraphs in documents)
            if var_y > 0.01 and var_x > 0.01:
                scores["document"] += 7
            # Very low variance might indicate single line
            elif var_y < 0.005 and var_x < 0.005:
                scores["single"] += 6
            # Medium variance might indicate screenshot with UI elements
            else:
                scores["screenshot"] += 4
                
            # 5. Certificate-specific check
            if self._is_likely_certificate(image):
                scores["certificate"] += 15
                
            # Determine the highest scoring type
            max_type = max(scores, key=scores.get)
            print(f"Image type scores: {scores}")
            
            # If the mode is clearly determined, use it
            if scores[max_type] > 12 and scores[max_type] > max(scores.values()) - scores[max_type]:
                return max_type
            
            # Default to document as a fallback (most general case)
            return "document"
            
        except Exception as e:
            print(f"Error in image type detection: {str(e)}")
            return "document"  # Default to document type as fallback
    
    def _is_likely_certificate(self, image):
        """Detect if image is likely a certificate or formal document"""
        try:
            # Convert to numpy for analysis
            img_np = np.array(image)
            
            # If it's a color image, check for mostly white background
            if len(img_np.shape) == 3:
                # Calculate percentage of white-ish pixels
                white_pixels = np.sum((img_np > 200).all(axis=2))
                total_pixels = img_np.shape[0] * img_np.shape[1]
                white_ratio = white_pixels / total_pixels
                
                # Certificates usually have > 60% white space
                if white_ratio > 0.6:
                    # Look for border patterns or formal layouts
                    # Convert to grayscale for edge detection
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                    
                    # Edge detection to find borders/patterns
                    edges = cv2.Canny(gray, 50, 150)
                    
                    # Count edge pixels
                    edge_ratio = np.sum(edges > 0) / total_pixels
                    
                    # Certificates often have border decorations (about 2-8% edge pixels)
                    if 0.02 < edge_ratio < 0.08:
                        return True
            
            # For grayscale images
            elif len(img_np.shape) == 2:
                # Check for mostly white background
                white_pixels = np.sum(img_np > 200)
                total_pixels = img_np.shape[0] * img_np.shape[1]
                white_ratio = white_pixels / total_pixels
                
                if white_ratio > 0.6:
                    # Look for edges/borders
                    edges = cv2.Canny(img_np, 50, 150)
                    edge_ratio = np.sum(edges > 0) / total_pixels
                    
                    if 0.02 < edge_ratio < 0.08:
                        return True
            
            return False
            
        except Exception as e:
            print(f"Certificate detection error: {str(e)}")
            return False
    
    def _enhance_certificate(self, image):
        """Apply specialized preprocessing for certificates"""
        try:
            # Convert to numpy for processing
            img_np = np.array(image)
            
            # Convert to grayscale if color
            if len(img_np.shape) == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
            
            # Create multiple processed versions for multi-pass OCR
            processed_versions = []
            
            # Version 1: Basic contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            processed_versions.append(enhanced)
            
            # Version 2: Strong contrast with binary threshold
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_versions.append(binary)
            
            # Version 3: Adaptive threshold for variable backgrounds
            adaptive = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            processed_versions.append(adaptive)
            
            # Version 4: Noise reduction without affecting text
            denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
            processed_versions.append(denoised)
            
            # Version 5: Edge enhancement for better text definition
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            processed_versions.append(sharpened)
            
            # Version 6: Morphological operations to connect broken text
            kernel = np.ones((1, 1), np.uint8)
            morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            processed_versions.append(morph)
            
            # Store all versions for multi-pass OCR
            self.processing_results = processed_versions
            self.multi_processing_available = True
            
            # Return the adaptive threshold version as primary
            processed_img = Image.fromarray(adaptive)
            return processed_img
            
        except Exception as e:
            print(f"Certificate enhancement error: {str(e)}")
            return image  # Return original if processing fails
            
    def _extract_certificate_text(self, image, config):
        """Specialized text extraction for certificates and formal documents"""
        print("Using specialized certificate text extraction")
        
        try:
            # For certificates, we'll try multiple approaches and combine results
            all_results = []
            
            # 1. Standard approach with the certificate-optimized image
            result1 = pytesseract.image_to_string(image, config=config).strip()
            all_results.append(result1)
            
            # 2. Try with different processing techniques if available
            if hasattr(self, 'processing_results') and self.multi_processing_available:
                for i, proc_img in enumerate(self.processing_results):
                    try:
                        # Convert to PIL
                        pil_img = Image.fromarray(proc_img)
                        
                        # Try different OCR configurations
                        if i == 0:  # For enhanced contrast
                            proc_result = pytesseract.image_to_string(pil_img, config=config).strip()
                        elif i == 1:  # For binary threshold
                            # Use a config optimized for clean binary images
                            binary_config = config.replace("--oem 1", "--oem 0")  # Legacy engine can be better for binary
                            proc_result = pytesseract.image_to_string(pil_img, config=binary_config).strip()
                        elif i == 2:  # For adaptive threshold
                            # Try with single column assumption
                            adapt_config = config.replace("--psm 3", "--psm 4")
                            proc_result = pytesseract.image_to_string(pil_img, config=adapt_config).strip()
                        else:
                            # Use standard config
                            proc_result = pytesseract.image_to_string(pil_img, config=config).strip()
                            
                        all_results.append(proc_result)
                    except Exception as e:
                        print(f"Error processing image version {i}: {str(e)}")
            
            # 3. Try segmenting the image to focus on title and content separately
            try:
                # For certificates, extract the top third (usually contains title/header)
                top_third = image.crop((0, 0, image.width, image.height // 3))
                
                # Extract middle section (usually contains main content)
                middle = image.crop((0, image.height // 3, image.width, image.height * 2 // 3))
                
                # Extract bottom section (usually contains signatures, dates)
                bottom = image.crop((0, image.height * 2 // 3, image.width, image.height))
                
                # Use single-line mode for the title (with a hint it's a title)
                title_config = config.replace("--psm 3", "--psm 7") + " -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ "
                title_text = pytesseract.image_to_string(top_third, config=title_config).strip()
                
                # Use text block mode for the body
                body_config = config.replace("--psm 3", "--psm 6")
                body_text = pytesseract.image_to_string(middle, config=body_config).strip()
                
                # Use sparse text mode for the bottom (often signatures)
                sig_config = config.replace("--psm 3", "--psm 11")
                sig_text = pytesseract.image_to_string(bottom, config=sig_config).strip()
                
                # Combine the results with proper formatting
                sectioned_text = f"{title_text}\n\n{body_text}\n\n{sig_text}"
                all_results.append(sectioned_text)
                
                # Also try just the middle section with highest quality
                if hasattr(self, 'processing_results') and len(self.processing_results) > 2:
                    # Convert middle section to numpy
                    middle_np = np.array(middle)
                    if len(middle_np.shape) == 3:
                        middle_gray = cv2.cvtColor(middle_np, cv2.COLOR_RGB2GRAY)
                    else:
                        middle_gray = middle_np
                    
                    # Apply adaptive threshold
                    middle_adaptive = cv2.adaptiveThreshold(
                        middle_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                        cv2.THRESH_BINARY, 11, 2
                    )
                    
                    # Convert back to PIL
                    middle_enhanced = Image.fromarray(middle_adaptive)
                    
                    # OCR with optimized settings
                    middle_enhanced_text = pytesseract.image_to_string(middle_enhanced, config=body_config).strip()
                    
                    # Add to results
                    all_results.append(f"{title_text}\n\n{middle_enhanced_text}\n\n{sig_text}")
            except Exception as e:
                print(f"Certificate segmentation error: {str(e)}")
            
            # 4. Try special handling for just the certificate text (common in middle section)
            # This will catch "CERTIFICATE" text and the main content
            try:
                # Create a copy of the image and apply special processing for "CERTIFICATE" text
                img_np = np.array(image)
                if len(img_np.shape) == 3:
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_np
                
                # Apply strong contrast
                _, cert_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Dilate to connect letters
                kernel = np.ones((2, 2), np.uint8)
                dilated = cv2.dilate(cert_binary, kernel, iterations=1)
                
                # Convert back to PIL
                cert_img = Image.fromarray(dilated)
                
                # Try to find the word "CERTIFICATE" and nearby text
                cert_config = config + " -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ "
                cert_text = pytesseract.image_to_string(cert_img, config=cert_config).strip()
                
                # Add to results
                all_results.append(cert_text)
            except Exception as e:
                print(f"Certificate text extraction error: {str(e)}")
            
            # Choose the best result based on content quality
            best_result = self._select_best_certificate_result(all_results)
            
            # Apply certificate-specific post-processing
            final_result = self._post_process_certificate_text(best_result)
            
            return final_result
            
        except Exception as e:
            print(f"Certificate OCR error: {str(e)}")
            # Fall back to standard OCR
            return pytesseract.image_to_string(image, config=config).strip()
            
    def _post_process_certificate_text(self, text):
        """Apply specialized post-processing for certificate text"""
        if not text:
            return text
            
        # Fix common certificate words that might be misrecognized
        certificate_corrections = {
            'certif': 'certificate',
            'certificat': 'certificate',
            'certificare': 'certificate',
            'certiticate': 'certificate',
            'certificste': 'certificate',
            'certlficate': 'certificate',
            'aword': 'award',
            'awerd': 'award',
            'awasd': 'award',
            'achievenent': 'achievement',
            'achievernent': 'achievement',
            'completion': 'completion',
            'cornpletion': 'completion',
            'presentet': 'presented',
            'presentec': 'presented',
            'recegnition': 'recognition',
            'recogniton': 'recognition',
            'recogn': 'recognition',
            'perfarmance': 'performance',
            'performonce': 'performance',
            'excellonce': 'excellence',
            'excellance': 'excellence',
            'euthorized': 'authorized',
            'authorlzed': 'authorized',
            'authorised': 'authorized',
            'slgnature': 'signature',
            'signafure': 'signature',
            'signatore': 'signature',
            'signoture': 'signature',
            'direcfor': 'director',
            'directar': 'director',
            'presidont': 'president',
            'presidont': 'president',
            'chaiperson': 'chairperson',
            'chairparson': 'chairperson',
            'chairnran': 'chairman',
            'chairwan': 'chairman',
            'opproval': 'approval',
            'appraval': 'approval',
            'approvel': 'approval'
        }
        
        # Apply corrections
        words = text.split()
        corrected_words = []
        
        for word in words:
            word_lower = word.lower()
            if word_lower in certificate_corrections:
                # Preserve capitalization
                if word.isupper():
                    corrected_words.append(certificate_corrections[word_lower].upper())
                elif word[0].isupper():
                    corrected_words.append(certificate_corrections[word_lower].capitalize())
                else:
                    corrected_words.append(certificate_corrections[word_lower])
            else:
                corrected_words.append(word)
        
        corrected_text = ' '.join(corrected_words)
        
        # Fix common format issues in certificates
        
        # Ensure certificate headings are uppercase and on their own line
        for heading in ['CERTIFICATE', 'AWARD', 'RECOGNITION', 'ACHIEVEMENT']:
            pattern = r'([^\n]*)(' + heading + r')([^\n]*)'
            corrected_text = re.sub(pattern, r'\1\n' + heading + r'\n\3', corrected_text, flags=re.IGNORECASE)
        
        # Ensure "presented to" and "awarded to" are on their own line
        for phrase in ['presented to', 'awarded to', 'given to', 'granted to']:
            pattern = r'([^\n]*)(' + phrase + r')([^\n]*)'
            corrected_text = re.sub(pattern, r'\1\n\2\n\3', corrected_text, flags=re.IGNORECASE)
        
        # Remove excessive newlines
        corrected_text = re.sub(r'\n{3,}', '\n\n', corrected_text)
        
        return corrected_text.strip()
    
    def scan_image(self):
        if not self.current_image_path:
            messagebox.showinfo("No Image", "Please upload an image first.")
            self.status_var.set("No image to scan")
            return
            
        if not self.tesseract_installed:
            answer = messagebox.askyesno(
                "Tesseract Not Properly Configured", 
                f"{self.tesseract_message}\n\n"
                "OCR functionality may not work correctly.\n\n"
                "Do you want to try anyway?"
            )
            if not answer:
                self.status_var.set("OCR aborted - Tesseract not configured")
                return
        
        if self.current_image is None:
            # If for some reason the image wasn't loaded properly, try to reload it
            try:
                self.current_image = Image.open(self.current_image_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not load image for processing: {str(e)}")
                self.status_var.set("Error loading image")
                return
        
        # Show processing indicator on the image
        self.show_processing_indicator()
        
        # Start OCR in a separate thread to keep UI responsive
        threading.Thread(target=self._process_ocr, daemon=True).start()
    
    def show_processing_indicator(self):
        """Show a processing indicator on the preview area"""
        # Hide the old processing indicator
        self.processing_indicator.place_forget()
        
        # Show hashtag loading bar (only in preview area, not in extracted text)
        self.hashtag_frame.place(relx=0.5, rely=0.5, width=300, height=50, anchor=tk.CENTER)
        self.hashtag_count = 0
        
        # Show side progress bar
        self.side_progress.pack(fill=tk.Y, expand=True, padx=5, pady=10)
        self.side_progress_var.set(0)
        
        # Show status in preview area
        self.preview_status.config(text="Image processing in progress...")
        
        # Start hashtag animation
        self.pulsating = True
        self._animate_hashtag_bar()
        
        # Disable buttons during processing
        self.scan_btn.config(state=tk.DISABLED)
        self.upload_btn.config(state=tk.DISABLED)
        
        # Update status bar
        self.status_var.set("OCR processing in progress...")
        
        # Clear text box but don't show animation in it
        self.text_box.delete(1.0, tk.END)
        
        # Ensure text frame maintains its size
        self.text_frame.config(height=150)
        self.text_frame.pack_propagate(False)
        
        # Force UI update
        self.root.update()
    
    def hide_processing_indicator(self):
        """Hide the processing indicator"""
        # Stop animation
        self.pulsating = False
        
        # Hide the indicators - with error handling
        try:
            self.processing_indicator.place_forget()
        except:
            pass
            
        try:
            self.hashtag_frame.place_forget()
        except:
            pass
        
        # Hide side progress bar
        try:
            self.side_progress.pack_forget()
        except:
            pass
        
        # Reset preview status
        try:
            self.preview_status.config(text="")
        except:
            pass
        
        # Re-enable buttons
        try:
            self.scan_btn.config(state=tk.NORMAL)
            self.upload_btn.config(state=tk.NORMAL)
        except:
            pass
        
        # Update status
        try:
            self.status_var.set("OCR processing complete")
        except:
            pass
        
        # Force UI update
        try:
            self.root.update()
        except:
            pass
    
    def _animate_hashtag_bar(self):
        """Animate the hashtag loading bar"""
        if not self.pulsating:
            return
        
        try:
            # Increment hashtag count (cycle from 1 to 20)
            self.hashtag_count = (self.hashtag_count + 1) % 21
            if self.hashtag_count == 0:
                self.hashtag_count = 1
                
            # Create hashtag loading bar
            hashtags = "#" * self.hashtag_count
            spaces = " " * (20 - self.hashtag_count)
            progress_text = f"[{hashtags}{spaces}]"
            
            # Update hashtag label
            self.hashtag_label.config(text=progress_text)
            
            # Alternate colors for visual effect
            if self.hashtag_count % 5 == 0:
                if self.hashtag_label.cget("foreground") == "#0066CC":  # Blue
                    self.hashtag_label.config(foreground="#FF4500")  # Orange-red
                else:
                    self.hashtag_label.config(foreground="#0066CC")  # Blue
            
            # Schedule next animation frame (faster for smoother animation)
            self.root.after(100, self._animate_hashtag_bar)
        except:
            # If there's an error (e.g., widget destroyed), stop animation
            self.pulsating = False
    
    def _animate_processing_indicator(self):
        """Animate the processing indicator with pulsating effect"""
        if not self.pulsating:
            return
        
        try:
            # Alternate colors for pulsating effect
            current_fg = self.processing_indicator.cget("foreground")
            
            if current_fg == "#FF4500":  # Orange-red
                new_fg = "#0066CC"  # Blue
            else:
                new_fg = "#FF4500"  # Orange-red
                
            self.processing_indicator.config(foreground=new_fg)
            
            # Schedule next animation frame
            self.root.after(500, self._animate_processing_indicator)
        except:
            # If there's an error (e.g., widget destroyed), stop animation
            self.pulsating = False
    
    def apply_ai_enhancement(self, image):
        """Apply advanced image processing techniques for optimal OCR results"""
        try:
            # Get current OCR mode
            ocr_mode = self.mode_var.get()
            
            # Convert PIL image to OpenCV format
            if image.mode == 'RGB':
                img_cv = np.array(image)
                # Convert RGB to BGR (OpenCV format)
                img_cv = img_cv[:, :, ::-1].copy()
            elif image.mode == 'L':
                img_cv = np.array(image)
            else:
                # Convert to RGB first, then to OpenCV format
                img_cv = np.array(image.convert('RGB'))
                img_cv = img_cv[:, :, ::-1].copy()
            
            # Store original image for multi-algorithm approach
            original_cv = img_cv.copy()
            
            # Optimize by downscaling very large images for faster processing
            h, w = img_cv.shape[:2] if len(img_cv.shape) == 3 else img_cv.shape
            max_dimension = 2000  # Maximum dimension for processing
            scale_factor = 1.0
            
            if max(h, w) > max_dimension:
                scale_factor = max_dimension / max(h, w)
                new_width = int(w * scale_factor)
                new_height = int(h * scale_factor)
                img_cv = cv2.resize(img_cv, (new_width, new_height), interpolation=cv2.INTER_AREA)
                print(f"Downscaled image from {w}x{h} to {new_width}x{new_height} for faster processing")
            
            # Convert to grayscale if not already
            if len(img_cv.shape) == 3:
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_cv
            
            # Update progress
            self._update_progress(10, "Initial image processing...")
            
            # Create a multi-approach results array to try different methods
            processed_images = []
            
            # For each mode, apply specialized processing
            if ocr_mode == "screenshot":
                # Approach 1: Optimize for clean digital text
                self._update_progress(20, "Optimizing screenshot...")
                
                # Apply CLAHE for better contrast
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img_contrast = clahe.apply(gray)
                
                # Apply simple threshold
                _, result1 = cv2.threshold(img_contrast, 150, 255, cv2.THRESH_BINARY)
                processed_images.append(result1)
                
                # Approach 2: Sharpen and threshold
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                img_sharp = cv2.filter2D(gray, -1, kernel)
                _, result2 = cv2.threshold(img_sharp, 150, 255, cv2.THRESH_BINARY)
                processed_images.append(result2)
                
            elif ocr_mode == "document":
                # Approach 1: Optimize for document scans
                self._update_progress(20, "Optimizing document scan...")
                
                # Apply CLAHE for better contrast
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img_contrast = clahe.apply(gray)
                
                # Apply denoising
                img_denoised = cv2.fastNlMeansDenoising(img_contrast, None, 10, 7, 21)
                
                # Apply adaptive threshold
                result1 = cv2.adaptiveThreshold(
                    img_denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 11, 2
                )
                processed_images.append(result1)
                
                # Approach 2: Otsu's thresholding for cleaner results
                img_blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                _, result2 = cv2.threshold(img_blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                processed_images.append(result2)
                
                # Approach 3: Canny edge detection with dilation for text enhancement
                edges = cv2.Canny(gray, 100, 200)
                kernel = np.ones((3, 3), np.uint8)
                dilated_edges = cv2.dilate(edges, kernel, iterations=1)
                result3 = 255 - dilated_edges  # Invert for OCR
                processed_images.append(result3)
                
            elif ocr_mode == "single":
                # Optimize for single line text
                self._update_progress(20, "Optimizing button/text...")
                
                # Approach 1: Scale up small images for better detail
                if min(gray.shape) < 100:
                    scale = 3.0
                    img_scaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                    
                    # Apply CLAHE for better contrast
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    img_contrast = clahe.apply(img_scaled)
                    
                    # Apply simple threshold
                    _, result1 = cv2.threshold(img_contrast, 150, 255, cv2.THRESH_BINARY)
                else:
                    # Apply CLAHE and threshold
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    img_contrast = clahe.apply(gray)
                    _, result1 = cv2.threshold(img_contrast, 150, 255, cv2.THRESH_BINARY)
                    
                processed_images.append(result1)
                
                # Approach 2: Sharpen and threshold
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                img_sharp = cv2.filter2D(gray, -1, kernel)
                _, result2 = cv2.threshold(img_sharp, 150, 255, cv2.THRESH_BINARY)
                processed_images.append(result2)
                
            else:  # Auto detect or fallback
                # Apply multiple techniques for auto mode
                self._update_progress(20, "Applying multiple enhancement techniques...")
                
                # Approach 1: Adaptive threshold
                result1 = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 11, 2
                )
                processed_images.append(result1)
                
                # Approach 2: CLAHE + Otsu threshold
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img_contrast = clahe.apply(gray)
                _, result2 = cv2.threshold(img_contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                processed_images.append(result2)
                
                # Approach 3: Denoising + sharpening
                img_denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                img_sharp = cv2.filter2D(img_denoised, -1, kernel)
                _, result3 = cv2.threshold(img_sharp, 150, 255, cv2.THRESH_BINARY)
                processed_images.append(result3)
            
            # Store all processed images for multi-pass OCR
            self.processing_results = processed_images
            self.multi_processing_available = True
            
            # Update progress
            self._update_progress(80, "Finalizing enhanced image...")
            
            # Choose the first result as the default
            result = processed_images[0] if processed_images else gray
            
            # Convert back to PIL format
            enhanced_img = Image.fromarray(result)
            
            # Update progress
            self._update_progress(90, "Image enhancement complete")
            
            self.status_var.set("AI enhancement applied")
            return enhanced_img
            
        except Exception as e:
            print(f"AI enhancement error: {str(e)}")
            self.status_var.set("AI enhancement failed, using original image")
            return image
    
    def _process_ocr(self):
        """Process OCR in a separate thread with progress indication"""
        try:
            # Don't use separate toplevel progress dialog - use in-frame progress instead
            self.status_var.set("Processing image...")
            
            # Show processing indicator directly in the main window
            self.show_processing_indicator()
            
            # Make sure UI is updated
            self.root.update()
            
            start_time = time.time()
            
            # Apply preprocessing to a copy of the image
            self._update_progress(5, "Preparing image...")
            processed_image = self.preprocess_image(self.current_image.copy())
            
            # Debug info
            print(f"Processing image: {self.current_image_path}")
            print(f"Image format: {processed_image.format}")
            print(f"Image size: {processed_image.size}")
            print(f"Image mode: {processed_image.mode}")
            print(f"AI enhancement: {'Yes' if self.ai_var.get() else 'No'}")
            print(f"Preprocessing: {self.preproc_var.get()}")
            print(f"OCR Mode: {self.mode_var.get()}")
            
            # Force conversion to RGB if needed
            if processed_image.mode not in ['RGB', 'L']:
                processed_image = processed_image.convert('RGB')
            
            # Optimize processing for large images
            w, h = processed_image.size
            if w * h > 1000000:  # For images larger than 1 megapixel
                # Resize for faster OCR processing
                scale_factor = min(1.0, 1000000 / (w * h))
                new_w = int(w * scale_factor)
                new_h = int(h * scale_factor)
                processed_image = processed_image.resize((new_w, new_h), Image.LANCZOS)
                print(f"Resized image for OCR: {w}x{h} -> {new_w}x{new_h}")
            
            # Get OCR configuration based on mode
            config = self._get_ocr_config()
            print(f"Using OCR config: {config}")
            
            # Update progress
            self._update_progress(95, "Extracting text...")
            
            # Use optimized OCR approach based on image type
            text = self._fast_ocr(processed_image, config)
            
            # Post-process text to clean up gibberish
            text = self._clean_text(text)
            
            # If the result is just dashes or placeholders, try with a different approach
            if not text or re.match(r'^[-_=.…]+$', text.strip()):
                print("Initial OCR result appears to be just dashes or placeholders, trying again with different settings")
                # Try with a different OCR engine mode
                alt_config = f"--psm 6 --oem 3 -l {self.lang_var.get()}"
                print(f"Using alternate OCR config: {alt_config}")
                text = pytesseract.image_to_string(processed_image, config=alt_config).strip()
                text = self._clean_text(text)
                
                # If still no good results, try one more time with another approach
                if not text or re.match(r'^[-_=.…]+$', text.strip()):
                    # Try with the original image without preprocessing
                    print("Still no good results, trying with original image")
                    orig_img = self.current_image.copy()
                    if orig_img.mode not in ['RGB', 'L']:
                        orig_img = orig_img.convert('RGB')
                    text = pytesseract.image_to_string(orig_img, config="--psm 3 --oem 3 -l eng").strip()
                    text = self._clean_text(text)
            
            # Measure and log processing time
            end_time = time.time()
            processing_time = end_time - start_time
            print(f"OCR processing time: {processing_time:.2f} seconds")
            
            print(f"Extracted text length: {len(text)}")
            print(f"First 100 chars: {text[:100]}")
            
            # Save the processed image for debugging if needed
            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, "last_processed.png")
            processed_image.save(debug_path)
            print(f"Saved debug image to: {debug_path}")
            
            # Update progress
            self._update_progress(100, "Completed!")
            
            # Hide the processing indicator
            self.root.after(0, self.hide_processing_indicator)
            
            # Display the extracted text in the main thread
            self.root.after(0, lambda: self._update_text_box(text))
            
            # Enable the view processed image button
            self.root.after(0, lambda: self.view_processed_btn.config(state=tk.NORMAL))
            
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            error_message = str(e)  # Store error message in a local variable
            
            # Special handling for tessdata errors
            if "tessdata" in error_message or "TESSDATA_PREFIX" in error_message:
                error_message = "Tesseract language data files not found. Please install the language data or set TESSDATA_PREFIX correctly."
            
            # Hide the processing indicator safely
            try:
                self.root.after(0, self.hide_processing_indicator)
            except Exception as dialog_error:
                print(f"Error hiding processing indicator: {str(dialog_error)}")
                
            # Show error in the main thread using a local variable that won't be lost in the lambda
            try:
                self.root.after(0, lambda msg=error_message: self._show_error(msg))
            except Exception as ui_error:
                print(f"Error showing error message: {str(ui_error)}")
    
    def _fast_ocr(self, image, config):
        """Optimized OCR process for extremely accurate text extraction"""
        try:
            # Check image type and apply specialized extraction
            detected_type = ""
            if hasattr(self, 'detected_type'):
                detected_type = self.detected_type
            else:
                # Try to detect type if not already detected
                detected_type = self._detect_image_type(self.current_image)
                self.detected_type = detected_type
            
            # Use specialized extraction based on type
            if detected_type == "certificate" and self._is_likely_certificate(self.current_image):
                return self._extract_certificate_text(image, config)
            elif detected_type == "screenshot":
                return self._extract_screenshot_text(image, config)
            elif detected_type == "document":
                return self._extract_document_text(image, config)
            elif detected_type == "single":
                return self._extract_single_line_text(image, config)
                
            # Standard processing for other image types
            # Get the image size
            w, h = image.size
            
            # Store different OCR results for voting/consensus
            all_results = []
            
            # For smaller images, use multiple OCR approaches
            if w * h < 500000:
                # First pass - standard OCR with selected config
                result1 = pytesseract.image_to_string(image, config=config).strip()
                all_results.append(result1)
                
                # Second pass - try with different PSM mode
                alt_config = config.replace("--psm 3", "--psm 6").replace("--psm 7", "--psm 6")
                if alt_config == config:  # If no replacement was made
                    alt_config = config.replace("--psm 6", "--psm 3")
                result2 = pytesseract.image_to_string(image, config=alt_config).strip()
                all_results.append(result2)
                
                # Third pass - try with enhanced image
                # Apply adaptive thresholding for better contrast
                try:
                    img_np = np.array(image)
                    if len(img_np.shape) == 3:  # Color image
                        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                    else:  # Already grayscale
                        img_gray = img_np
                        
                    # Apply adaptive thresholding
                    img_thresh = cv2.adaptiveThreshold(
                        img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                        cv2.THRESH_BINARY, 11, 2
                    )
                    
                    # Convert back to PIL
                    enhanced_img = Image.fromarray(img_thresh)
                    
                    # Run OCR on enhanced image
                    result3 = pytesseract.image_to_string(enhanced_img, config=config).strip()
                    all_results.append(result3)
                except Exception as e:
                    print(f"Enhancement error in multi-pass OCR: {str(e)}")
                    # Skip this result
                
                # Choose the best result based on length and quality
                result = self._select_best_ocr_result(all_results)
                print(f"Selected best result from {len(all_results)} OCR passes")
                return result
            
            # For larger images, split into regions and process in parallel with multiple approaches
            print("Using parallel multi-pass OCR processing for large image")
            
            # Determine number of regions (vertical splits)
            num_regions = min(4, max(2, h // 500))  # Max 4 regions, min 2 if large
            
            # Create regions
            region_height = h // num_regions
            regions = []
            
            for i in range(num_regions):
                y_start = i * region_height
                y_end = y_start + region_height if i < num_regions - 1 else h
                region = image.crop((0, y_start, w, y_end))
                regions.append(region)
            
            # Process each region with multiple approaches in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_regions) as executor:
                region_results = []
                
                # For each region, submit multiple OCR tasks
                for region in regions:
                    # Submit standard OCR
                    future1 = executor.submit(pytesseract.image_to_string, region, config=config)
                    
                    # Submit with alternate config
                    alt_config = config.replace("--psm 3", "--psm 6").replace("--psm 7", "--psm 6")
                    if alt_config == config:  # If no replacement was made
                        alt_config = config.replace("--psm 6", "--psm 3")
                    future2 = executor.submit(pytesseract.image_to_string, region, config=alt_config)
                    
                    # Add to results
                    region_results.append((future1, future2))
                
                # Collect results for each region
                combined_results = []
                for futures in region_results:
                    region_texts = []
                    for future in futures:
                        try:
                            text = future.result().strip()
                            region_texts.append(text)
                        except Exception as e:
                            print(f"Error in region OCR: {str(e)}")
                    
                    # Choose best result for this region
                    if region_texts:
                        best_text = self._select_best_ocr_result(region_texts)
                        combined_results.append(best_text)
            
            # Combine region results
            combined_text = "\n".join(combined_results)
            print(f"Combined multi-pass OCR result: '{combined_text}'")
            return combined_text
            
        except Exception as e:
            print(f"Fast OCR error: {str(e)}")
            # Fall back to standard OCR
            return pytesseract.image_to_string(image, config=config).strip()
    
    def _extract_document_text(self, image, config):
        """Specialized text extraction for document images"""
        print("Using specialized document text extraction")
        
        try:
            # For documents, we'll try multiple approaches and combine results
            all_results = []
            
            # 1. Standard approach with optimized image
            result1 = pytesseract.image_to_string(image, config=config).strip()
            all_results.append(result1)
            
            # 2. Try with different processing techniques if available
            if hasattr(self, 'processing_results') and self.multi_processing_available:
                for i, proc_img in enumerate(self.processing_results):
                    try:
                        # Convert to PIL
                        pil_img = Image.fromarray(proc_img)
                        
                        # Try different OCR configurations based on processing type
                        if i == 0:  # Enhanced contrast
                            doc_config = config.replace("--psm 3", "--psm 4")  # Single column assumption
                            proc_result = pytesseract.image_to_string(pil_img, config=doc_config).strip()
                        elif i == 1:  # Adaptive threshold
                            # Default config usually works well for adaptive
                            proc_result = pytesseract.image_to_string(pil_img, config=config).strip()
                        elif i == 3:  # Otsu threshold
                            # Legacy engine can work better for clean binary
                            binary_config = config.replace("--oem 1", "--oem 0")
                            proc_result = pytesseract.image_to_string(pil_img, config=binary_config).strip()
                        else:
                            # Use standard config
                            proc_result = pytesseract.image_to_string(pil_img, config=config).strip()
                            
                        all_results.append(proc_result)
                    except Exception as e:
                        print(f"Error processing document image version {i}: {str(e)}")
            
            # 3. Try multi-column detection for complex layouts
            try:
                # Check for multi-column layout
                img_np = np.array(image)
                if len(img_np.shape) == 3:
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_np
                
                # Use horizontal projection to detect columns
                # Sum pixels horizontally to find vertical spaces
                h_proj = np.sum(gray < 200, axis=0)
                
                # Find possible column boundaries (areas with few dark pixels)
                col_boundaries = []
                threshold = np.mean(h_proj) * 0.3
                for i in range(1, len(h_proj)):
                    if h_proj[i-1] > threshold and h_proj[i] <= threshold:
                        col_boundaries.append(i)
                    elif h_proj[i-1] <= threshold and h_proj[i] > threshold:
                        col_boundaries.append(i)
                
                # If we found potential column boundaries and there's more than 2
                # (indicating at least one column), process columns separately
                if len(col_boundaries) >= 4 and gray.shape[1] > 600:
                    print(f"Detected possible multi-column layout with {len(col_boundaries)} boundaries")
                    
                    # Group boundaries into column regions
                    col_regions = []
                    for i in range(0, len(col_boundaries), 2):
                        if i+1 < len(col_boundaries):
                            # Only consider columns wider than 100px
                            if col_boundaries[i+1] - col_boundaries[i] > 100:
                                col_regions.append((col_boundaries[i], col_boundaries[i+1]))
                    
                    # Process each column separately
                    column_texts = []
                    for left, right in col_regions:
                        # Crop to column region
                        column_img = image.crop((left, 0, right, image.height))
                        
                        # Process with document-specific settings
                        column_config = config.replace("--psm 3", "--psm 4")  # Single column mode
                        column_text = pytesseract.image_to_string(column_img, config=column_config).strip()
                        column_texts.append(column_text)
                    
                    # Combine column results
                    if column_texts:
                        column_result = "\n\n".join(column_texts)
                        all_results.append(column_result)
            except Exception as e:
                print(f"Multi-column detection error: {str(e)}")
            
            # Choose the best result
            best_result = self._select_best_document_result(all_results)
            
            # Apply document-specific post-processing
            final_result = self._clean_text(best_result)
            
            return final_result
            
        except Exception as e:
            print(f"Document OCR error: {str(e)}")
            # Fall back to standard OCR
            return pytesseract.image_to_string(image, config=config).strip()
    
    def _extract_screenshot_text(self, image, config):
        """Specialized text extraction for screenshot images"""
        print("Using specialized screenshot text extraction")
        
        try:
            # For screenshots, we'll try multiple approaches optimized for UI text
            all_results = []
            
            # 1. Standard approach with the optimized image
            result1 = pytesseract.image_to_string(image, config=config).strip()
            all_results.append(result1)
            
            # 2. Try with different processing techniques if available
            if hasattr(self, 'processing_results') and self.multi_processing_available:
                for i, proc_img in enumerate(self.processing_results):
                    try:
                        # Convert to PIL
                        pil_img = Image.fromarray(proc_img)
                        
                        # For screenshots, we want to keep layout, so use sparse text mode
                        sparse_config = config.replace("--psm 3", "--psm 11")
                        proc_result = pytesseract.image_to_string(pil_img, config=sparse_config).strip()
                        all_results.append(proc_result)
                        
                        # Also try with block mode for UI elements
                        block_config = config.replace("--psm 3", "--psm 6")
                        block_result = pytesseract.image_to_string(pil_img, config=block_config).strip()
                        all_results.append(block_result)
                    except Exception as e:
                        print(f"Error processing screenshot version {i}: {str(e)}")
            
            # 3. Try to detect and process UI elements separately
            try:
                # Convert to numpy for processing
                img_np = np.array(image)
                if len(img_np.shape) == 3:
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_np
                
                # Apply threshold to separate UI elements
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Find contours to identify text regions
                contours, _ = cv2.findContours(255-binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Filter and sort contours by size
                min_area = 200  # Minimum area to consider
                text_contours = [c for c in contours if cv2.contourArea(c) > min_area]
                
                # If we have potential text regions, process them separately
                if text_contours and len(text_contours) < 20:  # Avoid over-segmentation
                    ui_texts = []
                    for contour in text_contours:
                        # Get bounding rectangle
                        x, y, w, h = cv2.boundingRect(contour)
                        
                        # Expand rectangle slightly
                        x = max(0, x-5)
                        y = max(0, y-5)
                        w = min(binary.shape[1]-x, w+10)
                        h = min(binary.shape[0]-y, h+10)
                        
                        # Extract region
                        region = binary[y:y+h, x:x+w]
                        
                        # Skip very small regions
                        if w < 20 or h < 10:
                            continue
                            
                        # Convert to PIL
                        region_img = Image.fromarray(region)
                        
                        # Process with single line or block mode based on aspect ratio
                        if w > h*3:  # Likely a single line
                            region_config = config.replace("--psm 3", "--psm 7")
                        else:
                            region_config = config.replace("--psm 3", "--psm 6")
                            
                        region_text = pytesseract.image_to_string(region_img, config=region_config).strip()
                        
                        if region_text:
                            ui_texts.append(region_text)
                    
                    # Combine UI element texts
                    if ui_texts:
                        ui_result = "\n".join(ui_texts)
                        all_results.append(ui_result)
            except Exception as e:
                print(f"UI element detection error: {str(e)}")
            
            # Choose the best result
            best_result = self._select_best_screenshot_result(all_results)
            
            # Apply screenshot-specific post-processing
            final_result = self._clean_text(best_result)
            
            return final_result
            
        except Exception as e:
            print(f"Screenshot OCR error: {str(e)}")
            # Fall back to standard OCR
            return pytesseract.image_to_string(image, config=config).strip()
    
    def _extract_single_line_text(self, image, config):
        """Specialized text extraction for single line text"""
        print("Using specialized single line text extraction")
        
        try:
            # For single line text, we'll try multiple optimized approaches
            all_results = []
            
            # 1. Use single line mode as default
            single_config = config.replace("--psm 3", "--psm 7")
            result1 = pytesseract.image_to_string(image, config=single_config).strip()
            all_results.append(result1)
            
            # 2. Try with different processing techniques if available
            if hasattr(self, 'processing_results') and self.multi_processing_available:
                for i, proc_img in enumerate(self.processing_results):
                    try:
                        # Convert to PIL
                        pil_img = Image.fromarray(proc_img)
                        
                        # Try different OCR configurations
                        # For single line, psm 7 (single line) and psm 8 (single word) are best
                        if i % 2 == 0:
                            proc_config = config.replace("--psm 3", "--psm 7")
                        else:
                            proc_config = config.replace("--psm 3", "--psm 8")
                            
                        proc_result = pytesseract.image_to_string(pil_img, config=proc_config).strip()
                        all_results.append(proc_result)
                    except Exception as e:
                        print(f"Error processing single line version {i}: {str(e)}")
            
            # 3. Try with different character whitelist approaches
            # For single line text, we can try different character sets to improve accuracy
            try:
                # Create enhanced versions
                img_np = np.array(image)
                if len(img_np.shape) == 3:
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_np
                
                # Apply strong threshold
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Convert to PIL
                binary_img = Image.fromarray(binary)
                
                # Try with alphanumeric whitelist
                alpha_config = single_config + " -c preserve_interword_spaces=1"
                alpha_result = pytesseract.image_to_string(binary_img, config=alpha_config).strip()
                all_results.append(alpha_result)
                
                # Try with simple custom config without problematic whitelist
                full_config = single_config + " -c textord_space_size_is_variable=0"
                full_result = pytesseract.image_to_string(binary_img, config=full_config).strip()
                all_results.append(full_result)
            except Exception as e:
                print(f"Character whitelist error: {str(e)}")
            
            # Choose the best result - for single line, just take the longest non-empty result
            best_result = ""
            for result in all_results:
                if result and len(result) > len(best_result):
                    best_result = result
            
            # If no good result, use the first one
            if not best_result and all_results:
                best_result = all_results[0]
            
            # Apply single-line specific post-processing
            final_result = self._clean_text(best_result)
            
            # Remove any newlines for single line text
            final_result = final_result.replace('\n', ' ').strip()
            
            return final_result
            
        except Exception as e:
            print(f"Single line OCR error: {str(e)}")
            # Fall back to standard OCR with single line mode
            single_config = config.replace("--psm 3", "--psm 7")
            return pytesseract.image_to_string(image, config=single_config).strip()
    
    def _select_best_certificate_result(self, results):
        """Select the best OCR result for certificates based on specialized criteria"""
        if not results:
            return ""
            
        if len(results) == 1:
            return results[0]
        
        # Filter out empty results
        non_empty = [r for r in results if r.strip()]
        if not non_empty:
            return ""
            
        # Calculate scores for each result with certificate-specific criteria
        scores = []
        for result in non_empty:
            score = 0
            
            # Look for certificate-specific keywords
            certificate_keywords = ['certificate', 'certify', 'award', 'recognition', 'presented', 
                                   'completion', 'achievement', 'hereby', 'issued', 'granted',
                                   'honored', 'date', 'signature', 'authorized', 'official']
            
            # Count matches for certificate keywords (case insensitive)
            result_lower = result.lower()
            keyword_count = sum(1 for keyword in certificate_keywords if keyword in result_lower)
            score += keyword_count * 10  # High weight for certificate keywords
            
            # Prefer results with more lines (certificates usually have multiple sections)
            lines = result.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            score += min(len(non_empty_lines), 10) * 5
            
            # Prefer results with a good ratio of text to total length
            text_ratio = sum(1 for c in result if c.isalnum()) / max(1, len(result))
            score += text_ratio * 50
            
            # Check for date patterns (common in certificates)
            date_patterns = [
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # MM/DD/YYYY or similar
                r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',  # DD Mon YYYY
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}'  # Mon DD, YYYY
            ]
            
            has_date = any(re.search(pattern, result, re.IGNORECASE) for pattern in date_patterns)
            if has_date:
                score += 30  # Bonus for having a date format
            
            scores.append((score, result))
        
        # Return the result with the highest score
        scores.sort(reverse=True)
        print(f"Selected best certificate result with score {scores[0][0]}")
        return scores[0][1]
    
    def _select_best_ocr_result(self, results):
        """Select the best OCR result from multiple passes"""
        if not results:
            return ""
            
        if len(results) == 1:
            return results[0]
        
        # Filter out empty results
        non_empty = [r for r in results if r.strip()]
        if not non_empty:
            return ""
            
        # Calculate scores for each result
        scores = []
        for result in non_empty:
            score = 0
            
            # Longer text usually means better recognition (unless it's just noise)
            words = result.split()
            score += min(len(words), 50)  # Cap at 50 words to avoid bias toward extremely long gibberish
            
            # More real words = better score
            real_word_count = sum(1 for word in words if len(word) > 1 and word.isalpha())
            score += real_word_count * 2
            
            # Higher ratio of alphanumeric characters is usually better
            alphanumeric_ratio = sum(c.isalnum() or c.isspace() for c in result) / max(1, len(result))
            score += alphanumeric_ratio * 50
            
            # Penalize excessive special characters
            special_char_ratio = sum(not (c.isalnum() or c.isspace()) for c in result) / max(1, len(result))
            score -= special_char_ratio * 30
            
            scores.append((score, result))
        
        # Return the result with the highest score
        scores.sort(reverse=True)
        return scores[0][1]
    
    def _clean_text(self, text):
        """Clean up the extracted text to remove gibberish and improve accuracy"""
        if not text:
            return text
        
        # Debug the cleaning process
        print(f"Cleaning text: '{text}'")
            
        # Replace common OCR errors with more accurate characters
        replacements = {
            '|': 'I',      # Pipe character often mistaken for 'I'
            '1': 'l',      # 1 often mistaken for 'l' in some fonts
            '[': '(',      # Common bracket mistakes
            ']': ')',
            '{': '(',
            '}': ')',
            '$': 'S',      # Dollar sign often mistaken for 'S'
            '<': '(',      # Angle brackets confused with parentheses
            '>': ')',
            '`': "'",      # Backtick confused with apostrophe
            '¢': 'c',      # Cent sign confused with 'c'
            '©': 'c',      # Copyright symbol confused with 'c'
            '®': 'R',      # Registered symbol confused with 'R'
            '°': '0',      # Degree symbol confused with '0'
            '—': '-',      # Em dash to hyphen
            '–': '-',      # En dash to hyphen
            '"': '"',      # Smart quotes to regular quotes
            '"': '"',
            "'": "'",      # Smart apostrophes to regular apostrophes
            "'": "'",
            '…': '...',    # Ellipsis to three periods
            '•': '*',      # Bullet to asterisk
            'é': 'e',      # Common accented characters
            'è': 'e',
            'ê': 'e',
            'à': 'a',
            'â': 'a',
            'ô': 'o',
            'ö': 'o'
        }
        
        for original, replacement in replacements.items():
            text = text.replace(original, replacement)
        
        # Remove lines that are mostly special characters (likely gibberish)
        cleaned_lines = []
        for line in text.split('\n'):
            # Skip empty lines
            if not line.strip():
                cleaned_lines.append('')
                continue
                
            # Skip lines that are just dashes or other placeholder characters
            if re.match(r'^[-_=.…]+$', line.strip()):
                continue
                
            # Count alphanumeric characters vs special characters
            alpha_count = sum(c.isalnum() or c.isspace() for c in line)
            if alpha_count / len(line) >= 0.3:  # At least 30% should be alphanumeric or space
                # Further cleanup on the line
                line = re.sub(r'[^\w\s.,;:!?()\'"-]', '', line)  # Remove rare special chars
                cleaned_lines.append(line)
                
        # Join lines back together
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Remove repeated whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = re.sub(r'^\s+|\s+$', '', cleaned_text, flags=re.MULTILINE)
        
        # Remove isolated single characters that aren't words
        # (but keep 'a', 'A', 'I' which are valid single-letter words)
        cleaned_text = re.sub(r'\s[b-hj-zA-HJ-Z]\s', ' ', cleaned_text)
        
        # Fix up some common word pattern errors
        cleaned_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned_text)  # Add space between lowercase and uppercase
        
        # Fix common number/letter confusions
        cleaned_text = re.sub(r'([a-zA-Z])0([a-zA-Z])', r'\1o\2', cleaned_text)  # 0 between letters is usually 'o'
        cleaned_text = re.sub(r'([a-zA-Z])1([a-zA-Z])', r'\1l\2', cleaned_text)  # 1 between letters is usually 'l'
        
        # Advanced post-processing with language model principles
        # Split into words and correct those that look like mistakes
        words = cleaned_text.split()
        corrected_words = []
        
        for word in words:
            # Skip very short words, numbers, and words with special characters
            if len(word) <= 2 or word.isdigit() or not word.isalpha():
                corrected_words.append(word)
                continue
                
            # Check for common OCR errors in longer words
            # For example: "tbe" is probably "the", "bave" is probably "have"
            common_corrections = {
                # Common OCR errors with 'h' being read as 'b'
                'tbe': 'the',
                'bave': 'have',
                'tbat': 'that',
                'tban': 'than',
                'witb': 'with',
                'lf': 'If',
                'tbis': 'this',
                'wbat': 'what',
                'wben': 'when',
                'wbere': 'where',
                'wby': 'why',
                'bere': 'here',
                'tbere': 'there',
                'tbeir': 'their',
                'tbey': 'they',
                'tbem': 'them',
                'tbese': 'these',
                'tbose': 'those',
                'bome': 'home',
                'bouse': 'house',
                'bour': 'hour',
                'bead': 'head',
                'beart': 'heart',
                'bope': 'hope',
                'bigh': 'high',
                'band': 'hand',
                'batb': 'bath',
                'botb': 'both',
                'bard': 'hard',
                'belp': 'help',
                'bealth': 'health',
                'buman': 'human',
                'sbould': 'should',
                'bowever': 'however',
                'bebind': 'behind',
                'perbaps': 'perhaps',
                'bimself': 'himself',
                'berself': 'herself',
                
                # Common OCR errors with 'rn' being read as 'm'
                'modem': 'modern',
                'leam': 'learn',
                'bum': 'burn',
                'tum': 'turn',
                'retum': 'return',
                'pattem': 'pattern',
                'concem': 'concern',
                'intem': 'intern',
                'govemment': 'government',
                
                # Common OCR errors with 'I' and 'l' confusion
                'Iike': 'like',
                'Iife': 'life',
                'Iist': 'list',
                'Iine': 'line',
                'Iight': 'light',
                'Iittle': 'little',
                'Iong': 'long',
                'Iove': 'love',
                'Iook': 'look',
                'Iarge': 'large',
                'Iater': 'later',
                'Ieft': 'left',
                'Ievel': 'level',
                'Iearn': 'learn',
                'Iast': 'last',
                'Ieast': 'least',
                
                # Common OCR errors with 'O' and '0' confusion
                '0ne': 'One',
                '0nly': 'Only',
                '0ther': 'Other',
                '0ver': 'Over',
                '0pen': 'Open',
                '0ff': 'Off',
                '0ut': 'Out',
                '0ur': 'Our',
                'g0': 'go',
                'd0': 'do',
                't0': 'to',
                'n0': 'no',
                's0': 'so',
                
                # Other common OCR errors
                'arid': 'and',
                'iri': 'in',
                'ori': 'on',
                'frorn': 'from',
                'rnay': 'may',
                'sorne': 'some',
                'tirne': 'time',
                'cornputer': 'computer',
                'systern': 'system',
                'inforrnation': 'information',
                'prograrns': 'programs',
                'rnanagement': 'management',
                'developrnent': 'development',
                'docurnent': 'document',
                'environrnent': 'environment',
                'irnportant': 'important',
                'rnore': 'more',
                'rnust': 'must',
                'nurnber': 'number',
                'sarne': 'same',
                'cornpany': 'company',
                'rnethod': 'method',
                'cornmon': 'common',
                'rnain': 'main',
                'rnake': 'make',
                'rnean': 'mean',
                'arnount': 'amount',
                'alrnost': 'almost',
                'cornplete': 'complete',
                'cornponent': 'component',
                'rnernory': 'memory',
                'cornmand': 'command',
                'cornmunity': 'community',
                'cornpare': 'compare',
                'cornplex': 'complex',
                'rnernber': 'member',
                'rnonth': 'month',
                'rnedia': 'media',
                'rnessage': 'message',
                'rnove': 'move',
                'rnodel': 'model',
                'rnorning': 'morning',
                'rnernory': 'memory',
                'rnachine': 'machine',
                'rnaterial': 'material',
                'rneasure': 'measure',
                'rnedical': 'medical',
                'rnany': 'many',
                'rnight': 'might',
                'rnarket': 'market',
                'rnoney': 'money',
                'rneet': 'meet',
                'rnile': 'mile',
                'rnind': 'mind',
                
                # Double letter issues
                'nurnber': 'number',
                'cornrnand': 'command',
                'surnrnary': 'summary',
                'surnrner': 'summer',
                'cornrnunity': 'community',
                'cornrnent': 'comment',
                'cornrnon': 'common',
                'cornrnittee': 'committee',
                'cornrnunicate': 'communicate',
                'cornrnunication': 'communication',
                'cornrnercial': 'commercial',
                'cornrnission': 'commission',
                'prograrnrning': 'programming'
            }
            
            if word.lower() in common_corrections:
                # Preserve case
                if word.isupper():
                    corrected_words.append(common_corrections[word.lower()].upper())
                elif word[0].isupper():
                    corrected_words.append(common_corrections[word.lower()].capitalize())
                else:
                    corrected_words.append(common_corrections[word.lower()])
            else:
                corrected_words.append(word)
        
        # Recombine corrected words
        final_text = ' '.join(corrected_words)
        
        # Final formatting adjustments - ensure proper spacing after punctuation
        final_text = re.sub(r'([.,;:!?])([^\s])', r'\1 \2', final_text)
        
        print(f"Cleaned result: '{final_text.strip()}'")
        return final_text.strip()
    
    def _get_ocr_config(self):
        """Get highly optimized OCR configuration based on selected mode and document type"""
        lang = self.lang_var.get()
        mode = self.mode_var.get()
        
        # If auto-detect was used, get the detected mode
        if mode == "auto" and hasattr(self, 'detected_type'):
            mode = self.detected_type
            print(f"Using detected type {mode} for OCR configuration")
        
        # Set base engine mode: OEM 1 = LSTM only, OEM 3 = default, OEM 0 = legacy engine
        # For different document types, different engines might work better
        oem_mode = 1  # Default to LSTM only (faster and more accurate for most cases)
        
        # Set PSM (Page Segmentation Mode):
        # 1 = Auto OSD, 3 = Auto, 4 = Single column, 6 = Single block, 7 = Single line,
        # 8 = Single word, 9 = Single word in circle, 10 = Single character, 11 = Sparse text, 12 = Sparse text OSD
        psm_mode = 3  # Default to Auto
        
        # Additional custom configuration parameters
        custom_params = []
        
        if mode == "document":
            # Optimized for document scans (books, papers, etc.)
            psm_mode = 4  # Assume a single column of text
            oem_mode = 3  # Use both LSTM and legacy for better accuracy
            
            # Add extra parameters for document processing
            custom_params = [
                "-c", "preserve_interword_spaces=1",  # Preserve spacing
                "-c", "textord_heavy_nr=1",  # Better handling of noisy documents
                "-c", "textord_min_linesize=2.5"  # Better line detection
            ]
            
        elif mode == "screenshot":
            # Optimized for screenshots (clean, digital text)
            psm_mode = 6  # Assume a single uniform block of text
            oem_mode = 1  # LSTM only for cleaner results
            
            # Add extra parameters for screenshot processing
            custom_params = [
                "-c", "preserve_interword_spaces=1",  # Preserve spacing
                "-c", "textord_space_size_is_variable=0"  # Fixed spacing for cleaner text
                # Removed char whitelist that was causing issues
            ]
            
        elif mode == "single":
            # Optimized for single line text, buttons, labels
            psm_mode = 7  # Single line
            oem_mode = 0  # Legacy engine works better for very short text
            
            # Add extra parameters for single line processing
            custom_params = [
                "-c", "tessedit_do_invert=0"  # Don't try to invert colors
                # Removed char whitelist that was causing issues
            ]
            
        else:  # Auto detect
            # Use default settings but with LSTM engine
            psm_mode = 3  # Auto page segmentation
            oem_mode = 1  # LSTM only for better general results
            
            # Add general optimization parameters
            custom_params = [
                "-c", "preserve_interword_spaces=1",  # Preserve spacing
                "-c", "textord_heavy_nr=1"  # Better handling of noisy images
            ]
        
        # Special configuration for certificate/formal document detection
        if hasattr(self, 'processing_results') and self.multi_processing_available and self._is_likely_certificate(self.current_image):
            # Optimized for formal certificates with specific font types and layout
            psm_mode = 4  # Assume single column of text
            oem_mode = 1  # LSTM for better character recognition
            
            # Add extra parameters specifically for certificate recognition
            custom_params = [
                "-c", "preserve_interword_spaces=1",  # Preserve spacing
                "-c", "textord_space_size_is_variable=1",  # Variable spacing for formal documents
                "-c", "textord_min_linesize=1.5",  # Better line detection for formal text
                "-c", "textord_tablefind_recognize_tables=1"  # Handle table-like layouts
                # Removed char whitelist that was causing issues
            ]
            
        # Build the final configuration string
        config = f"-l {lang} --oem {oem_mode} --psm {psm_mode}"
        
        # Add any custom parameters
        if custom_params:
            config += " " + " ".join(custom_params)
        
        print(f"Using OCR config: {config}")
        return config
    
    def _update_text_box(self, text):
        """Update the text box with extracted text (called in main thread)"""
        self.text_box.delete(1.0, tk.END)
        
        # Debug the text content
        print(f"Updating text box with: '{text}'")
        
        # Ensure all the text containers maintain their height
        if hasattr(self, 'bottom_section'):
            self.bottom_section.config(height=150)
            self.bottom_section.pack_propagate(False)
            
        if hasattr(self, 'text_container'):
            self.text_container.config(height=100)
            self.text_container.pack_propagate(False)
        
        # If there's text, display it
        if text and text.strip():
            # Remove any non-printable characters
            cleaned_text = ''.join(c if c.isprintable() or c in ['\n', '\t'] else ' ' for c in text)
            
            # Ensure we're not just displaying placeholders or dashes
            if cleaned_text.strip('-').strip():
                self.text_box.insert(tk.END, cleaned_text)
                self.extracted_text = cleaned_text
                self.status_var.set("OCR completed successfully")
                
                # Use normal border for text box
                self.text_box_frame.config(relief=tk.SOLID, bd=1)
                
                # Make sure text is visible by scrolling to top
                self.text_box.see("1.0")
            else:
                # If text is just dashes or placeholders, treat as no text
                self.text_box.insert(tk.END, "No meaningful text detected in the image.")
                self.extracted_text = ""
                self.status_var.set("OCR completed, but no meaningful text was found")
                
                # Use normal border for text box
                self.text_box_frame.config(relief=tk.SOLID, bd=1)
        else:
            # If no text was found, show a message
            self.text_box.insert(tk.END, "No text detected in the image.")
            self.extracted_text = ""
            self.status_var.set("OCR completed, but no text was found")
            
            # Use normal border for text box
            self.text_box_frame.config(relief=tk.SOLID, bd=1)
        
        # Ensure bottom section and text container are visible
        if hasattr(self, 'main_content'):
            self.main_content.update_idletasks()
            
        if hasattr(self, 'bottom_section'):
            self.bottom_section.update_idletasks()
            self.bottom_section.pack(fill=tk.X, expand=False, padx=20, pady=10, side=tk.BOTTOM)
            
        # Ensure text box has focus and is visible
        self.text_box.focus_set()
        
        # Force UI update of the entire application
        self.root.update()
    
    def _show_error(self, error_msg):
        """Show error message (called in main thread)"""
        try:
            messagebox.showerror("OCR Error", f"Error during OCR processing: {error_msg}")
            self.status_var.set("Error during OCR processing")
        except Exception as e:
            print(f"Error showing error dialog: {str(e)}")
            # If UI is not responding, at least print to console
            print(f"OCR Error: {error_msg}")
    
    def _show_progress_dialog(self, message):
        """Show a progress dialog during AI processing - DEPRECATED, use in-frame progress instead"""
        # This method is kept for compatibility but we no longer use it
        # Instead, we update the status and use the hashtag loading animation
        self.status_var.set(message)
        self._update_progress(10, message)
    
    def _update_progress_dialog(self):
        """Update the progress dialog with status messages - DEPRECATED"""
        # This method is kept for compatibility but we no longer use it
        pass
        
    def _update_progress(self, value, status_text=None):
        """Update the progress bar value and status text"""
        # Update side progress bar
        if hasattr(self, 'side_progress_var'):
            self.side_progress_var.set(value)
            
        # Update hashtag bar to match progress
        if hasattr(self, 'hashtag_count'):
            # Calculate hashtags based on progress
            hashtag_count = int((value / 100) * 20)
            if hashtag_count > 0:  # Ensure at least one hashtag is showing if progress started
                self.hashtag_count = hashtag_count
                
                # Create hashtag loading bar
                hashtags = "#" * self.hashtag_count
                spaces = " " * (20 - self.hashtag_count)
                progress_text = f"[{hashtags}{spaces}]"
                
                # Update hashtag label if it exists
                if hasattr(self, 'hashtag_label'):
                    try:
                        self.hashtag_label.config(text=progress_text)
                    except:
                        pass  # Ignore errors if the widget was destroyed
            
        if status_text and hasattr(self, 'preview_status'):
            try:
                self.preview_status.config(text=status_text)
            except:
                pass  # Ignore errors if the widget was destroyed
            
        # Also update main status bar
        if status_text:
            self.status_var.set(status_text)
            
        # Force UI update for smoother progress indication
        try:
            self.root.update_idletasks()
        except:
            pass  # Ignore errors if the application is closing
    
    def save_text(self):
        if not self.extracted_text:
            messagebox.showinfo("No Text", "There is no text to save. Please scan an image first.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.extracted_text)
                self.status_var.set(f"Text saved to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save the text: {str(e)}")
                self.status_var.set("Error saving text")
    
    def view_processed_image(self):
        """View the last processed image for debugging"""
        debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug", "last_processed.png")
        
        if os.path.exists(debug_path):
            # Create a new window to display the processed image
            debug_window = tk.Toplevel(self.root)
            debug_window.title("Processed Image")
            debug_window.geometry("800x600")
            
            # Create a frame to hold the image
            img_frame = tk.Frame(debug_window)
            img_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Load and display the image
            try:
                img = Image.open(debug_path)
                
                # Calculate the size to maintain aspect ratio
                img_width, img_height = img.size
                window_width = 760
                window_height = 500
                
                ratio = min(window_width / img_width, window_height / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                
                img = img.resize((new_width, new_height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                
                img_label = tk.Label(img_frame, image=photo)
                img_label.image = photo  # Keep a reference
                img_label.pack(fill=tk.BOTH, expand=True)
                
                # Add info label
                info_text = f"Image Size: {img_width}x{img_height}\n"
                info_text += f"Processing: {'AI Enhanced' if self.ai_var.get() else 'Standard'}, "
                info_text += f"Mode: {self.mode_var.get()}, Language: {self.lang_var.get()}"
                
                info_label = tk.Label(debug_window, text=info_text, font=("Arial", 10))
                info_label.pack(pady=(0, 10))
                
            except Exception as e:
                tk.Label(img_frame, text=f"Error loading image: {str(e)}").pack()
        else:
            messagebox.showinfo("No Image", "No processed image found. Please scan an image first.")
    
    def refresh_app(self):
        """Reset the application state to handle a new image"""
        # Clear current image data
        self.current_image = None
        self.current_image_path = None
        self.extracted_text = ""
        
        # Reset UI elements
        self.text_box.delete(1.0, tk.END)
        self.preview_label.config(image="", text="")
        self.preview_label.image = None
        
        # Reset preprocessing option
        self.preproc_var.set("none")
        
        # Disable the view processed image button
        self.view_processed_btn.config(state=tk.DISABLED)
        
        # Update status
        self.status_var.set("Application reset. Ready for new image.")
    
    def _is_probably_empty_image(self, image):
        """Check if the image is likely empty (all white or all black)"""
        # Convert to numpy array
        img_array = np.array(image)
        
        # If grayscale
        if len(img_array.shape) == 2:
            # Check if more than 99% of pixels are white or black
            white_ratio = np.sum(img_array > 240) / img_array.size
            black_ratio = np.sum(img_array < 15) / img_array.size
            return white_ratio > 0.99 or black_ratio > 0.99
        
        # If RGB
        elif len(img_array.shape) == 3:
            # Convert to grayscale and check
            gray = np.mean(img_array, axis=2)
            white_ratio = np.sum(gray > 240) / gray.size
            black_ratio = np.sum(gray < 15) / gray.size
            return white_ratio > 0.99 or black_ratio > 0.99
            
        return False

    def _on_preview_frame_configure(self, event):
        """Update the scrollregion when the preview frame changes size"""
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
    
    def _on_preview_canvas_configure(self, event):
        """Resize the inner frame when the canvas changes size"""
        # Update the width of the preview frame window
        self.preview_canvas.itemconfig(self.preview_frame_window, width=event.width)
    
    def _enhance_screenshot(self, image):
        """Apply specialized preprocessing for screenshots"""
        try:
            # Convert to numpy for processing
            img_np = np.array(image)
            
            # Convert to grayscale if color
            if len(img_np.shape) == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
            
            # Create multiple processed versions for multi-pass OCR
            processed_versions = []
            
            # Version 1: Sharp contrast for UI text
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_versions.append(binary)
            
            # Version 2: Edge enhancement for crisp text
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(gray, -1, kernel)
            _, sharp_binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_versions.append(sharp_binary)
            
            # Version 3: Adaptive threshold for variable backgrounds
            adaptive = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            processed_versions.append(adaptive)
            
            # Store all versions for multi-pass OCR
            self.processing_results = processed_versions
            self.multi_processing_available = True
            
            # Return the binary version as primary (best for most screenshots)
            processed_img = Image.fromarray(binary)
            return processed_img
            
        except Exception as e:
            print(f"Screenshot enhancement error: {str(e)}")
            return image  # Return original if processing fails
    
    def _enhance_document(self, image):
        """Apply specialized preprocessing for text documents"""
        try:
            # Convert to numpy for processing
            img_np = np.array(image)
            
            # Convert to grayscale if color
            if len(img_np.shape) == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
            
            # Create multiple processed versions for multi-pass OCR
            processed_versions = []
            
            # Version 1: Enhanced contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            processed_versions.append(enhanced)
            
            # Version 2: Adaptive threshold for handling shadows and uneven lighting
            adaptive = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            processed_versions.append(adaptive)
            
            # Version 3: Denoised for cleaner text
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            processed_versions.append(denoised)
            
            # Version 4: Otsu's threshold for clean black and white text
            _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_versions.append(otsu)
            
            # Version 5: Light morphological operations to connect broken text
            kernel = np.ones((1, 1), np.uint8)
            morph = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)
            processed_versions.append(morph)
            
            # Store all versions for multi-pass OCR
            self.processing_results = processed_versions
            self.multi_processing_available = True
            
            # Return the adaptive threshold version as primary (best for most documents)
            processed_img = Image.fromarray(adaptive)
            return processed_img
            
        except Exception as e:
            print(f"Document enhancement error: {str(e)}")
            return image  # Return original if processing fails
    
    def _enhance_single_line(self, image):
        """Apply specialized preprocessing for single line text/buttons"""
        try:
            # Convert to numpy for processing
            img_np = np.array(image)
            
            # Convert to grayscale if color
            if len(img_np.shape) == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
            
            # For small images, scale up to improve OCR
            h, w = gray.shape
            if max(h, w) < 100:
                scale_factor = 3.0
                gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            
            # Create multiple processed versions for multi-pass OCR
            processed_versions = []
            
            # Version 1: Basic contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
            processed_versions.append(enhanced)
            
            # Version 2: Strong threshold for clear contrast
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_versions.append(binary)
            
            # Version 3: Edge enhancement for better definition
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            processed_versions.append(sharpened)
            
            # Version 4: Dilate slightly to connect broken characters
            kernel = np.ones((2, 2), np.uint8)
            dilated = cv2.dilate(binary, kernel, iterations=1)
            processed_versions.append(dilated)
            
            # Store all versions for multi-pass OCR
            self.processing_results = processed_versions
            self.multi_processing_available = True
            
            # Return the binary version as primary
            processed_img = Image.fromarray(binary)
            return processed_img
            
        except Exception as e:
            print(f"Single line enhancement error: {str(e)}")
            return image  # Return original if processing fails
    
    def _select_best_document_result(self, results):
        """Select the best OCR result for document images"""
        if not results:
            return ""
            
        if len(results) == 1:
            return results[0]
        
        # Filter out empty results
        non_empty = [r for r in results if r.strip()]
        if not non_empty:
            return ""
            
        # Calculate scores for each result
        scores = []
        for result in non_empty:
            score = 0
            
            # Longer text usually means better recognition (unless it's just noise)
            words = result.split()
            score += min(len(words), 100)  # Cap at 100 words to avoid bias
            
            # More real words = better score (words with at least 3 chars)
            real_word_count = sum(1 for word in words if len(word) > 2 and word.isalpha())
            score += real_word_count * 2
            
            # Higher ratio of alphanumeric characters is better
            alphanumeric_ratio = sum(c.isalnum() or c.isspace() for c in result) / max(1, len(result))
            score += alphanumeric_ratio * 100
            
            # Penalize excessive special characters
            special_char_ratio = sum(not (c.isalnum() or c.isspace()) for c in result) / max(1, len(result))
            score -= special_char_ratio * 50
            
            # Bonus for having paragraphs (indicates good structure detection)
            paragraphs = [p for p in result.split('\n\n') if p.strip()]
            score += min(len(paragraphs), 10) * 5
            
            scores.append((score, result))
        
        # Return the result with the highest score
        scores.sort(reverse=True)
        print(f"Selected best document result with score {scores[0][0]}")
        return scores[0][1]
    
    def _select_best_screenshot_result(self, results):
        """Select the best OCR result for screenshot images"""
        if not results:
            return ""
            
        if len(results) == 1:
            return results[0]
        
        # Filter out empty results
        non_empty = [r for r in results if r.strip()]
        if not non_empty:
            return ""
            
        # Calculate scores for each result
        scores = []
        for result in non_empty:
            score = 0
            
            # For screenshots, we want to preserve structure
            # More lines likely means better UI element detection
            lines = [line for line in result.split('\n') if line.strip()]
            score += min(len(lines), 30) * 3
            
            # Look for UI element keywords
            ui_keywords = ['menu', 'file', 'edit', 'view', 'window', 'help', 'options', 
                          'tools', 'settings', 'preferences', 'button', 'click', 'select',
                          'save', 'cancel', 'ok', 'yes', 'no', 'submit', 'login', 'sign']
            
            # Count matches for UI keywords (case insensitive)
            result_lower = result.lower()
            keyword_count = sum(1 for keyword in ui_keywords if keyword in result_lower)
            score += keyword_count * 8
            
            # For screenshots, shorter words are often UI elements
            avg_word_length = sum(len(word) for word in result.split()) / max(1, len(result.split()))
            if avg_word_length < 6:  # UI text tends to be shorter
                score += 20
            
            # Penalize excessive punctuation (UI elements typically have little)
            punct_ratio = sum(c in ',.;:!?' for c in result) / max(1, len(result))
            score -= punct_ratio * 40
            
            scores.append((score, result))
        
        # Return the result with the highest score
        scores.sort(reverse=True)
        print(f"Selected best screenshot result with score {scores[0][0]}")
        return scores[0][1]

def main():
    root = tk.Tk()
    app = OCRApp(root)
    root.update()  # Update to get correct window sizes
    
    # Configure window resizing behavior
    root.minsize(900, 700)
    
    root.mainloop()

if __name__ == "__main__":
    main() 