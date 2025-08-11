from markitdown import MarkItDown
import mammoth
import os


file_path = os.path.join('test_docs', 'test1.docx')

with open(file_path, 'rb') as file:
    result = mammoth.convert_to_html(file)
    html_output = result.value

print(html_output)