import zipfile
import os

def create_zip_folder(zip_name, file_paths):
    """
    Create a ZIP folder and add specified files to it.
    
    :param zip_name: Name of the ZIP file to create (e.g., 'my_archive.zip').
    :param file_paths: List of file paths to include in the ZIP.
    """
    try:
        # Create a new ZIP file
        with zipfile.ZipFile(zip_name, 'w') as zipf:
            for file in file_paths:
                # Add each file to the ZIP
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
                    print(f"Added {file} to {zip_name}")
                else:
                    print(f"File not found: {file}")
        print(f"ZIP folder '{zip_name}' created successfully.")
    except Exception as e:
        print(f"Error creating ZIP folder: {e}")

# Example usage
file_list = [
    "file1.txt",  # Replace with the actual file paths
    "file2.csv",
    "file3.json"
]
create_zip_folder("my_archive.zip", file_list)
