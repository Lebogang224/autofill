import sys
import os
import re
import json
import tempfile
import pytesseract
import pdfplumber
from pdfrw import PdfReader, PdfWriter
from pdfrw.objects import PdfName
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl
from reportlab.pdfgen import canvas
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QGroupBox, QPushButton, QLabel, QFileDialog, QCheckBox, QLineEdit,
                             QMessageBox, QTextEdit, QProgressBar, QListWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np

# Constants
ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_VAL_KEY = '/V'

class PDFProcessor:
    @staticmethod
    def extract_data_from_pdf(pdf_path):
        """Extract text from PDF using OCR if needed"""
        try:
            # First try text extraction
            with pdfplumber.open(pdf_path) as pdf:
                full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            
            # If text extraction fails, use OCR
            if not full_text.strip():
                images = convert_from_path(pdf_path, dpi=300)
                full_text = ""
                
                for img in images:
                    try:
                        # Convert to grayscale
                        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
                        
                        # Denoise
                        denoised = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
                        
                        # Adaptive thresholding
                        thresh = cv2.adaptiveThreshold(denoised, 255, 
                                                      cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                      cv2.THRESH_BINARY, 11, 2)
                        
                        # Convert back to PIL image
                        processed_img = Image.fromarray(thresh)
                        
                        # OCR with improved settings
                        custom_config = r'--oem 3 --psm 6 -l eng'
                        page_text = pytesseract.image_to_string(processed_img, config=custom_config)
                        full_text += page_text + "\n"
                    except Exception as e:
                        print(f"OCR failed for page: {e}")
                        continue
            
            # Field extraction patterns
            field_patterns = {
                'full_name': r'(?:name|full[_\s]*name)[\s:\-]*(.+)',
                'ssn': r'\b(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b',
                'email': r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b',
                'phone': r'(?:phone|tel|telephone)[\s:\-]*([\d\s().-]+)',
                'address': r'(?:address|street)[\s:\-]*(.+)',
                'date_of_birth': r'(?:dob|date\s*of\s*birth)[\s:\-]*([\d/\s-]+)'
            }
            
            # Extract data using patterns
            data = {}
            for field, pattern in field_patterns.items():
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    data[field] = match.group(1).strip()
                    
            return data
        except Exception as e:
            print(f"Extraction error: {e}")
            return {}
    
    @staticmethod
    def is_digital_form(pdf_path):
        """Check if PDF has fillable form fields"""
        try:
            pdf = PdfReader(pdf_path)
            return any(page.get(ANNOT_KEY) for page in pdf.pages)
        except Exception as e:
            print(f"Digital form check failed: {e}")
            return False
    
    @staticmethod
    def fill_digital_pdf(template_path, data, output_path):
        """Fill PDFs with AcroForm fields"""
        try:
            template_pdf = PdfReader(template_path)
            for page in template_pdf.pages:
                annotations = page.get(ANNOT_KEY) or []
                for annotation in annotations:
                    if annotation.get(ANNOT_FIELD_KEY):
                        field_name = annotation[ANNOT_FIELD_KEY][1:-1]  # Remove PDF string quotes
                        if field_name in data:
                            annotation.update({
                                ANNOT_VAL_KEY: f'({data[field_name]})'  # PDF string format
                            })
            PdfWriter().write(output_path, template_pdf)
            return True
        except Exception as e:
            print(f"Digital fill failed: {e}")
            return False
    
    @staticmethod
    def overlay_fill_pdf(template_path, data, output_path):
        """Fill non-digital PDFs with text overlay"""
        try:
            # Create a temporary PDF to draw on
            c = canvas.Canvas(output_path)
            
            # Read the template PDF
            template = PdfReader(template_path)
            
            # Iterate through pages
            for page_num, page in enumerate(template.pages):
                # Get the page size
                media_box = page[PdfName.MediaBox]
                page_width = float(media_box[2])
                page_height = float(media_box[3])
                
                # Set the page size
                c.setPageSize((page_width, page_height))
                
                # Draw the original page as background
                page_obj = pagexobj(page)
                rl_obj = makerl(c, page_obj)
                c.doForm(rl_obj)
                
                # Add text overlay
                for field, value in data.items():
                    # For simplicity, we're placing all text at fixed positions
                    # In a real app, you'd have a mapping configuration
                    y_pos = page_height - (100 + 20 * list(data.keys()).index(field))
                    c.drawString(100, y_pos, f"{field}: {value}")
                
                c.showPage()
            
            c.save()
            return True
        except Exception as e:
            print(f"Overlay fill error: {e}")
            return False
    
    @staticmethod
    def fill_pdf(template_path, data, output_path):
        """
        Main filling function - automatically routes to:
        - Digital form filler (for fillable PDFs)
        - Overlay filler (for scanned/flat PDFs)
        """
        if PDFProcessor.is_digital_form(template_path):
            print("Detected digital form - using AcroForm filler")
            return PDFProcessor.fill_digital_pdf(template_path, data, output_path)
        else:
            print("Detected scanned/flat PDF - using overlay filler")
            return PDFProcessor.overlay_fill_pdf(template_path, data, output_path)


