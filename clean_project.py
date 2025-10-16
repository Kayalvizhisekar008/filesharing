import os
import glob

def clean_python_files():
    """Clean all Python files in the project of null bytes."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Find all Python files
    python_files = glob.glob(os.path.join(project_root, '**', '*.py'), recursive=True)
    
    for file_path in python_files:
        try:
            # Read file content in binary mode
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Check for null bytes
            if b'\x00' in content:
                print(f'Found null bytes in {file_path}')
                # Remove null bytes and decode
                clean_content = content.replace(b'\x00', b'').decode('utf-8', errors='ignore')
                
                # Write back clean content
                with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(clean_content)
                print(f'Cleaned {file_path}')
        except Exception as e:
            print(f'Error processing {file_path}: {str(e)}')

if __name__ == '__main__':
    clean_python_files()