class ProcessingThread(QThread):
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    result = pyqtSignal(str, str)  # (status, output_path)
    extracted_data = pyqtSignal(dict, list)  # (data, errors)

    def __init__(self, operation_type, *args):
        super().__init__()
        self.operation_type = operation_type
        self.args = args
        self.force_fill = False

    def run(self):
        try:
            if self.operation_type == "extract_and_fill":
                filled_pdf, empty_form, force_fill = self.args
                self.force_fill = force_fill
                
                self.message.emit("Extracting data from PDF...")
                data = PDFProcessor.extract_data_from_pdf(filled_pdf)
                self.progress.emit(30)
                
                # Validate data
                errors = self.validate_data(data)
                self.progress.emit(40)
                
                # If there are errors and we're not forcing, return for preview
                if errors and not force_fill:
                    self.extracted_data.emit(data, errors)
                    return
                
                # Proceed with filling
                self.fill_pdf(data, empty_form)
                
            elif self.operation_type == "fill_from_json":
                json_file, empty_form = self.args
                self.message.emit("Reading JSON data...")
                
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                self.progress.emit(30)
                self.fill_pdf(data, empty_form)
                
        except Exception as e:
            self.result.emit("error", f"Processing failed: {str(e)}")

    def fill_pdf(self, data, template_path):
        self.message.emit("Filling PDF form...")
        output_dir = tempfile.mkdtemp()
        output_file = os.path.join(output_dir, "filled_form.pdf")
        
        if PDFProcessor.fill_pdf(template_path, data, output_file):
            self.progress.emit(100)
            self.result.emit("success", output_file)
        else:
            self.result.emit("error", "Failed to fill PDF")

    @staticmethod
    def validate_data(data):
        errors = []
        if not any(field in data and data[field].strip() for field in ['full_name', 'name']):
            errors.append("Full name is required")

        ssn = data.get('ssn', '').strip()
        if ssn:
            clean_ssn = re.sub(r'[^\d]', '', ssn)
            if len(clean_ssn) != 9:
                errors.append("SSN must be 9 digits")
        
        return errors


class AutoFillApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF AutoFill Desktop")
        self.setGeometry(100, 100, 800, 600)
        
        try:
            self.setWindowIcon(QIcon("autofill_icon.png"))
        except:
            pass
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_extract_fill_tab()
        self.create_fill_from_json_tab()
        
        # Status bar
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Initialize variables
        self.filled_pdf_path = ""
        self.empty_form_path = ""
        self.json_file_path = ""
        self.output_file = ""
        self.current_data = {}
        self.current_errors = []

    def create_extract_fill_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Section 1: Extract from Filled PDF
        extract_group = QGroupBox("Extract from Filled PDF")
        extract_layout = QVBoxLayout(extract_group)
        
        # Filled PDF selection
        filled_pdf_layout = QHBoxLayout()
        self.filled_pdf_label = QLabel("No file selected")
        filled_pdf_btn = QPushButton("Select Filled PDF")
        filled_pdf_btn.clicked.connect(self.select_filled_pdf)
        filled_pdf_layout.addWidget(QLabel("Filled PDF:"))
        filled_pdf_layout.addWidget(self.filled_pdf_label, 1)
        filled_pdf_layout.addWidget(filled_pdf_btn)
        extract_layout.addLayout(filled_pdf_layout)
        
        # Empty form selection
        empty_form_layout = QHBoxLayout()
        self.empty_form_label = QLabel("No file selected")
        empty_form_btn = QPushButton("Select Empty Form")
        empty_form_btn.clicked.connect(self.select_empty_form)
        empty_form_layout.addWidget(QLabel("Empty Form:"))
        empty_form_layout.addWidget(self.empty_form_label, 1)
        empty_form_layout.addWidget(empty_form_btn)
        extract_layout.addLayout(empty_form_layout)
        
        # Force fill checkbox
        self.force_fill_check = QCheckBox("Force Fill (Ignore Validation)")
        extract_layout.addWidget(self.force_fill_check)
        
        # Submit button
        submit_btn = QPushButton("Submit PDFs")
        submit_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        submit_btn.clicked.connect(self.process_pdfs)
        extract_layout.addWidget(submit_btn)
        
        layout.addWidget(extract_group)
        
        # Preview area (initially hidden)
        self.preview_group = QGroupBox("Data Preview")
        self.preview_group.setVisible(False)
        preview_layout = QVBoxLayout(self.preview_group)
        
        self.data_preview = QTextEdit()
        self.data_preview.setReadOnly(True)
        preview_layout.addWidget(self.data_preview)
        
        self.error_list = QListWidget()
        preview_layout.addWidget(QLabel("Validation Errors:"))
        preview_layout.addWidget(self.error_list)
        
        force_fill_btn = QPushButton("Force Fill Anyway")
        force_fill_btn.setStyleSheet("background-color: #FF9800; font-weight: bold;")
        force_fill_btn.clicked.connect(self.force_fill_pdf)
        preview_layout.addWidget(force_fill_btn)
        
        layout.addWidget(self.preview_group)
        
        self.tab_widget.addTab(tab, "Extract & Fill")

    def create_fill_from_json_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Section: Fill from JSON
        json_group = QGroupBox("Fill from JSON File")
        json_layout = QVBoxLayout(json_group)
        
        # JSON file selection
        json_layout.addWidget(QLabel("Select JSON file with form data:"))
        
        json_file_layout = QHBoxLayout()
        self.json_file_label = QLabel("No file selected")
        json_file_btn = QPushButton("Select JSON File")
        json_file_btn.clicked.connect(self.select_json_file)
        json_file_layout.addWidget(self.json_file_label, 1)
        json_file_layout.addWidget(json_file_btn)
        json_layout.addLayout(json_file_layout)
        
        # Empty form selection
        json_form_layout = QHBoxLayout()
        self.json_form_label = QLabel("No file selected")
        json_form_btn = QPushButton("Select Empty Form")
        json_form_btn.clicked.connect(self.select_json_form)
        json_form_layout.addWidget(QLabel("Empty Form:"))
        json_form_layout.addWidget(self.json_form_label, 1)
        json_form_layout.addWidget(json_form_btn)
        json_layout.addLayout(json_form_layout)
        
        # Submit button
        json_submit_btn = QPushButton("Fill from JSON")
        json_submit_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        json_submit_btn.clicked.connect(self.fill_from_json)
        json_layout.addWidget(json_submit_btn)
        
        layout.addWidget(json_group)
        
        self.tab_widget.addTab(tab, "Fill from JSON")

    def select_filled_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Filled PDF", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.filled_pdf_path = file_path
            self.filled_pdf_label.setText(os.path.basename(file_path))

    def select_empty_form(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Empty Form", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.empty_form_path = file_path
            self.empty_form_label.setText(os.path.basename(file_path))

    def select_json_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select JSON File", "", "JSON Files (*.json)"
        )
        if file_path:
            self.json_file_path = file_path
            self.json_file_label.setText(os.path.basename(file_path))

    def select_json_form(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Empty Form", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.json_form_path = file_path
            self.json_form_label.setText(os.path.basename(file_path))

    def process_pdfs(self):
        if not self.filled_pdf_path or not self.empty_form_path:
            QMessageBox.warning(self, "Missing Files", "Please select both PDF files")
            return
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start processing thread
        self.worker = ProcessingThread(
            "extract_and_fill", 
            self.filled_pdf_path, 
            self.empty_form_path,
            self.force_fill_check.isChecked()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.message.connect(self.status_bar.showMessage)
        self.worker.result.connect(self.handle_result)
        self.worker.extracted_data.connect(self.show_data_preview)
        self.worker.start()

    def fill_from_json(self):
        if not self.json_file_path or not self.json_form_path:
            QMessageBox.warning(self, "Missing Files", "Please select both JSON and PDF files")
            return
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start processing thread
        self.worker = ProcessingThread(
            "fill_from_json", 
            self.json_file_path, 
            self.json_form_path
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.message.connect(self.status_bar.showMessage)
        self.worker.result.connect(self.handle_result)
        self.worker.start()

    def show_data_preview(self, data, errors):
        self.current_data = data
        self.current_errors = errors
        
        # Format data for display
        preview_text = "Extracted Data:\n\n"
        for key, value in data.items():
            preview_text += f"{key.replace('_', ' ').title()}: {value}\n"
        
        self.data_preview.setText(preview_text)
        
        # Show errors
        self.error_list.clear()
        for error in errors:
            self.error_list.addItem(error)
        
        # Show preview group
        self.preview_group.setVisible(True)
        self.progress_bar.setVisible(False)

    def force_fill_pdf(self):
        if not self.filled_pdf_path or not self.empty_form_path:
            return
        
        # Hide preview
        self.preview_group.setVisible(False)
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(50)
        
        # Start processing thread with force fill
        self.worker = ProcessingThread(
            "extract_and_fill", 
            self.filled_pdf_path, 
            self.empty_form_path,
            True  # Force fill
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.message.connect(self.status_bar.showMessage)
        self.worker.result.connect(self.handle_result)
        self.worker.start()

    def handle_result(self, status, output_path):
        self.progress_bar.setVisible(False)
        
        if status == "success":
            self.output_file = output_path
            self.status_bar.showMessage("Processing completed successfully")
            
            # Ask to open the file
            reply = QMessageBox.question(
                self, "Success", 
                "PDF filled successfully! Would you like to open the file?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.open_file(output_path)
        else:
            QMessageBox.critical(self, "Error", output_path)
            self.status_bar.showMessage("Processing failed")

    def open_file(self, file_path):
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                os.system(f'open "{file_path}"')
            else:
                os.system(f'xdg-open "{file_path}"')
        except Exception as e:
            QMessageBox.warning(self, "Open Failed", f"Could not open file: {str(e)}")


if __name__ == "__main__":
    # Set Tesseract path if on Windows
    if sys.platform == "win32":
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        else:
            print("Warning: Tesseract OCR not found at default location. OCR may not work.")
    
    # Create application
    app = QApplication(sys.argv)
    window = AutoFillApp()
    window.show()
    sys.exit(app.exec_())
